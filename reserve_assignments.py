"""Date-bound reserve assignments for the writable NAS application."""

import csv
from datetime import date
from pathlib import Path

from data_paths import DATA_DIR
from manillen_core.data_helpers import load_pairing_history
from manillen_core.reference_adapter import ReferenceAdapter
from manillen_core.reference_helpers import (
    is_reserve_reference,
    reserve_reference_token,
)


DEFAULT_ASSIGNMENTS_FILE = DATA_DIR / "reserve_assignments.csv"
ASSIGNMENT_HEADERS = ("Date", "Slot", "Name")


def reserve_name_matches_pool(name, pool_players):
    """Return whether a proposed reserve label duplicates a pool player's name."""
    candidate = str(name).strip().casefold()
    return bool(candidate) and any(
        candidate == str(player).strip().casefold()
        for player in pool_players
    )


def resolve_reserve_name(player, assignments):
    """Resolve a reserve slot to its entered name, preserving unknown slots."""
    if is_reserve_reference(player):
        slot = reserve_reference_token(player)
        number = slot.split(":", 1)[1]
        return assignments.get(player, assignments.get(
            slot, assignments.get(f"Reserve {number}", player)
        ))
    return player


def _date_value(play_date):
    if isinstance(play_date, date):
        return play_date.isoformat()
    if isinstance(play_date, str) and play_date.strip():
        return date.fromisoformat(play_date.strip()).isoformat()
    raise ValueError("play_date must be a date or string in YYYY-MM-DD format")


def required_reserve_count(play_date, history_filename):
    """Return the number of reserve slots needed for one saved play date."""
    tables = load_pairing_history(history_filename).get(_date_value(play_date), [])
    participants = {
        player
        for _, players in tables
        for player in players
        if not is_reserve_reference(player)
    }
    return (-len(participants)) % 4


def get_reserve_assignments(play_date, assignments_filename=DEFAULT_ASSIGNMENTS_FILE):
    """Return saved non-empty assignments as ``{"Reserve 1": "Name"}``."""
    selected_date = _date_value(play_date)
    path = Path(assignments_filename)
    if not path.exists():
        return {}
    adapter = ReferenceAdapter.for_data_file(path)
    assignments = {}
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("Date") != selected_date:
                continue
            slot = row.get("Slot", "").strip()
            reference = (row.get("PlayerID") or row.get("Name") or "").strip()
            if slot and reference:
                reserve_slot = reserve_reference_token(slot)
                display_slot = (
                    f"Reserve {reserve_slot.split(':', 1)[1]}"
                    if reserve_slot else slot
                )
                assignments[display_slot] = adapter.player_name(reference)
    return assignments


def save_reserve_assignments(
    play_date,
    assignments,
    assignments_filename=DEFAULT_ASSIGNMENTS_FILE,
):
    """Replace all reserve assignments for one date and return the file path."""
    selected_date = _date_value(play_date)
    path = Path(assignments_filename)
    adapter = ReferenceAdapter.for_data_file(path)
    headers = ("Date", "Slot", "PlayerID") if adapter.is_versioned else ASSIGNMENT_HEADERS
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = [
                {header: row.get(header, "") for header in headers}
                for row in csv.DictReader(file)
                if row.get("Date") != selected_date
            ]
    for slot, name in sorted(assignments.items()):
        clean_name = str(name).strip()
        if clean_name:
            stored_slot = adapter.player_id(slot) if adapter.is_versioned else str(slot)
            stored_player = adapter.player_id(clean_name)
            value_column = "PlayerID" if adapter.is_versioned else "Name"
            rows.append({
                "Date": selected_date,
                "Slot": stored_slot,
                value_column: stored_player,
            })
    rows.sort(key=lambda row: (row["Date"], row["Slot"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def delete_reserve_assignments(play_date, assignments_filename=DEFAULT_ASSIGNMENTS_FILE):
    """Delete all saved reserve assignments for one date."""
    return save_reserve_assignments(play_date, {}, assignments_filename)