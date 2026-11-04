import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from data_paths import VERSIONED_FILES, active_data_dir
from generate_static_snapshot import build_snapshot
from github_publish import (
    SNAPSHOT_ARCHIVE,
    _snapshot_archive_bytes,
    trigger_mirror_workflow,
)
from manillen_functions import (
    _load_pairings_history,
    delete_pairings_by_date,
    fill_scorebladen_from_history,
    load_all_players,
    load_pair_counts,
    update_pairs_in_csv,
)
from manillen_core.reference_adapter import ReferenceAdapter
from manillen_core.data_helpers import (
    load_pairing_counts as load_pairing_count_rows,
    load_pairing_history,
    load_pairing_locations,
    load_pairing_records,
    load_reserve_assignments,
)
from reserve_assignments import get_reserve_assignments, save_reserve_assignments
from score_functions import compute_standings, load_scores, save_game_score
from manillen_core.season_helpers import load_season_playdays
from rename_player import rename_player
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
        "files": {
            filename: hashlib.sha256(
                (version_dir / filename).read_bytes()
            ).hexdigest()
            for filename in VERSIONED_FILES
        },
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


def test_versioned_history_helpers_return_display_names(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    history_path = version_dir / "pairings_history.csv"
    adapter = ReferenceAdapter(data_root)

    records = load_pairing_records(history_path, adapter)

    assert records == [{
        "Date": "2026-10-10",
        "Table": 1,
        "Players": ["An", "Bruno", "José", "Fred"],
        "Season": "2026-2027",
        "Location": "Gent",
    }]
    assert load_pairing_history(history_path, adapter) == {
        "2026-10-10": [(1, ["An", "Bruno", "José", "Fred"])],
    }
    assert load_pairing_locations(history_path, adapter) == {
        "2026-10-10": "Gent",
    }
    assert load_season_playdays(
        history_path, "2026-2027", adapter
    ) == [{
        "Date": "2026-10-10",
        "Location": "Gent",
        "PlayersPresent": 4,
    }]


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
    assert load_pairing_count_rows(version_dir / "pairings.csv") == [
        ("An", "Bruno", 1),
        ("An", "José", 1),
        ("Bruno", "José", 1),
    ]


def test_versioned_pairing_updates_and_deletes_preserve_reference_ids(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    pairings_path = version_dir / "pairings.csv"
    _write_csv(
        pairings_path,
        VERSIONED_SCHEMAS["pairings.csv"],
        [
            {"Player1": "plr_abcde", "Player2": "plr_fghjk", "Count": "4"},
            {"Player1": "plr_abcde", "Player2": "plr_mnpqr", "Count": "2"},
            {"Player1": "plr_fghjk", "Player2": "plr_mnpqr", "Count": "3"},
        ],
    )
    history_path = version_dir / "pairings_history.csv"

    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        pairings_path,
        history_filename=history_path,
        play_date="2026-10-11",
        location="Gent",
    )
    delete_pairings_by_date(
        "2026-10-11",
        csv_filename=pairings_path,
        history_filename=history_path,
    )

    with pairings_path.open("r", encoding="utf-8", newline="") as file:
        pair_rows = list(csv.DictReader(file))
    with history_path.open("r", encoding="utf-8", newline="") as file:
        history_rows = list(csv.DictReader(file))
    assert {
        tuple(sorted((row["Player1"], row["Player2"]))): row["Count"]
        for row in pair_rows
    } == {
        ("plr_abcde", "plr_fghjk"): "4",
        ("plr_abcde", "plr_mnpqr"): "2",
        ("plr_fghjk", "plr_mnpqr"): "3",
    }
    assert [row["Date"] for row in history_rows] == ["2026-10-10"]


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


def test_versioned_excel_export_shows_names_and_reserve_assignment(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    history_path = version_dir / "pairings_history.csv"
    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        version_dir / "pairings.csv",
        history_filename=history_path,
        play_date="2026-10-11",
        location="Gent",
    )
    template = tmp_path / "template.xlsx"
    workbook = Workbook()
    workbook.active.title = "Tafel 1"
    for table in range(2, 5):
        workbook.create_sheet(f"Tafel {table}")
    workbook.save(template)

    output = fill_scorebladen_from_history(
        play_date="2026-10-11",
        history_filename=history_path,
        template_filename=template,
        output_dir=tmp_path / "generated",
        reserve1="Frederik",
    )

    exported = load_workbook(output, data_only=True)
    sheet = exported["Tafel 1"]
    assert [sheet[cell].value for cell in ("B10", "B19", "E10", "E19")] == [
        "An",
        "Bruno",
        "José",
        "Frederik",
    ]


def test_versioned_snapshot_exports_display_names_not_ids(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    history_path = version_dir / "pairings_history.csv"
    pairings_path = version_dir / "pairings.csv"
    scores_path = version_dir / "scores_history.csv"
    assignments_path = version_dir / "reserve_assignments.csv"
    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        pairings_path,
        history_filename=history_path,
        play_date="2026-10-11",
        location="Ghent",
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

    _, files = build_snapshot(data_root)

    assert files["players.json"] == ["An", "Bruno", "José"]
    season = files["seasons/2026-2027.json"]
    playday = next(day for day in season["playdays"] if day["date"] == "2026-10-11")
    assert playday["location"] == "Gent"
    assert playday["tables"][0]["players"] == [
        "An",
        "Bruno",
        "José",
        "Fred*",
    ]
    assert season["scores"][0]["team2Players"] == "José | Fred*"
    serialized = json.dumps(files, ensure_ascii=False)
    assert "plr_" not in serialized
    assert "loc_" not in serialized
    _, archive_bytes = _snapshot_archive_bytes(data_root)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        archive_files = {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
        }
    assert "players.json" in archive_files
    assert all(
        "plr_" not in content and "loc_" not in content
        for content in archive_files.values()
    )


def test_versioned_publisher_uploads_name_only_archive_before_dispatch(
    tmp_path,
    monkeypatch,
):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    update_pairs_in_csv(
        [("An", "Bruno", "José", "Reserve 1")],
        version_dir / "pairings.csv",
        history_filename=version_dir / "pairings_history.csv",
        play_date="2026-10-11",
        location="Gent",
    )
    before = {
        path.relative_to(data_root): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }
    calls = []

    def fake_request_json(request, allow_not_found=False):
        method = request.get_method()
        calls.append(method)
        if method == "GET":
            assert allow_not_found
            assert request.full_url.endswith(f"/{SNAPSHOT_ARCHIVE}?ref=main")
            return 404, {}
        assert method == "PUT"
        payload = json.loads(request.data)
        with zipfile.ZipFile(
            io.BytesIO(base64.b64decode(payload["content"]))
        ) as archive:
            members = archive.namelist()
            assert all(member.endswith(".json") for member in members)
            contents = [
                archive.read(member).decode("utf-8")
                for member in members
            ]
        assert all(
            "plr_" not in content and "loc_" not in content
            for content in contents
        )
        return 201, {}

    class DispatchResponse:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        calls.append(request.get_method())
        assert timeout == 15
        assert request.full_url.endswith(
            "/actions/workflows/publish-mirror.yml/dispatches"
        )
        return DispatchResponse()

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/manillen")
    monkeypatch.setenv("GITHUB_WORKFLOW", "publish-mirror.yml")
    monkeypatch.setenv("GITHUB_REF", "main")
    monkeypatch.setattr("github_publish._request_json", fake_request_json)
    monkeypatch.setattr("github_publish.urlopen", fake_urlopen)

    trigger_mirror_workflow(data_root)

    after = {
        path.relative_to(data_root): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }
    assert calls == ["GET", "PUT", "POST"]
    assert after == before


def test_app_starts_with_active_id_version_and_displays_names(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    repo_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["MANILLEN_DATA_DIR"] = str(data_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import app, json; "
                "print(json.dumps({"
                "'active': str(app.ACTIVE_DATA_DIR), "
                "'players': app.players, "
                "'history': app._read_history(), "
                "'locations': app._location_choices()"
                "}, ensure_ascii=False))"
            ),
        ],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    state = json.loads(result.stdout.strip().splitlines()[-1])
    assert state == {
        "active": str(version_dir),
        "players": ["An", "Bruno", "José"],
        "history": {
            "2026-10-10": [
                ["1", ["An", "Bruno", "José", "Fred"]],
            ],
        },
        "locations": {"Gent": "Gent"},
    }


def test_offline_player_rename_preserves_id_history_excel_and_old_profile_url(
    tmp_path,
):
    data_root = tmp_path / "store"
    data_root.mkdir()
    old_version = _activate_version(data_root)
    excel_dir = data_root / "Scorebladen"
    excel_dir.mkdir()
    old_excel = excel_dir / "2026-10-10.xlsx"
    old_excel.write_bytes(b"existing workbook")
    backup_parent = tmp_path / "backups"
    backup_parent.mkdir()

    before_snapshot = build_snapshot(data_root)[1]
    old_player_bytes = (old_version / "players.csv").read_bytes()
    result = rename_player(
        data_root,
        "plr_abcde",
        "Anne",
        backup_parent / "before-rename",
    )

    adapter = ReferenceAdapter(data_root)
    active_version = active_data_dir(data_root)
    _, renamed_snapshot = build_snapshot(data_root)
    with (active_version / "player_aliases.csv").open(
        "r", encoding="utf-8", newline=""
    ) as file:
        aliases = list(csv.DictReader(file))
    template = tmp_path / "template.xlsx"
    workbook = Workbook()
    workbook.active.title = "Tafel 1"
    for table in range(2, 5):
        workbook.create_sheet(f"Tafel {table}")
    workbook.save(template)
    generated_excel = fill_scorebladen_from_history(
        play_date="2026-10-10",
        history_filename=active_version / "pairings_history.csv",
        template_filename=template,
        output_dir=tmp_path / "generated",
    )
    exported = load_workbook(generated_excel, data_only=True)
    subprocess_result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app, json; print(json.dumps(app.players, ensure_ascii=False))",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "MANILLEN_DATA_DIR": str(data_root)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result["player_id"] == "plr_abcde"
    assert result["old_name"] == "An"
    assert result["new_name"] == "Anne"
    assert result["manifest"]["previous_version"] == "v_test123"
    assert adapter.player_id("An") == adapter.player_id("Anne") == "plr_abcde"
    assert adapter.player_name("plr_abcde") == "Anne"
    assert (old_version / "players.csv").read_bytes() == old_player_bytes
    assert old_excel.read_bytes() == b"existing workbook"
    assert exported["Tafel 1"]["B10"].value == "Anne"
    assert any(
        row["Alias"] == "An"
        and row["PlayerID"] == "plr_abcde"
        and row["Source"] == "rename"
        for row in aliases
    )
    assert before_snapshot["players/an.json"]["name"] == "An"
    assert renamed_snapshot["players/anne.json"]["name"] == "Anne"
    assert renamed_snapshot["players/an.json"]["name"] == "Anne"
    assert json.loads(subprocess_result.stdout.strip().splitlines()[-1])[0] == "Anne"


def test_offline_player_rename_rejects_conflicting_name_without_changing_data(
    tmp_path,
):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    before = {
        path.relative_to(data_root): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match="already assigned"):
        rename_player(
            data_root,
            "plr_abcde",
            "Bruno",
            tmp_path / "backups" / "must-not-exist",
        )

    after = {
        path.relative_to(data_root): path.read_bytes()
        for path in data_root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (tmp_path / "backups").exists()
