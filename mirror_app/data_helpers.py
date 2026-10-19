"""Pure CSV readers shared by the NAS app and the read-only mirror."""

import csv
from collections import defaultdict
from pathlib import Path


DEFAULT_SEASON = "2026-2027"


def load_pairing_records(history_filename):
    """Return valid history rows with their date, table, players, and season."""
    path = Path(history_filename)
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            play_date = row.get("Date", "").strip()
            players = [name.strip() for name in row.get("Players", "").split("|")]
            try:
                table = int(row.get("Table", ""))
            except (TypeError, ValueError):
                continue
            if not play_date or len(players) != 4:
                continue
            records.append({
                "Date": play_date,
                "Table": table,
                "Players": players,
                "Season": (row.get("Season") or "").strip() or DEFAULT_SEASON,
                "Location": (row.get("Location") or "").strip(),
            })
    return records


def load_pairing_locations(history_filename):
    """Return the non-empty location recorded for each playday."""
    locations = {}
    for row in load_pairing_records(history_filename):
        if row["Location"]:
            locations.setdefault(row["Date"], row["Location"])
    return locations


def load_all_players(players_filename):
    path = Path(players_filename)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return [
            row[0].strip()
            for row in csv.reader(file)
            if row and row[0].strip()
        ]


def load_pairing_history(history_filename):
    """Return history grouped by date as ``{date: [(table, players), ...]}``."""
    grouped = defaultdict(list)
    for row in load_pairing_records(history_filename):
        grouped[row["Date"]].append((row["Table"], row["Players"]))
    return {
        play_date: sorted(tables, key=lambda item: item[0])
        for play_date, tables in grouped.items()
    }


def load_pairing_counts(pairings_filename):
    """Return valid pairing rows as ``[(player1, player2, count), ...]``."""
    path = Path(pairings_filename)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            try:
                count = int(row.get("Count", 0))
            except (TypeError, ValueError):
                continue
            player1 = row.get("Player1", "").strip()
            player2 = row.get("Player2", "").strip()
            if player1 and player2 and count >= 0:
                rows.append((player1, player2, count))
    return rows


def load_reserve_assignments(assignments_filename):
    """Return saved reserve names grouped by date and reserve slot."""
    path = Path(assignments_filename)
    if not path.exists():
        return {}
    assignments = defaultdict(dict)
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            play_date = row.get("Date", "").strip()
            slot = row.get("Slot", "").strip()
            name = row.get("Name", "").strip()
            if play_date and slot and name:
                assignments[play_date][slot] = name
    return dict(assignments)