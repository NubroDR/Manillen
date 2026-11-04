"""Build a validated, inactive ID-based staging dataset from an approved proposal."""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from data_paths import DATA_DIR
from manillen_core.reference_helpers import (
    ID_ALPHABET,
    is_reserve_reference,
    normalize_reference_name,
)
from migrate_ids import _source_hashes, calculate_proposal_hash
from profile_data import CSV_SCHEMAS


VERSIONED_SCHEMAS = {
    "players.csv": ("PlayerID", "Name", "PoolMember", "Active"),
    "player_aliases.csv": ("Alias", "PlayerID", "Source"),
    "locations.csv": ("LocationID", "Name", "Active"),
    "location_aliases.csv": ("Alias", "LocationID", "Source"),
    "pairings.csv": ("Player1", "Player2", "Count"),
    "pairings_history.csv": ("Date", "Table", "Players", "Season", "Location"),
    "scores_history.csv": (
        "Date",
        "Table",
        "Game",
        "Team1Players",
        "Team2Players",
        "Team1Score",
        "Team2Score",
    ),
    "reserve_assignments.csv": ("Date", "Slot", "PlayerID"),
    "seasons.csv": ("Season", "SeasonNumber", "SeasonStartYear", "Status"),
}
_ID_PATTERNS = {
    "PlayerID": re.compile(rf"^plr_[{re.escape(ID_ALPHABET)}]{{5}}$"),
    "LocationID": re.compile(rf"^loc_[{re.escape(ID_ALPHABET)}]{{5}}$"),
}
_RESERVE_PATTERN = re.compile(r"^reserve(?:\s+|:)([1-9]\d*)$", re.IGNORECASE)


def _read_csv(path, expected_columns):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != tuple(expected_columns):
            raise ValueError(f"Unexpected CSV schema: {path.name}")
        return list(reader)


def _load_approved_proposal(data_dir, proposal_path, approval_path):
    try:
        proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
        approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read the proposal and approval JSON files.") from error
    if not isinstance(proposal, dict) or not isinstance(approval, dict):
        raise ValueError("Proposal and approval must both be JSON objects.")

    proposal_hash = proposal.get("proposal_sha256")
    if not isinstance(proposal_hash, str) or calculate_proposal_hash(
        proposal
    ) != proposal_hash:
        raise ValueError("The proposal integrity hash is invalid.")
    if proposal.get("proposal_version") != 1:
        raise ValueError("Unsupported ID proposal version.")
    if approval.get("status") != "approved":
        raise ValueError("The proposal has not been explicitly approved.")
    if approval.get("proposal_sha256") != proposal_hash:
        raise ValueError("The approval does not match this exact proposal.")
    if not isinstance(approval.get("approved_by"), str) or not approval[
        "approved_by"
    ].strip():
        raise ValueError("The approval must identify the reviewer.")
    approved_at = approval.get("approved_at")
    if not isinstance(approved_at, str):
        raise ValueError("The approval must include an ISO 8601 timestamp.")
    try:
        parsed_approval_time = datetime.fromisoformat(approved_at)
    except ValueError as error:
        raise ValueError("The approval timestamp is not valid ISO 8601.") from error
    if parsed_approval_time.tzinfo is None:
        raise ValueError("The approval timestamp must include a timezone.")

    expected_hashes = _source_hashes(data_dir)
    if proposal.get("source_hashes") != expected_hashes:
        raise ValueError("Source data has changed since the proposal was generated.")
    return proposal, approval, proposal_hash


def _reference_maps(proposal, rows_key, aliases_key, id_key, kind):
    entities = proposal.get(rows_key)
    aliases = proposal.get(aliases_key)
    if not isinstance(entities, list) or not isinstance(aliases, list):
        raise ValueError(f"Proposal is missing {kind} entities or aliases.")

    ids = set()
    lookup = {}
    for row in entities:
        if not isinstance(row, dict):
            raise ValueError(f"Invalid {kind} entity in proposal.")
        reference_id = row.get(id_key)
        name = row.get("Name")
        if (
            not isinstance(reference_id, str)
            or not _ID_PATTERNS[id_key].fullmatch(reference_id)
            or reference_id in ids
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError(f"Invalid or duplicate {kind} entity in proposal.")
        ids.add(reference_id)
        normalized = normalize_reference_name(name)
        if normalized in lookup and lookup[normalized] != reference_id:
            raise ValueError(f"Ambiguous normalized {kind} name in proposal.")
        lookup[normalized] = reference_id

        if kind == "player":
            pool_member = row.get("PoolMember")
            active = row.get("Active")
            if type(pool_member) is not int or pool_member not in (0, 1):
                raise ValueError("Every approved player needs a reviewed PoolMember value.")
            if type(active) is not int or active not in (0, 1):
                raise ValueError("Every approved player needs a reviewed Active value.")
        elif type(row.get("Active")) is not int or row["Active"] not in (0, 1):
            raise ValueError("Every approved location needs a reviewed Active value.")

    for alias in aliases:
        if not isinstance(alias, dict):
            raise ValueError(f"Invalid {kind} alias in proposal.")
        reference_id = alias.get(id_key)
        name = alias.get("Alias")
        if reference_id not in ids or not isinstance(name, str) or not name.strip():
            raise ValueError(f"Invalid {kind} alias target in proposal.")
        normalized = normalize_reference_name(name)
        existing = lookup.get(normalized)
        if existing is not None and existing != reference_id:
            raise ValueError(f"Conflicting normalized {kind} alias in proposal.")
        lookup[normalized] = reference_id
    return lookup, ids


def _map_player_token(value, player_lookup, context):
    token = str(value or "").strip()
    if is_reserve_reference(token):
        match = _RESERVE_PATTERN.fullmatch(token)
        return f"RESERVE:{int(match.group(1))}"
    reference_id = player_lookup.get(normalize_reference_name(token))
    if reference_id is None:
        raise ValueError(f"Unknown player reference in {context}.")
    return reference_id


def _map_tokens(value, count, player_lookup, context):
    tokens = [token.strip() for token in str(value or "").split("|")]
    if len(tokens) != count or any(not token for token in tokens):
        raise ValueError(f"Expected {count} player references in {context}.")
    mapped = [
        _map_player_token(token, player_lookup, context) for token in tokens
    ]
    if len(set(mapped)) != len(mapped):
        raise ValueError(f"Duplicate player reference in {context}.")
    return mapped


def _write_csv(directory, filename, columns, rows):
    with (directory / filename).open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _transform(data_dir, stage_dir, proposal):
    player_lookup, player_ids = _reference_maps(
        proposal, "players", "player_aliases", "PlayerID", "player"
    )
    location_lookup, location_ids = _reference_maps(
        proposal, "locations", "location_aliases", "LocationID", "location"
    )
    source_rows = {
        filename: _read_csv(data_dir / filename, CSV_SCHEMAS[filename])
        for filename in CSV_SCHEMAS
    }
    output_rows = {}

    players = []
    for row in proposal["players"]:
        players.append({
            "PlayerID": row["PlayerID"],
            "Name": row["Name"].strip(),
            "PoolMember": row["PoolMember"],
            "Active": row["Active"],
        })
    output_rows["players.csv"] = players
    output_rows["player_aliases.csv"] = [
        {
            "Alias": row["Alias"],
            "PlayerID": row["PlayerID"],
            "Source": row.get("Source", ""),
        }
        for row in proposal["player_aliases"]
    ]
    output_rows["locations.csv"] = [
        {
            "LocationID": row["LocationID"],
            "Name": row["Name"].strip(),
            "Active": row["Active"],
        }
        for row in proposal["locations"]
    ]
    output_rows["location_aliases.csv"] = [
        {
            "Alias": row["Alias"],
            "LocationID": row["LocationID"],
            "Source": row.get("Source", ""),
        }
        for row in proposal["location_aliases"]
    ]

    pair_counts = defaultdict(int)
    for row_number, row in enumerate(source_rows["pairings.csv"], start=2):
        player1 = _map_player_token(
            row["Player1"], player_lookup, f"pairings.csv row {row_number}"
        )
        player2 = _map_player_token(
            row["Player2"], player_lookup, f"pairings.csv row {row_number}"
        )
        if player1.startswith("RESERVE:") or player2.startswith("RESERVE:"):
            raise ValueError(f"Reserve placeholder in pairings.csv row {row_number}.")
        if player1 == player2:
            raise ValueError(f"Self-pair in pairings.csv row {row_number}.")
        try:
            count = int(row["Count"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid pairing count in pairings.csv row {row_number}."
            ) from error
        if count < 0 or str(count) != row["Count"].strip():
            raise ValueError(f"Invalid pairing count in pairings.csv row {row_number}.")
        pair_counts[tuple(sorted((player1, player2)))] += count
    output_rows["pairings.csv"] = [
        {"Player1": pair[0], "Player2": pair[1], "Count": str(count)}
        for pair, count in sorted(pair_counts.items())
    ]

    table_reserves = defaultdict(list)
    table_ids_by_date = defaultdict(set)
    transformed_history = []
    for row_number, row in enumerate(source_rows["pairings_history.csv"], start=2):
        context = f"pairings_history.csv row {row_number}"
        mapped_players = _map_tokens(row["Players"], 4, player_lookup, context)
        reserves = [token for token in mapped_players if token.startswith("RESERVE:")]
        if len(reserves) > 1:
            raise ValueError(f"More than one reserve in {context}.")
        table_key = (row["Date"], row["Table"])
        if table_key in table_ids_by_date[row["Date"]]:
            raise ValueError(f"Duplicate table in {context}.")
        table_ids_by_date[row["Date"]].add(table_key)
        table_reserves[row["Date"]].extend(
            int(token.split(":", 1)[1]) for token in reserves
        )
        location = (row.get("Location") or "").strip()
        location_id = ""
        if location:
            location_id = location_lookup.get(normalize_reference_name(location), "")
            if not location_id:
                raise ValueError(f"Unknown location reference in {context}.")
        transformed_history.append({
            **row,
            "Players": " | ".join(mapped_players),
            "Location": location_id,
        })
    for playday, reserve_slots in table_reserves.items():
        table_count = len(table_ids_by_date[playday])
        if any(slot > table_count for slot in reserve_slots):
            raise ValueError(f"Reserve slot exceeds table count on {playday}.")
    output_rows["pairings_history.csv"] = transformed_history

    transformed_scores = []
    for row_number, row in enumerate(source_rows["scores_history.csv"], start=2):
        context = f"scores_history.csv row {row_number}"
        if (row["Date"], row["Table"]) not in table_ids_by_date[row["Date"]]:
            raise ValueError(f"No matching table in {context}.")
        table_count = len(table_ids_by_date[row["Date"]])
        for column in ("Team1Players", "Team2Players"):
            for token in _map_tokens(row[column], 2, player_lookup, context):
                if token.startswith("RESERVE:") and int(token.split(":", 1)[1]) > table_count:
                    raise ValueError(f"Reserve slot exceeds table count in {context}.")
        transformed_scores.append({
            **row,
            "Team1Players": " | ".join(
                _map_tokens(row["Team1Players"], 2, player_lookup, context)
            ),
            "Team2Players": " | ".join(
                _map_tokens(row["Team2Players"], 2, player_lookup, context)
            ),
        })
    output_rows["scores_history.csv"] = transformed_scores

    assignments = []
    seen_assignments = set()
    for row_number, row in enumerate(source_rows["reserve_assignments.csv"], start=2):
        context = f"reserve_assignments.csv row {row_number}"
        slot = row["Slot"].strip()
        if not is_reserve_reference(slot):
            raise ValueError(f"Invalid reserve slot in {context}.")
        slot_match = _RESERVE_PATTERN.fullmatch(slot)
        normalized_slot = f"RESERVE:{int(slot_match.group(1))}"
        key = (row["Date"], normalized_slot)
        if key in seen_assignments:
            raise ValueError(f"Duplicate reserve assignment in {context}.")
        table_count = len(table_ids_by_date[row["Date"]])
        if table_count == 0 or int(normalized_slot.split(":", 1)[1]) > table_count:
            raise ValueError(f"Reserve slot has no matching table in {context}.")
        seen_assignments.add(key)
        assignments.append({
            "Date": row["Date"],
            "Slot": normalized_slot,
            "PlayerID": _map_player_token(row["Name"], player_lookup, context),
        })
    output_rows["reserve_assignments.csv"] = assignments

    output_rows["seasons.csv"] = source_rows["seasons.csv"]
    score_baseline = [
        tuple(row[column] for column in (
            "Date", "Table", "Game", "Team1Score", "Team2Score"
        ))
        for row in source_rows["scores_history.csv"]
    ]
    transformed_score_baseline = [
        tuple(row[column] for column in (
            "Date", "Table", "Game", "Team1Score", "Team2Score"
        ))
        for row in output_rows["scores_history.csv"]
    ]
    if score_baseline != transformed_score_baseline:
        raise ValueError("Score rows or score values changed during staging.")

    partner_counts = {
        f"{pair[0]}|{pair[1]}": count
        for pair, count in sorted(pair_counts.items())
    }
    for filename, rows in output_rows.items():
        _write_csv(stage_dir, filename, VERSIONED_SCHEMAS[filename], rows)
    _validate_staged_data(
        stage_dir, output_rows, player_ids, location_ids, partner_counts
    )
    return {
        "source_rows": {
            filename: len(rows) for filename, rows in source_rows.items()
        },
        "staged_rows": {
            filename: len(rows) for filename, rows in output_rows.items()
        },
        "pairing_count_totals": sum(pair_counts.values()),
        "partner_counts": partner_counts,
        "score_row_count": len(transformed_scores),
        "score_points_total": sum(
            int(row["Team1Score"]) + int(row["Team2Score"])
            for row in transformed_scores
        ),
    }


def _validate_staged_data(
    stage_dir, expected_rows, player_ids, location_ids, expected_partner_counts
):
    staged = {
        filename: _read_csv(stage_dir / filename, schema)
        for filename, schema in VERSIONED_SCHEMAS.items()
    }
    for filename, rows in expected_rows.items():
        if len(staged[filename]) != len(rows):
            raise ValueError(f"Staged row count mismatch in {filename}.")
    if {row["PlayerID"] for row in staged["players.csv"]} != player_ids:
        raise ValueError("Staged player registry does not match the approved proposal.")
    if {row["LocationID"] for row in staged["locations.csv"]} != location_ids:
        raise ValueError("Staged location registry does not match the approved proposal.")
    if any(row["PlayerID"] not in player_ids for row in staged["player_aliases.csv"]):
        raise ValueError("Unknown player ID in staged player aliases.")
    if any(row["LocationID"] not in location_ids for row in staged["location_aliases.csv"]):
        raise ValueError("Unknown location ID in staged location aliases.")
    for row_number, row in enumerate(staged["pairings.csv"], start=2):
        if row["Player1"] not in player_ids or row["Player2"] not in player_ids:
            raise ValueError(f"Unknown player ID in staged pairings.csv row {row_number}.")
    staged_partner_counts = {}
    for row in staged["pairings.csv"]:
        pair = tuple(sorted((row["Player1"], row["Player2"])))
        staged_partner_counts[f"{pair[0]}|{pair[1]}"] = int(row["Count"])
    if staged_partner_counts != expected_partner_counts:
        raise ValueError("Partner-count baseline changed during staging.")
    for filename, columns in (
        ("pairings_history.csv", ("Players",)),
        ("scores_history.csv", ("Team1Players", "Team2Players")),
    ):
        for row_number, row in enumerate(staged[filename], start=2):
            for column in columns:
                for token in row[column].split(" | "):
                    if token.startswith("RESERVE:"):
                        if not _RESERVE_PATTERN.fullmatch(token.replace("RESERVE:", "reserve:")):
                            raise ValueError(f"Invalid reserve token in staged {filename}.")
                    elif token not in player_ids:
                        raise ValueError(f"Unknown player ID in staged {filename} row {row_number}.")
    for row_number, row in enumerate(staged["pairings_history.csv"], start=2):
        if row["Location"] and row["Location"] not in location_ids:
            raise ValueError(
                f"Unknown location ID in staged pairings_history.csv row {row_number}."
            )
    for row_number, row in enumerate(staged["reserve_assignments.csv"], start=2):
        if row["PlayerID"] not in player_ids:
            raise ValueError(
                f"Unknown player ID in staged reserve_assignments.csv row {row_number}."
            )
    score_columns = (
        "Date", "Table", "Game", "Team1Players", "Team2Players",
        "Team1Score", "Team2Score",
    )
    if [
        tuple(row[column] for column in score_columns)
        for row in staged["scores_history.csv"]
    ] != [
        tuple(row[column] for column in score_columns)
        for row in expected_rows["scores_history.csv"]
    ]:
        raise ValueError("Staged score rows changed during validation.")


def stage_id_migration(data_dir, proposal_path, approval_path, staging_output):
    """Write a validated ID-based dataset to a new, inactive external directory."""
    data_dir = Path(data_dir).resolve()
    staging_output = Path(staging_output).resolve()
    repo_root = Path(__file__).resolve().parent
    if staging_output == data_dir or data_dir in staging_output.parents:
        raise ValueError("Staging output must be outside the active data directory.")
    if staging_output == repo_root or repo_root in staging_output.parents:
        raise ValueError("Staging output must be outside the repository.")
    if staging_output.exists():
        raise FileExistsError(f"Refusing to overwrite staging output: {staging_output}")
    if not staging_output.parent.is_dir():
        raise FileNotFoundError(
            f"Staging output parent directory does not exist: {staging_output.parent}"
        )

    proposal, approval, proposal_hash = _load_approved_proposal(
        data_dir, proposal_path, approval_path
    )
    version_id = (
        "v_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_" + uuid.uuid4().hex[:8]
    )
    temporary_dir = Path(tempfile.mkdtemp(
        prefix=f".{staging_output.name}.",
        dir=staging_output.parent,
    ))
    try:
        metrics = _transform(data_dir, temporary_dir, proposal)
        file_hashes = {
            filename: hashlib.sha256((temporary_dir / filename).read_bytes()).hexdigest()
            for filename in VERSIONED_SCHEMAS
        }
        manifest = {
            "version_id": version_id,
            "state": "staged_inactive",
            "proposal_sha256": proposal_hash,
            "source_hashes": _source_hashes(data_dir),
            "approval": {
                "approved_by": approval["approved_by"],
                "approved_at": approval["approved_at"],
            },
            "files": file_hashes,
            "validation": metrics,
        }
        if _source_hashes(data_dir) != proposal["source_hashes"]:
            raise RuntimeError("Source data changed while staging was being built.")
        (temporary_dir / "staging-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_dir, staging_output)
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build an inactive ID migration staging dataset."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--staging-output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = stage_id_migration(
        args.data_dir, args.proposal, args.approval, args.staging_output
    )
    validation = manifest["validation"]
    print(
        f"Validated inactive staging version {manifest['version_id']}; "
        f"{validation['score_row_count']} score rows and "
        f"{validation['pairing_count_totals']} partner-count total. "
        "Active data and version were not changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
