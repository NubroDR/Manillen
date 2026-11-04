import csv
import json
import subprocess
import sys
from pathlib import Path

from mirror_app.score_helpers import compute_standings
from profile_data import profile_data


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_profile_fixture(data_dir):
    data_dir.mkdir()
    (data_dir / "AllPlayers.csv").write_text(
        "Alice\n alice \nBob\nCasey\nDana\n",
        encoding="utf-8",
    )
    write_csv(data_dir / "pairings.csv", ["Player1", "Player2", "Count"], [
        {"Player1": "Alice", "Player2": "Bob", "Count": "0"},
    ])
    write_csv(
        data_dir / "pairings_history.csv",
        ["Date", "Table", "Players", "Season", "Location"],
        [{
            "Date": "2026-01-02",
            "Table": "1",
            "Players": "Alice | Bob | Casey | Dana",
            "Season": "2025-2026",
            "Location": "Hall",
        }],
    )
    write_csv(
        data_dir / "scores_history.csv",
        [
            "Date",
            "Table",
            "Game",
            "Team1Players",
            "Team2Players",
            "Team1Score",
            "Team2Score",
        ],
        [{
            "Date": "2026-01-02",
            "Table": "1",
            "Game": "1",
            "Team1Players": "Alice | Mystery",
            "Team2Players": "Bob | Casey",
            "Team1Score": "101",
            "Team2Score": "101",
        }],
    )
    write_csv(
        data_dir / "reserve_assignments.csv",
        ["Date", "Slot", "Name"],
        [{"Date": "2026-01-02", "Slot": "Reserve 1", "Name": "Guest"}],
    )
    write_csv(
        data_dir / "seasons.csv",
        ["Season", "SeasonNumber", "SeasonStartYear", "Status"],
        [{"Season": "2025-2026", "SeasonNumber": "10", "SeasonStartYear": "2025", "Status": "afgesloten"}],
    )
    write_csv(
        data_dir / "seasons_history.csv",
        ["Season", "SeasonNumber", "Pool", "Gold", "Silver", "Bronze", "RedLantern"],
        [{"Season": "2024-2025", "SeasonNumber": "9", "Pool": "4", "Gold": "Alice", "Silver": "", "Bronze": "Unknown Award", "RedLantern": ""}],
    )
    write_csv(
        data_dir / "seasons_playdays_legacy.csv",
        ["Season", "Date", "Location", "PlayersPresent", "Pool"],
        [],
    )


def test_profile_reports_schema_unknown_names_ties_and_pairing_drift(tmp_path):
    data_dir = tmp_path / "fixture"
    make_profile_fixture(data_dir)
    before = {
        path.name: path.read_bytes()
        for path in data_dir.iterdir()
    }

    report = profile_data(data_dir)

    quality = report["data_quality"]
    assert report["files"]["scores_history.csv"]["rows"] == 1
    assert report["files"]["pairings.csv"]["schema_valid"] is True
    assert len(quality["duplicate_roster_names"]) == 1
    assert len(quality["normalization_collisions"]) == 1
    assert len(quality["invalid_references"]) == 3
    assert quality["tied_score_rows"] == [{
        "row": 2,
        "date": "2026-01-02",
        "table": "1",
        "game": "1",
    }]
    assert len(quality["pairing_count_drift"]) == 6
    assert report["repository_inventory"]["pool_membership"][
        "pool_member_column_present"
    ] is False
    assert {
        path.name: path.read_bytes()
        for path in data_dir.iterdir()
    } == before


def test_profile_hides_names_unless_explicitly_requested(tmp_path):
    data_dir = tmp_path / "fixture"
    make_profile_fixture(data_dir)

    redacted = json.dumps(profile_data(data_dir))
    detailed = profile_data(data_dir, include_names=True)
    detailed_json = json.dumps(detailed)

    assert "Mystery" not in redacted
    assert "Guest" not in redacted
    assert "Mystery" in detailed_json
    assert any(
        "values" in row for row in detailed["data_quality"]["unknown_name_groups"]
    )


def test_profile_reports_invalid_reserve_slot_tokens(tmp_path):
    data_dir = tmp_path / "fixture"
    make_profile_fixture(data_dir)
    scores_path = data_dir / "scores_history.csv"
    with scores_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    rows[0]["Team1Players"] = "Alice | Reserve 0"
    write_csv(scores_path, rows[0].keys(), rows)

    report = profile_data(data_dir)

    assert report["data_quality"]["invalid_reserve_tokens"] == [{
        "file": "scores_history.csv",
        "row": 2,
        "column": "Team1Players",
    }]


def test_profile_reports_normalized_alias_conflicts_without_names_by_default(tmp_path):
    data_dir = tmp_path / "fixture"
    make_profile_fixture(data_dir)
    write_csv(
        data_dir / "player_aliases.csv",
        ["Alias", "PlayerID", "Source"],
        [
            {"Alias": "Alice", "PlayerID": "plr_aaaaa", "Source": "manual"},
            {"Alias": " alice ", "PlayerID": "plr_bbbbb", "Source": "manual"},
        ],
    )
    before = {
        path.name: path.read_bytes()
        for path in data_dir.iterdir()
        if path.is_file()
    }

    redacted = profile_data(data_dir)
    detailed = profile_data(data_dir, include_names=True)

    redacted_conflict = redacted["data_quality"]["alias_registry"]["conflicts"][0]
    detailed_conflict = detailed["data_quality"]["alias_registry"]["conflicts"][0]
    assert redacted_conflict == {
        "file": "player_aliases.csv",
        "targets": 2,
        "rows": [2, 3],
    }
    assert detailed_conflict["alias"] == "alice"
    assert detailed_conflict["target_ids"] == ["plr_aaaaa", "plr_bbbbb"]
    assert redacted["files"]["player_aliases.csv"]["schema_valid"] is True
    assert {
        path.name: path.read_bytes()
        for path in data_dir.iterdir()
        if path.is_file()
    } == before


def test_profile_cli_emits_json_for_data_dir(tmp_path):
    data_dir = tmp_path / "fixture"
    make_profile_fixture(data_dir)
    script = Path(__file__).resolve().parents[1] / "profile_data.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--data-dir", str(data_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout)["report_version"] == 1


def test_standings_include_scored_players_outside_the_player_pool(tmp_path):
    scores_path = tmp_path / "scores_history.csv"
    write_csv(
        scores_path,
        [
            "Date",
            "Table",
            "Game",
            "Team1Players",
            "Team2Players",
            "Team1Score",
            "Team2Score",
        ],
        [{
            "Date": "2026-01-02",
            "Table": "1",
            "Game": "1",
            "Team1Players": "Alice | Guest",
            "Team2Players": "Bob | Casey",
            "Team1Score": "101",
            "Team2Score": "50",
        }],
    )

    standings = compute_standings(scores_path)

    assert {row["player"] for row in standings} == {"Alice", "Guest", "Bob", "Casey"}
