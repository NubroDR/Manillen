import csv

import pytest

from score_functions import save_game_score


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
