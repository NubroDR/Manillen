import csv
from datetime import date
from pathlib import Path

from data_paths import DATA_DIR
from mirror_app.score_helpers import (
    compute_standings as _compute_standings,
    load_scores as _load_scores,
)


def load_scores(scores_filename=str(DATA_DIR / "scores_history.csv"), play_date=None):
    return _load_scores(scores_filename, play_date)


def compute_standings(
    scores_filename=str(DATA_DIR / "scores_history.csv"),
    play_date=None,
    season=None,
    history_filename=None,
    reserve_assignments_filename=None,
):
    return _compute_standings(
        scores_filename,
        play_date,
        season=season,
        history_filename=history_filename,
        reserve_assignments_filename=reserve_assignments_filename,
    )


SCORES_HEADER = [
    "Date",
    "Table",
    "Game",
    "Team1Players",
    "Team2Players",
    "Team1Score",
    "Team2Score",
]


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


def get_matchups_for_table(players):
    """Return the three 2v2 matchups used by the scoreblad workflow."""
    if not isinstance(players, (list, tuple)) or len(players) != 4:
        raise ValueError("players must contain exactly 4 names")
    a, b, c, d = [str(player) for player in players]
    return [
        ((a, b), (c, d)),
        ((a, c), (b, d)),
        ((a, d), (b, c)),
    ]


def _team_value(team):
    if isinstance(team, str):
        return team
    return " | ".join(str(player) for player in team)


def _score_value(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("scores must be non-negative integers")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("scores must be non-negative integers") from error
    if number < 0 or str(value).strip() != str(number):
        raise ValueError("scores must be non-negative integers")
    return number


def save_scores(play_date, table, game_scores, scores_filename=str(DATA_DIR / "scores_history.csv")):
    """Replace all scores for one date and table, then write the CSV."""
    play_date = _score_date(play_date)
    try:
        table = int(table)
    except (TypeError, ValueError) as error:
        raise ValueError("table must be an integer") from error
    if table < 1:
        raise ValueError("table must be positive")
    if not isinstance(game_scores, (list, tuple)) or len(game_scores) != 3:
        raise ValueError("game_scores must contain exactly 3 games")

    new_rows = []
    for game, score in enumerate(game_scores, start=1):
        if not isinstance(score, dict):
            raise ValueError("each game score must be a dictionary")
        team1_score = _score_value(score.get("team1_score"))
        team2_score = _score_value(score.get("team2_score"))
        if not score.get("team1") or not score.get("team2"):
            raise ValueError("each game must contain both teams")
        new_rows.append({
            "Date": play_date,
            "Table": str(table),
            "Game": str(game),
            "Team1Players": _team_value(score["team1"]),
            "Team2Players": _team_value(score["team2"]),
            "Team1Score": str(team1_score),
            "Team2Score": str(team2_score),
        })

    path = Path(scores_filename)
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                if row.get("Date") == play_date and row.get("Table") == str(table):
                    continue
                rows.append({header: row.get(header, "") for header in SCORES_HEADER})
    rows.extend(new_rows)
    rows.sort(key=lambda row: (row["Date"], int(row["Table"]), int(row["Game"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SCORES_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    return str(path)


def save_game_score(
    play_date,
    table,
    game,
    team1,
    team2,
    team1_score,
    team2_score,
    scores_filename=str(DATA_DIR / "scores_history.csv"),
):
    """Insert or replace the score for one game without touching other games."""
    play_date = _score_date(play_date)
    try:
        table_number = int(table)
        game_number = int(game)
    except (TypeError, ValueError) as error:
        raise ValueError("table and game must be integers") from error
    if table_number < 1:
        raise ValueError("table must be positive")
    if game_number not in (1, 2, 3):
        raise ValueError("game must be between 1 and 3")
    if not team1 or not team2:
        raise ValueError("each game must contain both teams")

    new_row = {
        "Date": play_date,
        "Table": str(table_number),
        "Game": str(game_number),
        "Team1Players": _team_value(team1),
        "Team2Players": _team_value(team2),
        "Team1Score": str(_score_value(team1_score)),
        "Team2Score": str(_score_value(team2_score)),
    }
    path = Path(scores_filename)
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = [
                {header: row.get(header, "") for header in SCORES_HEADER}
                for row in csv.DictReader(file)
                if not (
                    row.get("Date") == play_date
                    and row.get("Table") == str(table_number)
                    and row.get("Game") == str(game_number)
                )
            ]
    rows.append(new_row)
    rows.sort(key=lambda row: (row["Date"], int(row["Table"]), int(row["Game"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SCORES_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)
