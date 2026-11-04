import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from build_static_site import build_site, build_site_from_archive
from github_publish import (
    SNAPSHOT_ARCHIVE,
    GitHubPublishError,
    _snapshot_archive_bytes,
    trigger_mirror_workflow,
)
from generate_static_snapshot import build_snapshot, generate_snapshot
from manillen_core.data_helpers import load_pairing_counts, load_reserve_assignments
from manillen_core.score_helpers import compute_standings, load_scores
from manillen_core.season_helpers import (
    compute_closed_season_awards,
    compute_hall_of_fame,
)


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_snapshot_fixture(data_dir):
    data_dir.mkdir()
    (data_dir / "AllPlayers.csv").write_text(
        "An\nBruno\nEtienne\nFreddy\nGilbert\nMatthias\nZoë\n",
        encoding="utf-8",
    )
    write_csv(data_dir / "pairings.csv", ["Player1", "Player2", "Count"], [
        {"Player1": "An", "Player2": "Bruno", "Count": "2"},
        {"Player1": "Etienne", "Player2": "Freddy", "Count": "1"},
    ])
    write_csv(
        data_dir / "pairings_history.csv",
        ["Date", "Table", "Players", "Season", "Location"],
        [
            {
                "Date": "2025-10-04",
                "Table": "1",
                "Players": "An | Bruno | Etienne | Freddy",
                "Season": "2025-2026",
                "Location": "Gent",
            },
            {
                "Date": "2026-05-16",
                "Table": "1",
                "Players": "An | Bruno | Etienne | Reserve 1",
                "Season": "2026-2027",
                "Location": "Brugge",
            },
        ],
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
        [
            {
                "Date": "2025-10-04",
                "Table": "1",
                "Game": "1",
                "Team1Players": "An | Bruno",
                "Team2Players": "Etienne | Freddy",
                "Team1Score": "101",
                "Team2Score": "50",
            },
            {
                "Date": "2025-10-04",
                "Table": "1",
                "Game": "2",
                "Team1Players": "An | Etienne",
                "Team2Players": "Bruno | Freddy",
                "Team1Score": "20",
                "Team2Score": "101",
            },
            {
                "Date": "2025-10-04",
                "Table": "1",
                "Game": "3",
                "Team1Players": "An | Freddy",
                "Team2Players": "Bruno | Etienne",
                "Team1Score": "101",
                "Team2Score": "90",
            },
            {
                "Date": "2026-05-16",
                "Table": "1",
                "Game": "1",
                "Team1Players": "An | Bruno",
                "Team2Players": "Etienne | Reserve 1",
                "Team1Score": "101",
                "Team2Score": "60",
            },
        ],
    )
    write_csv(
        data_dir / "reserve_assignments.csv",
        ["Date", "Slot", "Name"],
        [{"Date": "2026-05-16", "Slot": "Reserve 1", "Name": "Freddy"}],
    )
    write_csv(
        data_dir / "seasons.csv",
        ["Season", "SeasonNumber", "SeasonStartYear", "Status"],
        [
            {"Season": "2025-2026", "SeasonNumber": "10", "SeasonStartYear": "2025", "Status": "afgesloten"},
            {"Season": "2026-2027", "SeasonNumber": "11", "SeasonStartYear": "2026", "Status": "actief"},
        ],
    )
    write_csv(
        data_dir / "seasons_history.csv",
        ["Season", "SeasonNumber", "Pool", "Gold", "Silver", "Bronze", "RedLantern"],
        [{
            "Season": "2024-2025",
            "SeasonNumber": "9",
            "Pool": "22",
            "Gold": "José B",
            "Silver": "Fred G",
            "Bronze": "Gilbert W | Matthias S",
            "RedLantern": "Zoë DR",
        }],
    )
    write_csv(
        data_dir / "seasons_playdays_legacy.csv",
        ["Season", "Date", "Location", "PlayersPresent", "Pool"],
        [{
            "Season": "2024-2025",
            "Date": "2025-02-15",
            "Location": "Gent",
            "PlayersPresent": "22",
            "Pool": "22",
        }],
    )


def read_json_tree(path):
    def reject_constant(value):
        raise AssertionError(f"invalid JSON number: {value}")

    return {
        file.relative_to(path).as_posix(): json.loads(
            file.read_text(encoding="utf-8"),
            parse_constant=reject_constant,
        )
        for file in path.rglob("*.json")
    }


def assert_no_nulls(value):
    if isinstance(value, dict):
        for child in value.values():
            assert_no_nulls(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_nulls(child)
    else:
        assert value is not None


def tree_hash(path):
    return {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in path.iterdir()
        if file.is_file()
    }


def test_snapshot_season_standings_and_playday_match_shared_helpers(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    manifest, files = build_snapshot(data_dir)
    season = files["seasons/2025-2026.json"]
    current = files["seasons/2026-2027.json"]
    history_path = data_dir / "pairings_history.csv"
    scores_path = data_dir / "scores_history.csv"
    assignments_path = data_dir / "reserve_assignments.csv"

    old_standings = compute_standings(
        scores_path,
        season="2025-2026",
        history_filename=history_path,
        reserve_assignments_filename=assignments_path,
    )
    old_day_standings = compute_standings(
        scores_path,
        play_date="2025-10-04",
        season="2025-2026",
        history_filename=history_path,
        reserve_assignments_filename=assignments_path,
    )
    old_day = next(
        day for day in season["playdays"] if day["date"] == "2025-10-04"
    )
    expected_scores = [
        {
            "date": row["Date"],
            "table": row["Table"],
            "game": row["Game"],
            "team1Players": row["Team1Players"].replace(
                "Reserve 1",
                "Freddy*",
            ),
            "team2Players": row["Team2Players"].replace(
                "Reserve 1",
                "Freddy*",
            ),
            "team1Score": row["Team1Score"],
            "team2Score": row["Team2Score"],
            "validScore": int(row["Team1Score"]) != int(row["Team2Score"]),
        }
        for row in load_scores(scores_path, "2025-10-04")
    ]
    expected_scores.sort(
        key=lambda row: (row["date"], -row["table"], -row["game"]),
        reverse=True,
    )

    def normalize(rows):
        return [
            (
                row["player"],
                row["wins"],
                row["games_played"],
                row["points_for"],
                row["points_against"],
                row["point_diff"],
            )
            for row in rows
        ]

    assert manifest["activeSeason"] == "2026-2027"
    assert [
        (
            row["player"], row["wins"], row["gamesPlayed"], row["pointsFor"],
            row["pointsAgainst"], row["pointDiff"],
        )
        for row in season["standings"]
    ] == normalize(old_standings)
    assert [
        (
            row["player"], row["wins"], row["gamesPlayed"], row["pointsFor"],
            row["pointsAgainst"], row["pointDiff"],
        )
        for row in old_day["standings"]
    ] == normalize(old_day_standings)
    assert season["scores"] == expected_scores
    assert current["playdays"][0]["tables"][0]["players"][-1] == "Freddy*"


def test_playday_table_standings_are_scoped_and_scores_stay_in_scores_view(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    history_path = data_dir / "pairings_history.csv"
    with history_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "2025-10-04", "2", "An | Bruno | Etienne | Freddy",
            "2025-2026", "Gent",
        ])
    scores_path = data_dir / "scores_history.csv"
    with scores_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        for game, team1, team2 in (
            (1, "An | Bruno", "Etienne | Freddy"),
            (2, "An | Etienne", "Bruno | Freddy"),
            (3, "An | Freddy", "Bruno | Etienne"),
        ):
            writer.writerow([
                "2025-10-04", "2", game, team1, team2, "20", "101",
            ])

    _, files = build_snapshot(data_dir)
    day = next(
        day
        for day in files["seasons/2025-2026.json"]["playdays"]
        if day["date"] == "2025-10-04"
    )
    tables = {table["table"]: table for table in day["tables"]}
    table_one = {
        row["player"]: (row["wins"], row["losses"])
        for row in tables[1]["standings"]
    }
    table_two = {
        row["player"]: (row["wins"], row["losses"])
        for row in tables[2]["standings"]
    }

    assert table_one["An"] == (2, 1)
    assert table_two["An"] == (0, 3)
    assert [row["player"] for row in tables[1]["standings"]] == [
        "An", "Bruno", "Freddy", "Etienne",
    ]
    assert all("scores" not in table for table in tables.values())
    assert len(files["seasons/2025-2026.json"]["scores"]) == 6


def test_playday_reserve_names_have_asterisk_for_assigned_players(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)

    _, files = build_snapshot(data_dir)
    day = next(
        day
        for day in files["seasons/2026-2027.json"]["playdays"]
        if day["date"] == "2026-05-16"
    )
    table = day["tables"][0]

    assert "Freddy*" in table["players"]
    assert any(row["player"] == "Freddy*" for row in table["standings"])


def test_historical_equal_scores_are_marked_invalid_and_not_counted(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    scores_path = data_dir / "scores_history.csv"
    with scores_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    tied_row = next(row for row in rows if row["Date"] == "2025-10-04" and row["Game"] == "2")
    tied_row["Team1Score"] = tied_row["Team2Score"] = "75"
    write_csv(scores_path, list(rows[0]), rows)
    before = scores_path.read_bytes()

    _, files = build_snapshot(data_dir)
    season = files["seasons/2025-2026.json"]
    tied_score = next(
        row for row in season["scores"]
        if row["date"] == "2025-10-04" and row["game"] == 2
    )
    day = next(day for day in season["playdays"] if day["date"] == "2025-10-04")
    standings = {row["player"]: row for row in day["tables"][0]["standings"]}

    assert tied_score["validScore"] is False
    assert {player: row["wins"] for player, row in standings.items()} == {
        "An": 2, "Bruno": 1, "Etienne": 0, "Freddy": 1,
    }
    assert {player: row["losses"] for player, row in standings.items()} == {
        "An": 0, "Bruno": 1, "Etienne": 2, "Freddy": 1,
    }
    assert scores_path.read_bytes() == before


def test_snapshot_pairings_and_legacy_shared_bronze_match_helpers(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    _, files = build_snapshot(data_dir)
    pairs = files["pairings.json"]
    hall_of_fame = files["hall-of-fame.json"]
    players = ["An", "Bruno", "Etienne", "Freddy", "Gilbert", "Matthias", "Zoë"]
    tool_awards = compute_closed_season_awards(
        data_dir / "seasons.csv",
        data_dir / "scores_history.csv",
        data_dir / "pairings_history.csv",
        players,
    )

    assert pairs == [
        {"player1": row[0], "player2": row[1], "count": row[2]}
        for row in sorted(
            load_pairing_counts(data_dir / "pairings.csv"),
            key=lambda row: (-row[2], row[0].casefold(), row[1].casefold()),
        )
    ]
    assignments = load_reserve_assignments(data_dir / "reserve_assignments.csv")
    assert assignments["2026-05-16"]["Reserve 1"] == "Freddy"
    assert hall_of_fame == compute_hall_of_fame(
        players,
        data_dir / "seasons_history.csv",
        tool_awards,
    )
    bronze = next(row for row in hall_of_fame if row["Player"] == "Gilbert")
    bronze_peer = next(row for row in hall_of_fame if row["Player"] == "Matthias")
    assert bronze["Bronze"] == bronze_peer["Bronze"] == 1


def test_snapshot_is_deterministic_json_only_and_never_changes_source(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    before = tree_hash(data_dir)

    first = generate_snapshot(
        data_dir,
        tmp_path / "build-one",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    second = generate_snapshot(
        data_dir,
        tmp_path / "build-two",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    first_files = read_json_tree(tmp_path / "build-one")
    second_files = read_json_tree(tmp_path / "build-two")

    assert first["buildId"] == second["buildId"]
    assert first_files == second_files
    assert all(path.endswith(".json") for path in first_files)
    assert first["schemaVersion"] == 1
    assert first["generatedAt"] == "2026-01-01T00:00:00+00:00"
    assert first["activeSeason"] == "2026-2027"
    assert {"schemaVersion", "generatedAt", "buildId", "activeSeason", "seasons"} <= first.keys()
    for payload in first_files.values():
        assert_no_nulls(payload)
    assert isinstance(first_files["players.json"], list)
    assert all(isinstance(player, str) for player in first_files["players.json"])
    assert all(
        set(row) == {"player1", "player2", "count"}
        for row in first_files["pairings.json"]
    )
    assert all(
        set(row) == {"Player", "InPool", "Gold", "Silver", "Bronze", "RedLantern"}
        for row in first_files["hall-of-fame.json"]
    )
    season_keys = {
        "season", "seasonNumber", "status", "poolSize", "standings",
        "playdays", "scores", "legacyPlaydays", "awards",
    }
    standings_keys = {
        "player", "wins", "gamesPlayed", "pointsFor", "pointsAgainst",
        "pointDiff",
    }
    score_keys = {
        "date", "table", "game", "team1Players", "team2Players",
        "team1Score", "team2Score", "validScore",
    }
    for path, payload in first_files.items():
        if not path.startswith("seasons/"):
            continue
        assert set(payload) == season_keys
        assert all(set(row) == standings_keys for row in payload["standings"])
        assert all(set(row) == score_keys for row in payload["scores"])
        for day in payload["playdays"]:
            assert set(day) == {
                "date", "location", "playersPresent", "tables", "standings",
            }
            assert all(set(row) == standings_keys for row in day["standings"])
            for table in day["tables"]:
                assert set(table) == {
                    "table", "players", "location", "standings",
                }
                assert all(
                    set(row) == {"player", "wins", "losses"}
                    for row in table["standings"]
                )
        assert all(
            set(row) == {"date", "location", "playersPresent"}
            for row in payload["legacyPlaydays"]
        )
    assert tree_hash(data_dir) == before


def test_snapshot_refuses_to_overwrite_nonempty_output(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    output = tmp_path / "snapshot"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("do not remove", encoding="utf-8")

    try:
        generate_snapshot(data_dir, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected snapshot output directory rejection")

    assert marker.read_text(encoding="utf-8") == "do not remove"


def test_static_site_build_contains_only_derived_json_and_site_assets(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    before = tree_hash(data_dir)

    manifest = build_site(
        data_dir,
        tmp_path / "site-build",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    output = tmp_path / "site-build"
    files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }

    assert {
        "index.html",
        "styles.css",
        "app.js",
        "service-worker-cleanup.js",
        "favicon.svg",
        "data/manifest.json",
        "data/players.json",
    } <= files
    assert all(path.endswith(".json") or path in {
        "index.html", "styles.css", "app.js", "service-worker-cleanup.js",
        "favicon.svg",
    } for path in files)
    assert not any(path.endswith(".csv") for path in files)
    index = (output / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex">' in index
    assert '<link rel="icon" href="./favicon.svg" type="image/svg+xml">' in index
    site_assets = Path(__file__).resolve().parents[1] / "site"
    asset_digest = hashlib.sha256()
    for filename in (
        "index.html",
        "styles.css",
        "app.js",
        "service-worker-cleanup.js",
        "favicon.svg",
    ):
        asset_digest.update(filename.encode("utf-8"))
        asset_digest.update(b"\0")
        asset_digest.update((site_assets / filename).read_bytes())
        asset_digest.update(b"\0")
    asset_id = asset_digest.hexdigest()[:12]
    assert f"styles.css?v={manifest['buildId']}-{asset_id}" in index
    assert f"service-worker-cleanup.js?v={manifest['buildId']}-{asset_id}" in index
    assert f"app.js?v={manifest['buildId']}-{asset_id}" in index
    for filename in (
        "index.html",
        "styles.css",
        "app.js",
        "service-worker-cleanup.js",
        "favicon.svg",
    ):
        assert b"\r\n" not in (output / filename).read_bytes()
    cleanup_script = (output / "service-worker-cleanup.js").read_text(encoding="utf-8")
    assert 'key.endsWith(cacheSuffix)' in cleanup_script
    assert 'url.pathname.startsWith(appBase.pathname)' in cleanup_script
    assert tree_hash(data_dir) == before


def test_snapshot_generates_player_profile_files_and_allows_them_in_site_output(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)

    snapshot = generate_snapshot(data_dir, tmp_path / "snapshot")
    files = read_json_tree(tmp_path / "snapshot")
    profile = files["players/an.json"]

    assert profile["name"] == "An"
    assert profile["slug"] == "an"
    assert profile["gamesPlayed"] >= 1
    assert profile["wins"] >= 1
    assert "seasons" in profile

    site_dir = tmp_path / "site-output"
    build_site(data_dir, site_dir, generated_at=snapshot["generatedAt"])
    assert (site_dir / "data" / "players" / "an.json").is_file()


def test_static_site_refuses_nonempty_output_without_removing_files(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    output = tmp_path / "site-build"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    try:
        build_site(data_dir, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected static site output directory rejection")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_snapshot_archive_builds_a_json_only_site(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    before = tree_hash(data_dir)

    manifest, archive_bytes = _snapshot_archive_bytes(data_dir)
    archive_path = tmp_path / SNAPSHOT_ARCHIVE
    archive_path.write_bytes(archive_bytes)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = archive.namelist()
        assert "manifest.json" in members
        assert all(member.endswith(".json") for member in members)
        assert not any(member.endswith(".csv") for member in members)

    output = tmp_path / "site-from-archive"
    built_manifest = build_site_from_archive(archive_path, output)
    files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }

    assert built_manifest["buildId"] == manifest["buildId"]
    assert {
        "index.html",
        "styles.css",
        "app.js",
        "service-worker-cleanup.js",
        "favicon.svg",
        "data/manifest.json",
    } <= files
    assert all(path.endswith(".json") or path in {
        "index.html", "styles.css", "app.js", "service-worker-cleanup.js",
        "favicon.svg",
    } for path in files)
    assert tree_hash(data_dir) == before


def test_snapshot_archive_rejects_path_traversal_and_tampered_contents(tmp_path):
    output = tmp_path / "unsafe-site"
    traversal_archive = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_archive, "w") as archive:
        archive.writestr("../outside.json", "{}")

    with pytest.raises(ValueError, match="invalid file path"):
        build_site_from_archive(traversal_archive, output)
    assert not output.exists()

    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    _, archive_bytes = _snapshot_archive_bytes(data_dir)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = {
            name: archive.read(name)
            for name in archive.namelist()
        }
    members["pairings.json"] = b"[]\n"
    tampered_archive = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered_archive, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    with pytest.raises(ValueError, match="buildId"):
        build_site_from_archive(tampered_archive, output)
    assert not output.exists()


def test_publish_uploads_only_the_derived_archive_then_dispatches(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    before = tree_hash(data_dir)
    calls = []
    uploaded_archives = []

    def fake_request_json(request, allow_not_found=False):
        method = request.get_method()
        calls.append(method)
        assert request.get_header("Authorization") == "Bearer test-token"
        if method == "GET":
            assert allow_not_found
            assert request.full_url.endswith(f"/{SNAPSHOT_ARCHIVE}?ref=main")
            return 404, {}

        assert method == "PUT"
        assert request.full_url.endswith(f"/{SNAPSHOT_ARCHIVE}")
        payload = json.loads(request.data)
        with zipfile.ZipFile(
            io.BytesIO(base64.b64decode(payload["content"]))
        ) as archive:
            members = archive.namelist()
            assert all(member.endswith(".json") for member in members)
            assert not any(member.endswith(".csv") for member in members)
            uploaded_archives.append(members)
        assert payload["branch"] == "main"
        return 201, {}

    class DispatchResponse:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        assert timeout == 15
        assert request.get_method() == "POST"
        assert request.full_url.endswith("/actions/workflows/publish-mirror.yml/dispatches")
        assert json.loads(request.data) == {"ref": "main"}
        calls.append(request.get_method())
        return DispatchResponse()

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/manillen")
    monkeypatch.setenv("GITHUB_WORKFLOW", "publish-mirror.yml")
    monkeypatch.setenv("GITHUB_REF", "main")
    monkeypatch.setattr("github_publish._request_json", fake_request_json)
    monkeypatch.setattr("github_publish.urlopen", fake_urlopen)

    trigger_mirror_workflow(data_dir)

    assert calls == ["GET", "PUT", "POST"]
    assert len(uploaded_archives) == 1
    assert tree_hash(data_dir) == before


def test_publish_does_not_dispatch_when_archive_upload_fails(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    calls = []

    def failed_upload(request, allow_not_found=False):
        calls.append(request.get_method())
        if request.get_method() == "GET":
            assert allow_not_found
            return 404, {}
        raise GitHubPublishError("upload failed")

    def unexpected_dispatch(*_args, **_kwargs):
        raise AssertionError("workflow must not dispatch after an upload failure")

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/manillen")
    monkeypatch.setenv("GITHUB_WORKFLOW", "publish-mirror.yml")
    monkeypatch.setenv("GITHUB_REF", "main")
    monkeypatch.setattr("github_publish._request_json", failed_upload)
    monkeypatch.setattr("github_publish.urlopen", unexpected_dispatch)

    with pytest.raises(GitHubPublishError, match="upload failed"):
        trigger_mirror_workflow(data_dir)

    assert calls == ["GET", "PUT"]


def test_static_generator_runs_with_standard_library_only(tmp_path):
    data_dir = tmp_path / "data"
    make_snapshot_fixture(data_dir)
    script = Path(__file__).resolve().parents[1] / "generate_static_snapshot.py"
    output = tmp_path / "stdlib-snapshot"

    subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "--data-dir",
            str(data_dir),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output / "manifest.json").is_file()
    assert (output / "seasons" / "all.json").is_file()


def test_frontend_uses_safe_text_rendering_and_mobile_accessible_controls():
    root = Path(__file__).resolve().parents[1]
    index = (root / "site" / "index.html").read_text(encoding="utf-8")
    styles = (root / "site" / "styles.css").read_text(encoding="utf-8")
    app = (root / "site" / "app.js").read_text(encoding="utf-8")

    assert '<meta name="robots" content="noindex">' in index
    assert '<link rel="icon" href="./favicon.svg" type="image/svg+xml">' in index
    assert 'viewport-fit=cover' in index
    assert all(f'data-route="{route}"' in index for route in (
        "seizoenen",
        "hall-of-fame",
        "tussenstand",
        "speeldagen",
        "scores",
        "parenhistoriek",
    ))
    assert "innerHTML" not in app
    assert "textContent" in app
    assert "document.createElement" in app
    assert "min-height: 44px" in styles
    assert "font-size: 1rem" in styles
    assert 'id="theme-toggle"' in index
    assert 'aria-pressed="false"' in index
    assert "document.documentElement.dataset.theme = theme" in app
    assert "localStorage.setItem(themeStorageKey, theme)" in app
    assert "rank-gold" in app and "🥇" in app
    assert "rank-silver" in app and "🥈" in app
    assert "rank-bronze" in app and "🥉" in app
    assert "rank-lantern" in app and "🏮" in app
    assert "--rank-gold:" in styles and "--rank-lantern:" in styles
    assert 'prefers-color-scheme: dark' not in styles
    assert "prefers-reduced-motion: reduce" in styles
    assert "@media (min-width: 901px)" in styles
    assert "grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr))" in styles
