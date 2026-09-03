"""Pure CSV readers shared by the NAS app and the read-only mirror."""

import csv
from collections import defaultdict
from pathlib import Path


def load_pairing_history(history_filename):
    """Return history grouped by date as ``{date: [(table, players), ...]}``."""
    grouped = defaultdict(list)
    path = Path(history_filename)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            players = [name.strip() for name in row.get("Players", "").split("|")]
            if len(players) != 4 or not row.get("Date"):
                continue
            try:
                table = int(row.get("Table", ""))
            except (TypeError, ValueError):
                continue
            grouped[row["Date"].strip()].append((table, players))
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