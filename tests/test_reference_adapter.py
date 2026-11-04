import csv
import json

import pytest

from data_paths import VERSIONED_FILES
from manillen_functions import (
    _load_pairings_history,
    load_all_players,
    load_pair_counts,
    update_pairs_in_csv,
)
from manillen_core.reference_adapter import ReferenceAdapter
from manillen_core.data_helpers import load_reserve_assignments
from reserve_assignments import get_reserve_assignments, save_reserve_assignments
from score_functions import compute_standings, load_scores, save_game_score
from versioned_data import VERSIONED_SCHEMAS


def _write_csv(path, headers, rows=()):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _activate_version(data_root):
    version_id = "v_test123"
    version_dir = data_root / "versions" / version_id
    version_dir.mkdir(parents=True)
    rows = {
        "players.csv": [
            {"PlayerID": "plr_abcde", "Name": "An", "PoolMember": "1", "Active": "1"},
            {"PlayerID": "plr_fghjk", "Name": "Bruno", "PoolMember": "1", "Active": "1"},
            {"PlayerID": "plr_mnpqr", "Name": "José", "PoolMember": "1", "Active": "1"},
            {"PlayerID": "plr_stuvw", "Name": "Fred", "PoolMember": "0", "Active": "1"},
            {"PlayerID": "plr_xyz23", "Name": "Oud-lid", "PoolMember": "0", "Active": "0"},
        ],
        "player_aliases.csv": [
            {"Alias": "Joseph", "PlayerID": "plr_mnpqr", "Source": "manual"},
        ],
        "locations.csv": [
            {"LocationID": "loc_abcde", "Name": "Gent", "Active": "1"},
        ],
        "location_aliases.csv": [
            {"Alias": "Ghent", "LocationID": "loc_abcde", "Source": "manual"},
        ],
        "pairings.csv": [],
        "pairings_history.csv": [
            {
                "Date": "2026-10-10",
                "Table": "1",
                "Players": "plr_abcde | plr_fghjk | plr_mnpqr | plr_stuvw",
                "Season": "2026-2027",
                "Location": "loc_abcde",
            },
        ],
        "scores_history.csv": [],
        "reserve_assignments.csv": [],
        "seasons.csv": [
            {
                "Season": "2026-2027",
                "SeasonNumber": "1",
                "SeasonStartYear": "2026",
                "Status": "actief",
            },
        ],
    }
    for filename in VERSIONED_FILES:
        _write_csv(version_dir / filename, VERSIONED_SCHEMAS[filename], rows[filename])
    (data_root / "active-version.json").write_text(json.dumps({
        "manifest_version": 1,
        "active_version": version_id,
    }), encoding="utf-8")
    return version_dir


def test_versioned_adapter_resolves_names_aliases_reserves_and_pool(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    _activate_version(data_root)
    adapter = ReferenceAdapter(data_root)

    assert adapter.is_versioned
    assert adapter.player_pool() == ["An", "Bruno", "José"]
    assert adapter.active_players() == ["An", "Bruno", "José", "Fred"]
    assert adapter.player_id("  JOSEPH  ") == "plr_mnpqr"
    assert adapter.player_name("plr_mnpqr") == "José"
    assert adapter.player_id("Reserve 2") == "RESERVE:2"
    assert adapter.player_name("RESERVE:2") == "Reserve 2"
    assert adapter.player_tokens("An | Joseph | Reserve 1") == (
        "plr_abcde | plr_mnpqr | RESERVE:1"
    )
    assert adapter.player_names("plr_abcde | plr_mnpqr | RESERVE:1") == (
        "An | José | Reserve 1"
    )
    assert adapter.location_id("  GHENT ") == "loc_abcde"
    assert adapter.location_name("loc_abcde") == "Gent"


def test_versioned_adapter_rejects_unknown_references(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    _activate_version(data_root)
    adapter = ReferenceAdapter(data_root)

    with pytest.raises(ValueError, match="Unknown player name or alias"):
        adapter.player_id("Unknown")
    with pytest.raises(ValueError, match="Unknown player ID"):
        adapter.player_name("plr_zzzzz")
    with pytest.raises(ValueError, match="Unknown location name or alias"):
        adapter.location_id("Unknown")
    with pytest.raises(ValueError, match="Unknown location ID"):
        adapter.location_name("loc_zzzzz")


def test_legacy_adapter_preserves_name_based_behavior(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    (data_root / "AllPlayers.csv").write_text("An\nBruno\n", encoding="utf-8")
    adapter = ReferenceAdapter(data_root)

    assert not adapter.is_versioned
    assert adapter.player_pool() == ["An", "Bruno"]
    assert adapter.player_id("An") == "An"
    assert adapter.player_name("An") == "An"
    assert adapter.player_id("Reserve 1") == "Reserve 1"
    assert adapter.player_name("Reserve 1") == "Reserve 1"
    assert adapter.location_id("Gent") == "Gent"
    assert adapter.location_name("Gent") == "Gent"


def test_versioned_player_pool_and_pairings_round_trip_names_and_ids(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    history_path = version_dir / "pairings_history.csv"

    assert load_all_players(version_dir / "players.csv") == ["An", "Bruno", "José"]
    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        version_dir / "pairings.csv",
        history_filename=history_path,
        play_date="2026-10-11",
        location="Ghent",
    )

    with (version_dir / "pairings.csv").open(
        "r", encoding="utf-8", newline=""
    ) as file:
        pair_rows = list(csv.DictReader(file))
    with history_path.open("r", encoding="utf-8", newline="") as file:
        history_rows = list(csv.DictReader(file))

    assert {
        tuple(sorted((row["Player1"], row["Player2"]))): row["Count"]
        for row in pair_rows
    } == {
        ("plr_abcde", "plr_fghjk"): "1",
        ("plr_abcde", "plr_mnpqr"): "1",
        ("plr_fghjk", "plr_mnpqr"): "1",
    }
    assert history_rows[-1] == {
        "Date": "2026-10-11",
        "Table": "1",
        "Players": "plr_abcde | plr_fghjk | plr_mnpqr | RESERVE:1",
        "Season": "2026-2027",
        "Location": "loc_abcde",
    }
    assert _load_pairings_history("2026-10-11", history_path) == [
        ["An", "Bruno", "José", "Reserve 1"]
    ]
    assert load_pair_counts(version_dir / "pairings.csv") == {
        ("An", "Bruno"): 1,
        ("An", "José"): 1,
        ("Bruno", "José"): 1,
    }


def test_versioned_score_and_reserve_assignment_round_trip_ids(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    history_path = version_dir / "pairings_history.csv"
    scores_path = version_dir / "scores_history.csv"
    assignments_path = version_dir / "reserve_assignments.csv"
    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        version_dir / "pairings.csv",
        history_filename=history_path,
        play_date="2026-10-11",
        location="Gent",
    )
    save_reserve_assignments(
        "2026-10-11",
        {"Reserve 1": "Fred"},
        assignments_path,
    )
    save_game_score(
        "2026-10-11",
        1,
        1,
        ["An", "Bruno"],
        ["José", "Reserve 1"],
        101,
        20,
        scores_path,
    )

    with assignments_path.open("r", encoding="utf-8", newline="") as file:
        assignment_rows = list(csv.DictReader(file))
    with scores_path.open("r", encoding="utf-8", newline="") as file:
        score_rows = list(csv.DictReader(file))
    standings = compute_standings(
        scores_path,
        "2026-10-11",
        history_filename=history_path,
        reserve_assignments_filename=assignments_path,
    )

    assert assignment_rows == [{
        "Date": "2026-10-11",
        "Slot": "RESERVE:1",
        "PlayerID": "plr_stuvw",
    }]
    assert score_rows[0]["Team1Players"] == "plr_abcde | plr_fghjk"
    assert score_rows[0]["Team2Players"] == "plr_mnpqr | RESERVE:1"
    loaded_scores = load_scores(scores_path, "2026-10-11")
    assert loaded_scores[0]["Team1Players"] == "An | Bruno"
    assert loaded_scores[0]["Team2Players"] == "José | Reserve 1"
    assert load_reserve_assignments(assignments_path) == {
        "2026-10-11": {"RESERVE:1": "plr_stuvw"},
    }
    assert get_reserve_assignments("2026-10-11", assignments_path) == {
        "Reserve 1": "Fred",
    }
    by_player = {row["player"]: row for row in standings}
    assert by_player["Fred*"]["games_played"] == 1
    assert by_player["Fred*"]["wins"] == 0
    assert by_player["An"]["wins"] == 1
