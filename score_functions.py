import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


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


def save_scores(play_date, table, game_scores, scores_filename="scores_history.csv"):
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


def load_scores(scores_filename="scores_history.csv", play_date=None):
    """Load score rows, optionally limited to one ISO date."""
    selected_date = _score_date(play_date) if play_date is not None else None
    path = Path(scores_filename)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = []
        for row in csv.DictReader(file):
            if selected_date is not None and row.get("Date") != selected_date:
                continue
            try:
                row["Table"] = int(row["Table"])
                row["Game"] = int(row["Game"])
                row["Team1Score"] = int(row["Team1Score"])
                row["Team2Score"] = int(row["Team2Score"])
            except (TypeError, ValueError):
                continue
            rows.append(row)
    return rows


def compute_standings(scores_filename="scores_history.csv", play_date=None):
    """Compute sorted individual standings from saved 2v2 scores."""
    standings = defaultdict(lambda: {
        "games_played": 0, "wins": 0, "points_for": 0, "points_against": 0,
    })
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

    result = []
    for player, values in standings.items():
        result.append({
            "player": player,
            **values,
            "point_diff": values["points_for"] - values["points_against"],
        })
    return sorted(result, key=lambda row: (-row["wins"], -row["games_played"], -row["point_diff"], row["player"].casefold()))
