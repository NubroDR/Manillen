"""Pure score loading and standings logic shared with the NAS app."""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


DEFAULT_SCORES_FILE = Path(__file__).resolve().parent / "data" / "scores_history.csv"


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
            rows.append(row)
    return rows


def compute_standings(scores_filename=str(DEFAULT_SCORES_FILE), play_date=None):
    standings = defaultdict(lambda: {"games_played": 0, "wins": 0, "points_for": 0, "points_against": 0})
    for row in load_scores(scores_filename, play_date):
        team1 = [name.strip() for name in row["Team1Players"].split("|") if name.strip()]
        team2 = [name.strip() for name in row["Team2Players"].split("|") if name.strip()]
        if len(team1) != 2 or len(team2) != 2:
            continue
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