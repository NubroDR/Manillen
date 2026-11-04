"""Resolve canonical IDs to display names at the writable app boundary."""

import csv
import re
from pathlib import Path

from data_paths import DATA_DIR, active_data_dir, validate_active_data
from manillen_core.reference_helpers import (
    normalize_reference_name,
    reserve_reference_token,
)


def _read_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _read_legacy_players(path):
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        return [
            row[0].strip()
            for row in csv.reader(file)
            if row and row[0].strip()
        ]


class ReferenceAdapter:
    """Translate display names and reserve labels to stable stored references.

    With no active ID version, values pass through unchanged so existing
    name-based app behavior remains available until an approved activation.
    """

    def __init__(self, data_root=DATA_DIR):
        self.data_root = Path(data_root).resolve()
        self.data_dir = active_data_dir(self.data_root)
        self.is_versioned = self.data_dir != self.data_root
        self._player_names = {}
        self._player_ids_by_name = {}
        self._location_names = {}
        self._location_ids_by_name = {}
        self._active_players = []
        self._pool = []

        if not self.is_versioned:
            players_path = self.data_root / "AllPlayers.csv"
            self._pool = (
                _read_legacy_players(players_path)
                if players_path.exists() else []
            )
            self._active_players = list(self._pool)
            return

        validate_active_data(self.data_root)
        players = _read_rows(self.data_dir / "players.csv")
        for row in players:
            player_id = row["PlayerID"]
            name = row["Name"].strip()
            self._player_names[player_id] = name
            self._player_ids_by_name[normalize_reference_name(name)] = player_id
            if row["Active"] == "1":
                self._active_players.append(name)
                if row["PoolMember"] == "1":
                    self._pool.append(name)
        for row in _read_rows(self.data_dir / "player_aliases.csv"):
            self._player_ids_by_name[
                normalize_reference_name(row["Alias"])
            ] = row["PlayerID"]

        locations = _read_rows(self.data_dir / "locations.csv")
        for row in locations:
            location_id = row["LocationID"]
            name = row["Name"].strip()
            self._location_names[location_id] = name
            self._location_ids_by_name[normalize_reference_name(name)] = location_id
        for row in _read_rows(self.data_dir / "location_aliases.csv"):
            self._location_ids_by_name[
                normalize_reference_name(row["Alias"])
            ] = row["LocationID"]

    @classmethod
    def for_data_file(cls, filename):
        """Create an adapter for a datastore file in its root or active version."""
        directory = Path(filename).resolve().parent
        if directory.parent.name == "versions":
            directory = directory.parent.parent
        return cls(directory)

    @staticmethod
    def _reserve_reference(value):
        return reserve_reference_token(value)

    def player_id(self, name):
        """Resolve a displayed player name or reserve label to its stored token."""
        value = str(name or "").strip()
        if not value:
            raise ValueError("Player name must not be empty.")
        reserve = self._reserve_reference(value)
        if reserve:
            return reserve if self.is_versioned else f"Reserve {reserve.split(':', 1)[1]}"
        if not self.is_versioned:
            return value
        if value in self._player_names:
            return value
        player_id = self._player_ids_by_name.get(normalize_reference_name(value))
        if player_id is None:
            raise ValueError(f"Unknown player name or alias: {value}")
        return player_id

    def find_player_id(self, name):
        """Return a known player's ID, or None for an unregistered historical name."""
        value = str(name or "").strip()
        if not value or self._reserve_reference(value):
            return None
        if not self.is_versioned:
            return value
        if value in self._player_names:
            return value
        return self._player_ids_by_name.get(normalize_reference_name(value))

    def player_name(self, reference):
        """Resolve a stored player ID or reserve token to a display label."""
        value = str(reference or "").strip()
        if not value:
            raise ValueError("Player reference must not be empty.")
        reserve = self._reserve_reference(value)
        if reserve:
            return f"Reserve {int(reserve.split(':', 1)[1])}"
        if not self.is_versioned:
            return value
        try:
            return self._player_names[value]
        except KeyError as error:
            raise ValueError(f"Unknown player ID: {value}") from error

    def location_id(self, name):
        """Resolve a displayed location name or alias to its stored value."""
        value = str(name or "").strip()
        if not value:
            return ""
        if not self.is_versioned:
            return value
        if value in self._location_names:
            return value
        location_id = self._location_ids_by_name.get(normalize_reference_name(value))
        if location_id is None:
            raise ValueError(f"Unknown location name or alias: {value}")
        return location_id

    def location_name(self, reference):
        """Resolve a stored location ID to its display name."""
        value = str(reference or "").strip()
        if not value:
            return ""
        if not self.is_versioned:
            return value
        try:
            return self._location_names[value]
        except KeyError as error:
            raise ValueError(f"Unknown location ID: {value}") from error

    def player_pool(self):
        """Return the active scheduling pool as display names."""
        return list(self._pool)

    def active_players(self):
        """Return all active player names, including non-pool players."""
        return list(self._active_players)

    def player_tokens(self, value):
        """Translate a pipe-delimited display-name list to stored references."""
        return " | ".join(self.player_id(token) for token in str(value).split("|"))

    def player_names(self, value):
        """Translate pipe-delimited stored references to display names."""
        return " | ".join(self.player_name(token) for token in str(value).split("|"))
