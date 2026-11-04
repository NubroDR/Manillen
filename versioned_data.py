"""Schema and referential-integrity checks for versioned ID-based datasets."""

import csv
import hashlib
import re
from pathlib import Path

from manillen_core.reference_helpers import ID_ALPHABET, normalize_reference_name


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
_PLAYER_ID = re.compile(rf"^plr_[{re.escape(ID_ALPHABET)}]{{5}}$")
_LOCATION_ID = re.compile(rf"^loc_[{re.escape(ID_ALPHABET)}]{{5}}$")
_RESERVE = re.compile(r"^RESERVE:([1-9]\d*)$")


def _read_csv(directory, filename):
    path = Path(directory) / filename
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != VERSIONED_SCHEMAS[filename]:
            raise ValueError(f"Unexpected schema in {filename}.")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV row in {filename}.")
    return rows


def _parse_ids(rows, column, pattern, entity):
    ids = set()
    normalized_names = {}
    for row_number, row in enumerate(rows, start=2):
        reference_id = row[column]
        name = row["Name"].strip()
        if not pattern.fullmatch(reference_id) or reference_id in ids or not name:
            raise ValueError(f"Invalid or duplicate {entity} in row {row_number}.")
        ids.add(reference_id)
        normalized = normalize_reference_name(name)
        previous = normalized_names.get(normalized)
        if previous is not None and previous != reference_id:
            raise ValueError(f"Ambiguous normalized {entity} name in row {row_number}.")
        normalized_names[normalized] = reference_id
    return ids, normalized_names


def _parse_aliases(rows, column, valid_ids, lookup, entity):
    for row_number, row in enumerate(rows, start=2):
        alias = row["Alias"].strip()
        target = row[column]
        normalized = normalize_reference_name(alias)
        if not alias or target not in valid_ids:
            raise ValueError(f"Invalid {entity} alias in row {row_number}.")
        existing = lookup.get(normalized)
        if existing is not None and existing != target:
            raise ValueError(f"Conflicting {entity} alias in row {row_number}.")
        lookup[normalized] = target


def _map_tokens(value, count, player_ids, context):
    tokens = [token.strip() for token in value.split("|")]
    if len(tokens) != count or any(not token for token in tokens):
        raise ValueError(f"Invalid player-token count in {context}.")
    if len(set(tokens)) != len(tokens):
        raise ValueError(f"Duplicate player token in {context}.")
    for token in tokens:
        if token in player_ids:
            continue
        if not _RESERVE.fullmatch(token):
            raise ValueError(f"Unknown player reference in {context}.")
    return tokens


def validate_version_directory(directory):
    """Validate all schemas, IDs, references, and row-level invariants."""
    directory = Path(directory).resolve()
    rows = {
        filename: _read_csv(directory, filename)
        for filename in VERSIONED_SCHEMAS
    }

    player_ids, player_names = _parse_ids(
        rows["players.csv"], "PlayerID", _PLAYER_ID, "player"
    )
    location_ids, location_names = _parse_ids(
        rows["locations.csv"], "LocationID", _LOCATION_ID, "location"
    )
    for row_number, row in enumerate(rows["players.csv"], start=2):
        if row["PoolMember"] not in ("0", "1") or row["Active"] not in ("0", "1"):
            raise ValueError(f"Invalid player status in row {row_number}.")
    for row_number, row in enumerate(rows["locations.csv"], start=2):
        if row["Active"] not in ("0", "1"):
            raise ValueError(f"Invalid location status in row {row_number}.")
    _parse_aliases(
        rows["player_aliases.csv"], "PlayerID", player_ids, player_names, "player"
    )
    _parse_aliases(
        rows["location_aliases.csv"],
        "LocationID",
        location_ids,
        location_names,
        "location",
    )

    pairings = set()
    for row_number, row in enumerate(rows["pairings.csv"], start=2):
        first, second = row["Player1"], row["Player2"]
        pair = tuple(sorted((first, second)))
        try:
            count = int(row["Count"])
        except ValueError as error:
            raise ValueError(f"Invalid pair count in row {row_number}.") from error
        if (
            first not in player_ids or second not in player_ids or first == second
            or count < 0 or str(count) != row["Count"].strip()
            or pair in pairings
        ):
            raise ValueError(f"Invalid or duplicate pair in row {row_number}.")
        pairings.add(pair)

    tables_by_date = {}
    table_keys = set()
    reserve_slots = {}
    for row_number, row in enumerate(rows["pairings_history.csv"], start=2):
        table_key = (row["Date"], row["Table"])
        tables = tables_by_date.setdefault(row["Date"], set())
        if not all(row[field].strip() for field in ("Date", "Table", "Season")):
            raise ValueError(f"Missing playday field in pairing row {row_number}.")
        if table_key in tables:
            raise ValueError(f"Duplicate table in pairing row {row_number}.")
        tables.add(table_key)
        table_keys.add(table_key)
        tokens = _map_tokens(
            row["Players"], 4, player_ids, f"pairings_history.csv row {row_number}"
        )
        table_reserves = [token for token in tokens if token.startswith("RESERVE:")]
        if len(table_reserves) > 1:
            raise ValueError(f"More than one reserve in pairing row {row_number}.")
        reserve_slots.setdefault(row["Date"], []).extend(
            int(_RESERVE.fullmatch(token).group(1)) for token in table_reserves
        )
        if row["Location"] and row["Location"] not in location_ids:
            raise ValueError(f"Unknown location in pairing row {row_number}.")
    for playday, slots in reserve_slots.items():
        if any(slot > len(tables_by_date[playday]) for slot in slots):
            raise ValueError(f"Reserve slot exceeds table count on {playday}.")
    known_slots = {
        (playday, f"RESERVE:{slot}")
        for playday, slots in reserve_slots.items()
        for slot in slots
    }

    for row_number, row in enumerate(rows["scores_history.csv"], start=2):
        context = f"scores_history.csv row {row_number}"
        if (row["Date"], row["Table"]) not in table_keys:
            raise ValueError(f"Score row has no matching table in row {row_number}.")
        for column in ("Team1Players", "Team2Players"):
            tokens = _map_tokens(row[column], 2, player_ids, context)
            if any(
                token.startswith("RESERVE:")
                and (row["Date"], token) not in known_slots
                for token in tokens
            ):
                raise ValueError(f"Score uses an unassigned reserve slot in {context}.")
        for column in ("Team1Score", "Team2Score"):
            try:
                score = int(row[column])
            except ValueError as error:
                raise ValueError(f"Invalid score in {context}.") from error
            if score < 0 or str(score) != row[column].strip():
                raise ValueError(f"Invalid score in {context}.")

    seen_assignments = set()
    for row_number, row in enumerate(rows["reserve_assignments.csv"], start=2):
        key = (row["Date"], row["Slot"])
        if (
            key not in known_slots or key in seen_assignments
            or row["PlayerID"] not in player_ids
        ):
            raise ValueError(f"Invalid reserve assignment in row {row_number}.")
        seen_assignments.add(key)

    for row_number, row in enumerate(rows["seasons.csv"], start=2):
        if not all(row[field].strip() for field in VERSIONED_SCHEMAS["seasons.csv"]):
            raise ValueError(f"Missing season field in row {row_number}.")
        try:
            int(row["SeasonNumber"])
            int(row["SeasonStartYear"])
        except ValueError as error:
            raise ValueError(f"Invalid season numbers in row {row_number}.") from error

    return {
        filename: hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        for filename in VERSIONED_SCHEMAS
    }
