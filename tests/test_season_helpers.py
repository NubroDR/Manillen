import csv
import shutil
from pathlib import Path

import pytest

from manillen_functions import save_pairings_history
from mirror_app.data_helpers import (
    DEFAULT_SEASON,
    load_pairing_locations,
    load_pairing_records,
)
from mirror_app.score_helpers import compute_standings
from mirror_app.season_helpers import (
    MIN_GAMES_FOR_AWARD,
    append_season_and_close_current,
    compute_closed_season_awards,
    compute_hall_of_fame,
    compute_legacy_hall_of_fame,
    compute_tool_awards,
    ensure_season_data,
    get_active_season,
    load_seasons,
    load_legacy_seasons,
    load_season_playdays,
    migrate_pairing_history,
    next_season_values,
    reopen_season,
    sort_season_rows_newest_first,
)


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_old_history_loads_and_migration_adds_default_season_once(tmp_path):
    history = tmp_path / "pairings_history.csv"
    original = "Date,Table,Players\n2026-02-14,1,An | Bruno | Etienne | Freddy\n"
    history.write_text(original, encoding="utf-8")

    assert load_pairing_records(history)[0]["Season"] == DEFAULT_SEASON
    assert migrate_pairing_history(history) is True
    first_migrated = history.read_bytes()
    assert history.with_name("pairings_history.csv.bak-pre-seasons").read_text(encoding="utf-8") == original
    assert migrate_pairing_history(history) is False
    assert history.read_bytes() == first_migrated
    assert load_pairing_records(history)[0]["Season"] == DEFAULT_SEASON
    assert load_pairing_records(history)[0]["Location"] == ""


def test_saving_pairing_history_persists_playday_location(tmp_path):
    history = tmp_path / "pairings_history.csv"

    save_pairings_history(
        [["An", "Bruno", "Etienne", "Freddy"]],
        play_date="2026-10-31",
        history_filename=history,
        season="2026-2027",
        location="Brugge",
    )

    assert load_pairing_locations(history) == {"2026-10-31": "Brugge"}


def test_migration_preserves_nonempty_seasons_and_never_overwrites_backup(tmp_path):
    history = tmp_path / "pairings_history.csv"
    history.write_text(
        "Date,Table,Players,Season\n"
        "2026-02-14,1,An | Bruno | Etienne | Freddy,custom-label\n"
        "2026-05-16,1,An | Bruno | Etienne | Freddy,\n",
        encoding="utf-8",
    )
    backup = history.with_name("pairings_history.csv.bak-pre-seasons")
    backup.write_text("user-provided-backup", encoding="utf-8")

    migrate_pairing_history(history)

    assert backup.read_text(encoding="utf-8") == "user-provided-backup"
    records = load_pairing_records(history)
    assert [row["Season"] for row in records] == ["custom-label", DEFAULT_SEASON]


def test_migration_does_not_run_when_backup_path_is_not_a_file(tmp_path):
    history = tmp_path / "pairings_history.csv"
    original = "Date,Table,Players\n2026-02-14,1,An | Bruno | Etienne | Freddy\n"
    history.write_text(original, encoding="utf-8")
    history.with_name("pairings_history.csv.bak-pre-seasons").mkdir()

    with pytest.raises(OSError, match="backup is not a file"):
        migrate_pairing_history(history)

    assert history.read_text(encoding="utf-8") == original


def test_migration_keeps_original_when_atomic_replace_fails(tmp_path, monkeypatch):
    history = tmp_path / "pairings_history.csv"
    original = "Date,Table,Players\n2026-02-14,1,An | Bruno | Etienne | Freddy\n"
    history.write_text(original, encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        migrate_pairing_history(history)

    assert history.read_text(encoding="utf-8") == original
    assert history.with_name("pairings_history.csv.bak-pre-seasons").read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_ensure_season_data_creates_register_and_migration_backup(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    history = data_dir / "pairings_history.csv"
    history.write_text("Date,Table,Players\n", encoding="utf-8")

    ensure_season_data(data_dir)

    assert get_active_season(data_dir / "seasons.csv")["Season"] == "2026-2027"
    assert (data_dir / "pairings_history.csv.bak-pre-seasons").exists()


def test_season_lifecycle_preview_values_close_and_reopen_guard(tmp_path):
    register = tmp_path / "seasons.csv"
    ensure_season_data(tmp_path)
    assert next_season_values(register) == {
        "Season": "2027-2028",
        "SeasonNumber": 12,
        "SeasonStartYear": 2027,
    }
    append_season_and_close_current(register, "label-editable")
    seasons = load_seasons(register)
    assert [(row["Season"], row["Status"]) for row in seasons] == [
        ("2026-2027", "afgesloten"),
        ("label-editable", "actief"),
    ]
    with pytest.raises(ValueError, match="opvolgend seizoen"):
        reopen_season(register, "2026-2027")


def test_season_rows_are_sorted_newest_first():
    rows = [
        (9, "2024-2025"),
        (11, "2026-2027"),
        (10, "2025-2026"),
    ]

    assert sort_season_rows_newest_first(rows) == [
        (11, "2026-2027"),
        (10, "2025-2026"),
        (9, "2024-2025"),
    ]


def test_reopen_works_when_there_is_no_active_successor(tmp_path):
    register = tmp_path / "seasons.csv"
    write_csv(register, ["Season", "SeasonNumber", "SeasonStartYear", "Status"], [
        {"Season": "2025-2026", "SeasonNumber": 10, "SeasonStartYear": 2025, "Status": "afgesloten"},
        {"Season": "2026-2027", "SeasonNumber": 11, "SeasonStartYear": 2026, "Status": "afgesloten"},
    ])

    reopen_season(register, "2025-2026")

    assert get_active_season(register)["Season"] == "2025-2026"


def test_tool_awards_use_only_eligible_pool_players_and_allow_overlap():
    assert MIN_GAMES_FOR_AWARD == 3
    standings = [
        {"player": "Reserve 1*", "wins": 20, "games_played": 20, "point_diff": 500},
        {"player": "An", "wins": 4, "games_played": 5, "point_diff": 10},
        {"player": "Bruno", "wins": 3, "games_played": 3, "point_diff": 5},
        {"player": "Etienne", "wins": 2, "games_played": 2, "point_diff": 0},
    ]
    awards = compute_tool_awards(standings, ["An", "Bruno", "Etienne"])
    assert awards == {"Gold": "An", "Silver": "Bruno", "RedLantern": "Bruno"}
    assert "Reserve 1*" not in awards.values()


def test_legacy_season_awards_can_be_canonicalized_to_the_player_pool(tmp_path):
    seasons = tmp_path / "seasons_history.csv"
    write_csv(seasons, [
        "Season", "SeasonNumber", "Pool", "Gold", "Silver", "Bronze", "RedLantern",
    ], [{
        "Season": "2024-2025",
        "SeasonNumber": 10,
        "Pool": 4,
        "Gold": "Gilbert W",
        "Silver": "Marc G",
        "Bronze": "Gilbert W | Marc G",
        "RedLantern": "José B",
    }])

    rows = load_legacy_seasons(seasons, pool_players=["Gilbert", "Marc", "José"])

    assert rows[0]["Gold"] == "Gilbert"
    assert rows[0]["Silver"] == "Marc"
    assert rows[0]["Bronze"] == "Gilbert | Marc"
    assert rows[0]["RedLantern"] == "José"


def test_hall_of_fame_sort_prioritizes_medals_then_fewer_red_lanterns(tmp_path):
    seasons = tmp_path / "seasons_history.csv"
    write_csv(seasons, [
        "Season", "SeasonNumber", "Pool", "Gold", "Silver", "Bronze", "RedLantern",
    ], [
        {
            "Season": "2020-2021",
            "SeasonNumber": 1,
            "Pool": 5,
            "Gold": "Gold",
            "Silver": "Silver",
            "Bronze": "Bronze",
            "RedLantern": "Lantern High",
        },
        {
            "Season": "2021-2022",
            "SeasonNumber": 2,
            "Pool": 5,
            "Gold": "Gold",
            "Silver": "Silver",
            "Bronze": "Bronze",
            "RedLantern": "Lantern High",
        },
    ])

    rows = compute_hall_of_fame(
        ["Gold", "Silver", "Bronze", "Lantern Low", "Lantern High"],
        seasons,
    )

    assert [row["Player"] for row in rows] == [
        "Gold", "Silver", "Bronze", "Lantern Low", "Lantern High",
    ]


def test_load_season_playdays_counts_present_players_per_date(tmp_path):
    history = tmp_path / "pairings_history.csv"
    write_csv(history, ["Date", "Table", "Players", "Season", "Location"], [
        {"Date": "2026-05-16", "Table": 1, "Players": "An | Bruno | Cato | Dina", "Season": "2026-2027", "Location": "Brugge"},
        {"Date": "2026-05-16", "Table": 2, "Players": "Evi | Fred | Gijs | Hana", "Season": "2026-2027", "Location": "Brugge"},
        {"Date": "2026-02-14", "Table": 1, "Players": "An | Bruno | Cato | Dina", "Season": "2026-2027", "Location": ""},
        {"Date": "2026-05-16", "Table": 3, "Players": "An | Bruno | Cato | Dina", "Season": "2025-2026", "Location": "Elsewhere"},
    ])

    playdays = load_season_playdays(history, "2026-2027")

    assert playdays == [
        {"Date": "2026-02-14", "Location": "", "PlayersPresent": 4},
        {"Date": "2026-05-16", "Location": "Brugge", "PlayersPresent": 8},
    ]


def test_closed_season_awards_are_derived_from_scores_and_exclude_reserves(tmp_path):
    register = tmp_path / "seasons.csv"
    history = tmp_path / "pairings_history.csv"
    scores = tmp_path / "scores_history.csv"
    write_csv(register, ["Season", "SeasonNumber", "SeasonStartYear", "Status"], [
        {"Season": "2025-2026", "SeasonNumber": 10, "SeasonStartYear": 2025, "Status": "afgesloten"},
        {"Season": "2026-2027", "SeasonNumber": 11, "SeasonStartYear": 2026, "Status": "actief"},
    ])
    write_csv(history, ["Date", "Table", "Players", "Season"], [
        {"Date": "2025-10-01", "Table": 1, "Players": "An | Bruno | Etienne | Reserve 1", "Season": "2025-2026"},
        {"Date": "2026-10-01", "Table": 1, "Players": "An | Bruno | Etienne | Reserve 1", "Season": "2026-2027"},
    ])
    score_rows = []
    for game in range(1, 4):
        score_rows.append({
            "Date": "2025-10-01",
            "Table": 1,
            "Game": game,
            "Team1Players": "An | Bruno",
            "Team2Players": "Etienne | Reserve 1",
            "Team1Score": "110",
            "Team2Score": "80",
        })
    write_csv(scores, [
        "Date", "Table", "Game", "Team1Players", "Team2Players", "Team1Score", "Team2Score",
    ], score_rows)

    awards = compute_closed_season_awards(register, scores, history, ["An", "Bruno", "Etienne"])

    assert [season for season, _ in awards] == ["2025-2026"]
    assert awards[0][1]["Gold"] == "An"
    assert "Reserve 1" not in awards[0][1].values()


def test_standings_resolve_reserve_name_with_asterisk_by_date(tmp_path):
    history = tmp_path / "pairings_history.csv"
    scores = tmp_path / "scores_history.csv"
    assignments = tmp_path / "reserve_assignments.csv"
    write_csv(history, ["Date", "Table", "Players", "Season"], [
        {"Date": "2026-09-19", "Table": 1, "Players": "An | Bruno | Etienne | Reserve 1", "Season": DEFAULT_SEASON},
    ])
    write_csv(scores, [
        "Date", "Table", "Game", "Team1Players", "Team2Players", "Team1Score", "Team2Score",
    ], [{
        "Date": "2026-09-19",
        "Table": 1,
        "Game": 1,
        "Team1Players": "An | Reserve 1",
        "Team2Players": "Bruno | Etienne",
        "Team1Score": "110",
        "Team2Score": "80",
    }])
    write_csv(assignments, ["Date", "Slot", "Name"], [
        {"Date": "2026-09-19", "Slot": "Reserve 1", "Name": "Jeroen"},
    ])

    rows = compute_standings(scores, reserve_assignments_filename=assignments)

    assert "Jeroen*" in {row["player"] for row in rows}
    assert "Reserve 1" not in {row["player"] for row in rows}


def test_standings_filter_by_season_and_specific_play_day(tmp_path):
    history = tmp_path / "pairings_history.csv"
    scores = tmp_path / "scores_history.csv"
    write_csv(history, ["Date", "Table", "Players", "Season"], [
        {"Date": "2026-09-19", "Table": 1, "Players": "An | Bruno | Etienne | Fred", "Season": "2026-2027"},
        {"Date": "2026-10-03", "Table": 1, "Players": "An | Bruno | Etienne | Fred", "Season": "2026-2027"},
        {"Date": "2027-09-18", "Table": 1, "Players": "An | Bruno | Etienne | Fred", "Season": "2027-2028"},
    ])
    write_csv(scores, [
        "Date", "Table", "Game", "Team1Players", "Team2Players", "Team1Score", "Team2Score",
    ], [
        {
            "Date": play_date,
            "Table": 1,
            "Game": 1,
            "Team1Players": "An | Bruno",
            "Team2Players": "Etienne | Fred",
            "Team1Score": "110",
            "Team2Score": "80",
        }
        for play_date in ("2026-09-19", "2026-10-03", "2027-09-18")
    ])

    season_rows = compute_standings(
        scores,
        season="2026-2027",
        history_filename=history,
    )
    day_rows = compute_standings(
        scores,
        play_date="2026-10-03",
        season="2026-2027",
        history_filename=history,
    )

    assert {row["games_played"] for row in season_rows} == {2}
    assert {row["games_played"] for row in day_rows} == {1}
    assert {row["player"] for row in day_rows} == {"An", "Bruno", "Etienne", "Fred"}


def test_hall_of_fame_totals_match_fixture(tmp_path):
    source = Path(__file__).parent / "fixtures"
    for filename in ("AllPlayers.csv", "seasons_history.csv", "hall_of_fame_check.csv"):
        shutil.copyfile(source / filename, tmp_path / filename)
    pool = [
        line.strip()
        for line in (tmp_path / "AllPlayers.csv").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actual = compute_legacy_hall_of_fame(tmp_path / "seasons_history.csv", pool)
    expected = {}
    with (tmp_path / "hall_of_fame_check.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            expected[row["Player"]] = {
                "Gold": int(row["Gold"]),
                "Silver": int(row["Silver"]),
                "Bronze": int(row["Bronze"]),
                "RedLantern": int(row["RedLantern"]),
                "InPool": row["InPool"],
            }

    zero_awards = {"Gold": 0, "Silver": 0, "Bronze": 0, "RedLantern": 0}
    assert set(actual) == {
        name
        for name, row in expected.items()
        if {key: row[key] for key in zero_awards} != zero_awards or name in pool
    }
    for name, row in expected.items():
        totals = {key: row[key] for key in zero_awards}
        assert actual.get(name, zero_awards) == totals
    hall = compute_hall_of_fame(pool, tmp_path / "seasons_history.csv")
    assert {row["Player"] for row in hall if row["InPool"]} == set(pool)
    assert any(not row["InPool"] for row in hall)
    hall_by_name = {row["Player"]: row for row in hall}
    for name, row in expected.items():
        assert hall_by_name.get(name, {}).get("InPool", False) == (row["InPool"] == "yes")
