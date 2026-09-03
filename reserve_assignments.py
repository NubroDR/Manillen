"""Date-bound reserve assignments for the writable NAS application."""

import csv
from datetime import date
from pathlib import Path

from mirror_app.data_helpers import load_pairing_history


DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_ASSIGNMENTS_FILE = DATA_DIR / "reserve_assignments.csv"
ASSIGNMENT_HEADERS = ("Date", "Slot", "Name")


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
        if not player.casefold().startswith("reserve ")
    }
    return (-len(participants)) % 4


def get_reserve_assignments(play_date, assignments_filename=DEFAULT_ASSIGNMENTS_FILE):
    """Return saved non-empty assignments as ``{"Reserve 1": "Name"}``."""
    selected_date = _date_value(play_date)
    path = Path(assignments_filename)
    if not path.exists():
        return {}
    assignments = {}
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("Date") != selected_date:
                continue
            slot = row.get("Slot", "").strip()
            name = row.get("Name", "").strip()
            if slot and name:
                assignments[slot] = name
    return assignments


def save_reserve_assignments(
    play_date,
    assignments,
    assignments_filename=DEFAULT_ASSIGNMENTS_FILE,
):
    """Replace all reserve assignments for one date and return the file path."""
    selected_date = _date_value(play_date)
    path = Path(assignments_filename)
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = [
                {header: row.get(header, "") for header in ASSIGNMENT_HEADERS}
                for row in csv.DictReader(file)
                if row.get("Date") != selected_date
            ]
    for slot, name in sorted(assignments.items()):
        clean_name = str(name).strip()
        if clean_name:
            rows.append({"Date": selected_date, "Slot": str(slot), "Name": clean_name})
    rows.sort(key=lambda row: (row["Date"], row["Slot"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=ASSIGNMENT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def delete_reserve_assignments(play_date, assignments_filename=DEFAULT_ASSIGNMENTS_FILE):
    """Delete all saved reserve assignments for one date."""
    return save_reserve_assignments(play_date, {}, assignments_filename)