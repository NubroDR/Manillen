import csv
import json
from itertools import combinations
from pathlib import Path

from mirror_app.data_helpers import load_pairing_counts
from mirror_app.score_helpers import compute_standings


PLAYERS = ("Alice", "Bob", "Casey", "Dana")
PAIRING_HEADER = ("Date", "Table", "Players", "Season", "Location")
SCORE_HEADER = (
    "Date",
    "Table",
    "Game",
    "Team1Players",
    "Team2Players",
    "Team1Score",
    "Team2Score",
)
EXPECTED_BASELINE = (
    Path(__file__).parent / "expected" / "phase0_baseline.json"
)


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_baseline_fixture(data_dir):
    history = data_dir / "pairings_history.csv"
    scores = data_dir / "scores_history.csv"
    pairings = data_dir / "pairings.csv"
    data_dir.mkdir()

    playdays = [
        ("2026-01-03", "season-alpha"),
        ("2026-02-07", "season-beta"),
    ]
    write_csv(history, PAIRING_HEADER, [
        {
            "Date": play_date,
            "Table": "1",
            "Players": " | ".join(PLAYERS),
            "Season": season,
            "Location": "Hall",
        }
        for play_date, season in playdays
    ])
    write_csv(scores, SCORE_HEADER, [
        {
            "Date": "2026-01-03",
            "Table": "1",
            "Game": "1",
            "Team1Players": "Alice | Bob",
            "Team2Players": "Casey | Dana",
            "Team1Score": "101",
            "Team2Score": "50",
        },
        {
            "Date": "2026-01-03",
            "Table": "1",
            "Game": "2",
            "Team1Players": "Alice | Casey",
            "Team2Players": "Bob | Dana",
            "Team1Score": "40",
            "Team2Score": "101",
        },
        {
            "Date": "2026-01-03",
            "Table": "1",
            "Game": "3",
            "Team1Players": "Alice | Dana",
            "Team2Players": "Bob | Casey",
            "Team1Score": "101",
            "Team2Score": "90",
        },
        {
            "Date": "2026-02-07",
            "Table": "1",
            "Game": "1",
            "Team1Players": "Alice | Bob",
            "Team2Players": "Casey | Dana",
            "Team1Score": "101",
            "Team2Score": "40",
        },
    ])
    expected_pairs = {
        tuple(sorted(pair)): 2
        for pair in combinations(PLAYERS, 2)
    }
    write_csv(pairings, ["Player1", "Player2", "Count"], [
        {"Player1": pair[0], "Player2": pair[1], "Count": count}
        for pair, count in sorted(expected_pairs.items())
    ])
    return history, scores, pairings, expected_pairs


def standings_values(rows):
    return [
        (
            row["player"],
            row["wins"],
            row["games_played"],
            row["point_diff"],
        )
        for row in rows
    ]


def load_expected_baseline():
    return json.loads(EXPECTED_BASELINE.read_text(encoding="utf-8"))


def test_baseline_standings_are_stable_per_season_and_playday(tmp_path):
    history, scores, _, _ = make_baseline_fixture(tmp_path / "fixture")
    expected = load_expected_baseline()

    alpha = compute_standings(
        scores,
        season="season-alpha",
        history_filename=history,
    )
    alpha_again = compute_standings(
        scores,
        season="season-alpha",
        history_filename=history,
    )
    beta = compute_standings(
        scores,
        season="season-beta",
        history_filename=history,
    )
    alpha_playday = compute_standings(scores, play_date="2026-01-03")
    beta_playday = compute_standings(scores, play_date="2026-02-07")
    legacy_without_scores = compute_standings(
        scores,
        season="legacy-season",
        history_filename=history,
    )

    assert standings_values(alpha) == [tuple(row) for row in expected["seasons"]["season-alpha"]]
    assert standings_values(alpha_again) == standings_values(alpha)
    assert standings_values(beta) == [tuple(row) for row in expected["seasons"]["season-beta"]]
    assert standings_values(alpha_playday) == [
        tuple(row) for row in expected["playdays"]["2026-01-03"]
    ]
    assert standings_values(beta_playday) == [
        tuple(row) for row in expected["playdays"]["2026-02-07"]
    ]
    assert standings_values(legacy_without_scores) == expected["seasons"]["legacy-season"]


def test_baseline_partner_counts_are_normalized_and_stable(tmp_path):
    _, _, pairings, _ = make_baseline_fixture(tmp_path / "fixture")

    counts = {
        tuple(sorted((player1.casefold(), player2.casefold()))): count
        for player1, player2, count in load_pairing_counts(pairings)
    }

    assert [
        [player1, player2, count]
        for (player1, player2), count in sorted(counts.items())
    ] == load_expected_baseline()["partner_counts"]
