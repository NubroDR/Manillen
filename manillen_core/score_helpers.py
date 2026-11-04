"""Pure score loading and standings logic shared with the NAS app."""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from manillen_core.reference_adapter import ReferenceAdapter

try:
    from .data_helpers import load_pairing_records, load_reserve_assignments
except ImportError:
    from data_helpers import load_pairing_records, load_reserve_assignments

try:
    from .reference_helpers import reserve_reference_token
except ImportError:
    from reference_helpers import reserve_reference_token

DEFAULT_SCORES_FILE = Path(__file__).resolve().parent / "data" / "scores_history.csv"


def is_valid_game_score(team1_score, team2_score):
    return team1_score != team2_score


def _score_date(play_date):
    if play_date is None:
        return date.today().isoformat()
    if isinstance(play_date, date):
        return play_date.isoformat()
    if isinstance(play_date, str):
        try:
            return date.fromisoformat(play_date).isoformat()
        except ValueError:
            pass
        if len(play_date) == 8 and play_date.isdigit():
            return f"{play_date[:4]}-{play_date[4:6]}-{play_date[6:]}"
    raise ValueError("play_date must be a date or string in YYYY-MM-DD / YYYYMMDD format")


def load_scores(scores_filename=str(DEFAULT_SCORES_FILE), play_date=None):
    selected_date = _score_date(play_date) if play_date is not None else None
    path = Path(scores_filename)
    if not path.exists():
        return []
    adapter = ReferenceAdapter.for_data_file(path)
    rows = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if selected_date is not None and row.get("Date") != selected_date:
                continue
            try:
                row["Table"] = int(row["Table"])
                row["Game"] = int(row["Game"])
                row["Team1Score"] = int(row["Team1Score"])
                row["Team2Score"] = int(row["Team2Score"])
            except (TypeError, ValueError, KeyError):
                continue
            row["Team1Players"] = adapter.player_names(row["Team1Players"])
            row["Team2Players"] = adapter.player_names(row["Team2Players"])
            rows.append(row)
    return rows


def compute_standings(
    scores_filename=str(DEFAULT_SCORES_FILE),
    play_date=None,
    season=None,
    history_filename=None,
    reserve_assignments_filename=None,
    table_number=None,
):
    selected_date = _score_date(play_date) if play_date is not None else None
    scores = load_scores(scores_filename, selected_date)
    if table_number is not None:
        scores = [row for row in scores if row["Table"] == table_number]
    if season is not None:
        if history_filename is None:
            raise ValueError("history_filename is required when filtering by season")
        season_dates = {
            row["Date"]
            for row in load_pairing_records(history_filename)
            if row["Season"] == season
        }
        scores = [row for row in scores if row["Date"] in season_dates]

    assignments = {}
    if reserve_assignments_filename is not None:
        assignments = load_reserve_assignments(reserve_assignments_filename)
        adapter = ReferenceAdapter.for_data_file(scores_filename)
        assignments = {
            playday: {
                slot: adapter.player_name(reference)
                for slot, reference in playday_assignments.items()
            }
            for playday, playday_assignments in assignments.items()
        }

    standings = defaultdict(lambda: {"games_played": 0, "wins": 0, "points_for": 0, "points_against": 0})
    for row in scores:
        if not is_valid_game_score(row["Team1Score"], row["Team2Score"]):
            continue
        team1 = [name.strip() for name in row["Team1Players"].split("|") if name.strip()]
        team2 = [name.strip() for name in row["Team2Players"].split("|") if name.strip()]
        if len(team1) != 2 or len(team2) != 2:
            continue
        reserve_names = assignments.get(row["Date"], {})
        def assigned_player(name):
            slot = reserve_reference_token(name)
            if slot is None:
                return name
            number = slot.split(":", 1)[1]
            assigned = (
                reserve_names.get(name)
                or reserve_names.get(slot)
                or reserve_names.get(f"Reserve {number}")
                or name
            )
            return f"{assigned}*"

        team1 = [assigned_player(name) for name in team1]
        team2 = [assigned_player(name) for name in team2]
        scores = (row["Team1Score"], row["Team2Score"])
        for team_index, team in enumerate((team1, team2)):
            points_for, points_against = scores[team_index], scores[1 - team_index]
            for player in team:
                item = standings[player]
                item["games_played"] += 1
                item["wins"] += int(points_for > points_against)
                item["points_for"] += points_for
                item["points_against"] += points_against
    return sorted([
        {"player": player, **values, "point_diff": values["points_for"] - values["points_against"]}
        for player, values in standings.items()
    ], key=lambda row: (-row["wins"], -row["games_played"], -row["point_diff"], row["player"].casefold()))