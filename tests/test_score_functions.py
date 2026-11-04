import csv

import pytest

from score_functions import compute_standings, save_game_score, save_game_scores, save_scores


HEADER = [
    "Date",
    "Table",
    "Game",
    "Team1Players",
    "Team2Players",
    "Team1Score",
    "Team2Score",
]


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_game_save_allows_partial_day_and_preserves_other_games(tmp_path):
    path = tmp_path / "scores.csv"
    save_game_score("2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"], 101, 20, path)
    save_game_score("2026-09-19", 1, 3, ["An", "Etienne"], ["Bruno", "Freddy"], 40, 101, path)
    assert [row["Game"] for row in read_rows(path)] == ["1", "3"]


def test_game_save_is_idempotent_and_edit_replaces_only_same_game(tmp_path):
    path = tmp_path / "scores.csv"
    args = ("2026-09-19", 1, 2, ["An", "Bruno"], ["Etienne", "Freddy"])
    save_game_score(*args, 101, 20, path)
    save_game_score(*args, 101, 20, path)
    save_game_score(*args, 30, 101, path)
    rows = read_rows(path)
    assert len(rows) == 1
    assert rows[0]["Team1Score"] == "30"
    assert rows[0]["Team2Score"] == "101"


def test_batch_game_save_replaces_submitted_games_and_preserves_others(tmp_path):
    path = tmp_path / "scores.csv"
    save_game_score("2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"], 101, 20, path)
    save_game_score("2026-09-19", 1, 2, ["An", "Etienne"], ["Bruno", "Freddy"], 101, 20, path)
    save_game_scores("2026-09-19", [{
        "table": 1,
        "game": 1,
        "team1": ["An", "Bruno"],
        "team2": ["Etienne", "Freddy"],
        "team1_score": 30,
        "team2_score": 101,
    }], path)

    rows = read_rows(path)

    assert [(row["Game"], row["Team1Score"]) for row in rows] == [
        ("1", "30"),
        ("2", "101"),
    ]


def test_batch_game_save_validates_every_game_before_writing(tmp_path):
    path = tmp_path / "scores.csv"
    valid_game = {
        "table": 1,
        "game": 1,
        "team1": ["An", "Bruno"],
        "team2": ["Etienne", "Freddy"],
        "team1_score": 101,
        "team2_score": 20,
    }
    invalid_game = {**valid_game, "game": 2, "team1_score": -1}

    with pytest.raises(ValueError):
        save_game_scores("2026-09-19", [valid_game, invalid_game], path)

    assert not path.exists()


def test_equal_scores_are_rejected_without_changing_existing_scores(tmp_path):
    path = tmp_path / "scores.csv"
    save_game_score(
        "2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"], 101, 20, path,
    )
    before = path.read_bytes()

    with pytest.raises(ValueError, match="scores must not be equal"):
        save_game_score(
            "2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"], 80, 80, path,
        )

    assert path.read_bytes() == before


def test_save_scores_rejects_equal_scores_before_replacing_table(tmp_path):
    path = tmp_path / "scores.csv"
    save_game_score(
        "2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"], 101, 20, path,
    )
    before = path.read_bytes()

    with pytest.raises(ValueError, match="scores must not be equal"):
        save_scores("2026-09-19", 1, [
            {
                "team1": ["An", "Bruno"], "team2": ["Etienne", "Freddy"],
                "team1_score": 101, "team2_score": 20,
            },
            {
                "team1": ["An", "Etienne"], "team2": ["Bruno", "Freddy"],
                "team1_score": 75, "team2_score": 75,
            },
            {
                "team1": ["An", "Freddy"], "team2": ["Bruno", "Etienne"],
                "team1_score": 80, "team2_score": 101,
            },
        ], path)

    assert path.read_bytes() == before


def test_historical_equal_scores_are_excluded_from_standings_without_modification(tmp_path):
    path = tmp_path / "scores.csv"
    path.write_text(
        ",".join(HEADER) + "\n"
        "2026-09-19,1,1,An | Bruno,Etienne | Freddy,80,80\n"
        "2026-09-19,1,2,An | Etienne,Bruno | Freddy,101,20\n",
        encoding="utf-8",
    )
    before = path.read_bytes()

    standings = compute_standings(path, play_date="2026-09-19")
    by_player = {row["player"]: row for row in standings}

    assert {player: row["games_played"] for player, row in by_player.items()} == {
        "An": 1, "Bruno": 1, "Etienne": 1, "Freddy": 1,
    }
    assert {player: row["wins"] for player, row in by_player.items()} == {
        "An": 1, "Bruno": 0, "Etienne": 1, "Freddy": 0,
    }
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "scores",
    [(None, 20), (-1, 20), (1.5, 20), (True, 20)],
)
def test_game_save_rejects_invalid_scores(tmp_path, scores):
    with pytest.raises(ValueError):
        save_game_score(
            "2026-09-19", 1, 1, ["An", "Bruno"], ["Etienne", "Freddy"],
            scores[0], scores[1], tmp_path / "scores.csv",
        )
