import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from manillen_core.reference_helpers import (
    ID_ALPHABET,
    generate_reference_id,
    is_reserve_reference,
    normalize_reference_name,
)
from migrate_ids import build_id_proposal, write_id_proposal


SOURCE_SCHEMAS = {
    "pairings.csv": ["Player1", "Player2", "Count"],
    "pairings_history.csv": ["Date", "Table", "Players", "Season", "Location"],
    "scores_history.csv": [
        "Date",
        "Table",
        "Game",
        "Team1Players",
        "Team2Players",
        "Team1Score",
        "Team2Score",
    ],
    "reserve_assignments.csv": ["Date", "Slot", "Name"],
    "seasons.csv": ["Season", "SeasonNumber", "SeasonStartYear", "Status"],
    "seasons_history.csv": [
        "Season",
        "SeasonNumber",
        "Pool",
        "Gold",
        "Silver",
        "Bronze",
        "RedLantern",
    ],
    "seasons_playdays_legacy.csv": [
        "Season",
        "Date",
        "Location",
        "PlayersPresent",
        "Pool",
    ],
}


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_migration_fixture(data_dir):
    data_dir.mkdir()
    (data_dir / "Scorebladen").mkdir()
    (data_dir / "Scorebladen.xlsx").write_bytes(b"existing-template")
    (data_dir / "Scorebladen" / "historical.xlsx").write_bytes(b"existing-sheet")
    (data_dir / "AllPlayers.csv").write_text(
        "Alice\nALICE\nBob\n",
        encoding="utf-8",
    )
    write_csv(data_dir / "pairings.csv", SOURCE_SCHEMAS["pairings.csv"], [
        {"Player1": "Alice", "Player2": "Bob", "Count": "0"},
    ])
    write_csv(
        data_dir / "pairings_history.csv",
        SOURCE_SCHEMAS["pairings_history.csv"],
        [{
            "Date": "2026-01-02",
            "Table": "1",
            "Players": "Alice | Bob | Casey | Reserve 1",
            "Season": "2025-2026",
            "Location": "Hall",
        }],
    )
    write_csv(
        data_dir / "scores_history.csv",
        SOURCE_SCHEMAS["scores_history.csv"],
        [{
            "Date": "2026-01-02",
            "Table": "1",
            "Game": "1",
            "Team1Players": "Alice | Reserve 1",
            "Team2Players": "Bob | Guest",
            "Team1Score": "101",
            "Team2Score": "50",
        }],
    )
    write_csv(
        data_dir / "reserve_assignments.csv",
        SOURCE_SCHEMAS["reserve_assignments.csv"],
        [{"Date": "2026-01-02", "Slot": "Reserve 1", "Name": "Guest"}],
    )
    write_csv(data_dir / "seasons.csv", SOURCE_SCHEMAS["seasons.csv"], [
        {
            "Season": "2025-2026",
            "SeasonNumber": "10",
            "SeasonStartYear": "2025",
            "Status": "afgesloten",
        },
    ])
    write_csv(data_dir / "seasons_history.csv", SOURCE_SCHEMAS["seasons_history.csv"], [
        {
            "Season": "2024-2025",
            "SeasonNumber": "9",
            "Pool": "2",
            "Gold": "Alice",
            "Silver": "",
            "Bronze": "",
            "RedLantern": "",
        },
    ])
    write_csv(
        data_dir / "seasons_playdays_legacy.csv",
        SOURCE_SCHEMAS["seasons_playdays_legacy.csv"],
        [{
            "Season": "2024-2025",
            "Date": "2025-02-15",
            "Location": "HALL",
            "PlayersPresent": "2",
            "Pool": "2",
        }],
    )


def tree_hashes(path):
    return {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in path.rglob("*")
        if file.is_file()
    }


def test_reference_helpers_normalize_exact_names_and_reserve_placeholders():
    assert normalize_reference_name("  Alice\tSmith ") == "alice smith"
    assert is_reserve_reference("Reserve 2")
    assert is_reserve_reference("reserve:2")
    assert not is_reserve_reference("Reserve 0")
    assert len(ID_ALPHABET) == 31
    assert not set("0o1li") & set(ID_ALPHABET)


def test_generate_reference_id_retries_collisions(monkeypatch):
    choices = iter("aaaaabbbbb")
    monkeypatch.setattr(
        "manillen_core.reference_helpers.secrets.choice",
        lambda alphabet: next(choices),
    )
    used_ids = {"plr_aaaaa"}

    assert generate_reference_id("player", used_ids) == "plr_bbbbb"
    assert "plr_bbbbb" in used_ids


def test_dry_run_proposes_ids_and_aliases_without_mutating_sources(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    before = tree_hashes(data_dir)

    proposal = build_id_proposal(data_dir)

    players = {row["Name"]: row for row in proposal["players"]}
    assert players["Alice"]["PoolMember"] == 1
    assert players["Alice"]["Active"] == 1
    assert players["Casey"]["PoolMember"] == 0
    assert players["Casey"]["Active"] is None
    assert players["Guest"]["PoolMember"] == 0
    assert len({
        row["PlayerID"] for row in proposal["players"]
    }) == len(proposal["players"])
    assert all(
        row["PlayerID"].startswith("plr_")
        and len(row["PlayerID"]) == 9
        and set(row["PlayerID"][4:]) <= set(ID_ALPHABET)
        for row in proposal["players"]
    )
    assert "Reserve 1" not in players
    assert {
        alias["Alias"] for alias in proposal["player_aliases"]
    } >= {"ALICE"}
    assert {
        (row["Name"], row["Active"], row["active_status"])
        for row in proposal["locations"]
    } == {("Hall", None, "requires_manual_review")}
    assert any(alias["Alias"] == "HALL" for alias in proposal["location_aliases"])
    assert proposal["approval"]["status"] == "pending"
    assert proposal["review_summary"]["duplicate_roster_names"] == 1
    expected_hash = proposal.pop("proposal_sha256")
    canonical = json.dumps(
        proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == expected_hash
    assert tree_hashes(data_dir) == before


def test_proposal_output_must_be_external_and_never_overwritten(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)

    with pytest.raises(ValueError, match="outside"):
        write_id_proposal(data_dir, data_dir / "proposal.json")

    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_id_proposal(data_dir, proposal_path)
    assert proposal_path.read_text(encoding="utf-8") == "keep"


def test_proposal_output_contains_reviewable_json_and_no_apply_permission(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    proposal_path = tmp_path / "private-review" / "proposal.json"
    proposal_path.parent.mkdir()

    proposal = write_id_proposal(data_dir, proposal_path)

    assert json.loads(proposal_path.read_text(encoding="utf-8")) == proposal
    assert proposal["approval"] == {
        "required": True,
        "status": "pending",
        "note": "Review privately; no apply command exists yet.",
    }


def test_proposal_refuses_already_migrated_reference_files(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    (data_dir / "players.csv").write_text("PlayerID,Name,PoolMember,Active\n")

    with pytest.raises(ValueError, match="players.csv"):
        build_id_proposal(data_dir)


def test_cli_writes_private_proposal_without_printing_names(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    proposal_path = tmp_path / "review" / "proposal.json"
    proposal_path.parent.mkdir()
    script = Path(__file__).resolve().parents[1] / "migrate_ids.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--data-dir",
            str(data_dir),
            "--proposal-output",
            str(proposal_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Alice" not in completed.stdout
    assert "No source data was changed." in completed.stdout
    assert json.loads(proposal_path.read_text(encoding="utf-8"))[
        "contains_personal_data"
    ] is True
