"""Create a read-only, reviewable proposal for the future ID migration."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from data_paths import DATA_DIR
from manillen_core.reference_helpers import (
    generate_reference_id,
    is_reserve_reference,
    normalize_reference_name,
)
from profile_data import CSV_SCHEMAS, profile_data


SOURCE_FILES = ("AllPlayers.csv", *CSV_SCHEMAS)


def _read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _read_roster(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [row[0].strip() for row in csv.reader(file) if row and row[0].strip()]


def _source_hashes(data_dir):
    return {
        filename: hashlib.sha256((data_dir / filename).read_bytes()).hexdigest()
        for filename in SOURCE_FILES
    }


def _display_sort_key(name):
    return (name.casefold(), name.isupper(), name)


def _collect_player_names(data_dir):
    groups = defaultdict(lambda: defaultdict(set))

    def add(value, source):
        name = str(value or "").strip()
        normalized = normalize_reference_name(name)
        if not normalized or is_reserve_reference(name):
            return
        groups[normalized][name].add(source)

    for name in _read_roster(data_dir / "AllPlayers.csv"):
        add(name, "AllPlayers.csv")
    for row in _read_csv(data_dir / "pairings.csv"):
        add(row.get("Player1"), "pairings.csv")
        add(row.get("Player2"), "pairings.csv")
    for row in _read_csv(data_dir / "pairings_history.csv"):
        for name in (row.get("Players") or "").split("|"):
            add(name, "pairings_history.csv")
    for row in _read_csv(data_dir / "scores_history.csv"):
        for column in ("Team1Players", "Team2Players"):
            for name in (row.get(column) or "").split("|"):
                add(name, "scores_history.csv")
    for row in _read_csv(data_dir / "reserve_assignments.csv"):
        add(row.get("Name"), "reserve_assignments.csv")
    for row in _read_csv(data_dir / "seasons_history.csv"):
        for column in ("Gold", "Silver", "Bronze", "RedLantern"):
            for name in (row.get(column) or "").split("|"):
                add(name, "seasons_history.csv")

    return groups


def _collect_location_names(data_dir):
    groups = defaultdict(lambda: defaultdict(set))
    for filename, column in (
        ("pairings_history.csv", "Location"),
        ("seasons_playdays_legacy.csv", "Location"),
    ):
        for row in _read_csv(data_dir / filename):
            name = (row.get(column) or "").strip()
            normalized = normalize_reference_name(name)
            if normalized:
                groups[normalized][name].add(filename)
    return groups


def _build_entities(groups, kind, pool_names=frozenset(), used_ids=None):
    used_ids = used_ids if used_ids is not None else set()
    entities = []
    aliases = []
    for normalized, variants in sorted(groups.items()):
        roster_variants = sorted(
            (name for name, sources in variants.items() if "AllPlayers.csv" in sources),
            key=_display_sort_key,
        )
        names = sorted(variants, key=_display_sort_key)
        canonical_name = roster_variants[0] if roster_variants else names[0]
        reference_id = generate_reference_id(kind, used_ids)
        if kind == "player":
            pool_member = normalized in pool_names
            entities.append({
                "PlayerID": reference_id,
                "Name": canonical_name,
                "PoolMember": int(pool_member),
                "Active": 1 if pool_member else None,
                "active_status": (
                    "confirmed_by_current_roster"
                    if pool_member else "requires_manual_review"
                ),
            })
        else:
            entities.append({
                "LocationID": reference_id,
                "Name": canonical_name,
                "Active": None,
                "active_status": "requires_manual_review",
            })
        for name, sources in sorted(
            variants.items(), key=lambda item: _display_sort_key(item[0])
        ):
            if name == canonical_name:
                continue
            alias = {
                "Alias": name,
                "PlayerID" if kind == "player" else "LocationID": reference_id,
                "Source": ";".join(sorted(sources)),
            }
            aliases.append(alias)
    return entities, aliases


def _review_summary(report):
    quality = report["data_quality"]
    return {
        "schema_issues": len(quality["schema_issues"]),
        "alias_conflicts": len(quality["alias_registry"]["conflicts"]),
        "alias_issues": len(quality["alias_registry"]["issues"]),
        "duplicate_roster_names": len(quality["duplicate_roster_names"]),
        "normalization_collisions": len(quality["normalization_collisions"]),
        "observed_name_variants": len(quality["observed_name_variants"]),
        "unknown_name_groups": len(quality["unknown_name_groups"]),
        "pairing_history_issues": len(quality["pairing_history_issues"]),
        "invalid_reserve_tokens": len(quality["invalid_reserve_tokens"]),
        "invalid_pairing_count_rows": len(quality["invalid_pairing_count_rows"]),
        "invalid_score_rows": len(quality["invalid_score_rows"]),
        "tied_score_rows": len(quality["tied_score_rows"]),
        "pairing_count_drift": len(quality["pairing_count_drift"]),
    }


def calculate_proposal_hash(proposal):
    """Return the integrity hash for proposal content, excluding its hash field."""
    unsigned_proposal = {
        key: value for key, value in proposal.items() if key != "proposal_sha256"
    }
    canonical = json.dumps(
        unsigned_proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_id_proposal(data_dir=DATA_DIR, repo_root=None):
    """Return a review proposal without changing the source datastore."""
    data_dir = Path(data_dir).resolve()
    missing = [name for name in SOURCE_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Cannot create an ID proposal; required source files are missing: "
            + ", ".join(missing)
        )

    for filename in ("players.csv", "player_aliases.csv", "locations.csv", "location_aliases.csv"):
        if (data_dir / filename).exists():
            raise ValueError(
                f"ID proposal currently requires name-based source files; found {filename}."
            )

    initial_hashes = _source_hashes(data_dir)
    report = profile_data(data_dir, include_names=True, repo_root=repo_root)
    if any(not details["schema_valid"] for details in report["files"].values()):
        raise ValueError("Cannot create an ID proposal from invalid or missing CSV schemas.")

    roster = _read_roster(data_dir / "AllPlayers.csv")
    pool_names = {normalize_reference_name(name) for name in roster}
    player_groups = _collect_player_names(data_dir)
    location_groups = _collect_location_names(data_dir)
    used_ids = set()
    players, player_aliases = _build_entities(
        player_groups, "player", pool_names=pool_names, used_ids=used_ids
    )
    locations, location_aliases = _build_entities(
        location_groups, "location", used_ids=used_ids
    )

    final_hashes = _source_hashes(data_dir)
    if initial_hashes != final_hashes:
        raise RuntimeError("Source data changed while the ID proposal was being built.")

    proposal = {
        "proposal_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contains_personal_data": True,
        "source_hashes": initial_hashes,
        "data_quality": report["data_quality"],
        "review_summary": _review_summary(report),
        "players": players,
        "player_aliases": player_aliases,
        "locations": locations,
        "location_aliases": location_aliases,
        "approval": {
            "required": True,
            "status": "pending",
            "note": "Review privately; no apply command exists yet.",
        },
    }
    proposal["proposal_sha256"] = calculate_proposal_hash(proposal)
    return proposal


def write_id_proposal(data_dir, proposal_output, repo_root=None):
    """Write a proposal outside the source datastore without overwriting files."""
    data_dir = Path(data_dir).resolve()
    proposal_output = Path(proposal_output).resolve()
    if proposal_output == data_dir or data_dir in proposal_output.parents:
        raise ValueError("Proposal output must be outside the active data directory.")
    if proposal_output.exists():
        raise FileExistsError(f"Refusing to overwrite proposal: {proposal_output}")
    if not proposal_output.parent.is_dir():
        raise FileNotFoundError(
            f"Proposal output directory does not exist: {proposal_output.parent}"
        )

    proposal = build_id_proposal(data_dir, repo_root=repo_root)
    with proposal_output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n")
    return proposal


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a private, read-only proposal for Manillen ID migration."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="source datastore to inspect (default: configured MANILLEN_DATA_DIR)",
    )
    parser.add_argument(
        "--proposal-output",
        type=Path,
        required=True,
        help="new JSON proposal path outside the source datastore; never overwritten",
    )
    args = parser.parse_args(argv)
    proposal = write_id_proposal(args.data_dir, args.proposal_output)
    summary = proposal["review_summary"]
    print(
        "Private ID proposal created for "
        f"{len(proposal['players'])} players and {len(proposal['locations'])} locations; "
        f"{sum(summary.values())} review findings. No source data was changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
