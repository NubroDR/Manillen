import csv
import hashlib
import json
from pathlib import Path

import pytest

from migrate_ids import build_id_proposal, calculate_proposal_hash
from stage_ids import VERSIONED_SCHEMAS, stage_id_migration
from test_migrate_ids import make_migration_fixture, tree_hashes


def _proposal_hash(proposal):
    return calculate_proposal_hash(proposal)


def _write_reviewed_inputs(data_dir, review_dir, resolve_status=True):
    review_dir.mkdir()
    proposal = build_id_proposal(data_dir)
    if resolve_status:
        for player in proposal["players"]:
            if player["PoolMember"] == 0:
                player["Active"] = 1
        for location in proposal["locations"]:
            location["Active"] = 1
    proposal["proposal_sha256"] = _proposal_hash(proposal)
    proposal_path = review_dir / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    approval_path = review_dir / "approval.json"
    approval_path.write_text(json.dumps({
        "status": "approved",
        "proposal_sha256": proposal["proposal_sha256"],
        "approved_by": "test reviewer",
        "approved_at": "2026-11-04T10:00:00+01:00",
    }), encoding="utf-8")
    return proposal, proposal_path, approval_path


def _read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_stage_requires_explicit_approval_and_resolved_review(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    before = tree_hashes(data_dir)
    review_dir = tmp_path / "review"
    proposal, proposal_path, approval_path = _write_reviewed_inputs(
        data_dir, review_dir
    )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["status"] = "pending"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")

    with pytest.raises(ValueError, match="explicitly approved"):
        stage_id_migration(
            data_dir, proposal_path, approval_path, tmp_path / "staging"
        )
    assert tree_hashes(data_dir) == before
    assert not (tmp_path / "staging").exists()

    approval["status"] = "approved"
    approval["proposal_sha256"] = "0" * 64
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        stage_id_migration(
            data_dir, proposal_path, approval_path, tmp_path / "staging"
        )

    unresolved_dir = tmp_path / "review-unresolved"
    _, proposal_path, approval_path = _write_reviewed_inputs(
        data_dir, unresolved_dir, resolve_status=False
    )
    with pytest.raises(ValueError, match="reviewed Active"):
        stage_id_migration(
            data_dir, proposal_path, approval_path, tmp_path / "staging-unresolved"
        )


def test_stage_transforms_and_validates_an_inactive_version_without_mutating_sources(
    tmp_path,
):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    pairings_path = data_dir / "pairings.csv"
    pairings_path.write_text(
        pairings_path.read_text(encoding="utf-8").replace(",0\n", ",3\n"),
        encoding="utf-8",
    )
    before = tree_hashes(data_dir)
    review_dir = tmp_path / "private-review"
    proposal, proposal_path, approval_path = _write_reviewed_inputs(
        data_dir, review_dir
    )
    output = tmp_path / "staging-version"

    manifest = stage_id_migration(data_dir, proposal_path, approval_path, output)

    player_ids = {row["Name"]: row["PlayerID"] for row in proposal["players"]}
    location_id = proposal["locations"][0]["LocationID"]
    assert manifest["state"] == "staged_inactive"
    assert manifest["proposal_sha256"] == proposal["proposal_sha256"]
    assert manifest["validation"]["source_rows"]["scores_history.csv"] == 1
    assert manifest["validation"]["staged_rows"]["scores_history.csv"] == 1
    assert manifest["validation"]["pairing_count_totals"] == 3
    assert manifest["validation"]["score_points_total"] == 151
    assert manifest["validation"]["partner_counts"] == {
        "|".join(sorted((player_ids["Alice"], player_ids["Bob"]))): 3
    }
    assert set(manifest["files"]) == set(VERSIONED_SCHEMAS)

    assert {path.name for path in output.iterdir()} == (
        set(VERSIONED_SCHEMAS) | {"staging-manifest.json"}
    )
    assert _read_rows(output / "players.csv")
    pairing = _read_rows(output / "pairings_history.csv")[0]
    assert pairing["Players"] == " | ".join((
        player_ids["Alice"], player_ids["Bob"], player_ids["Casey"], "RESERVE:1"
    ))
    assert pairing["Location"] == location_id
    score = _read_rows(output / "scores_history.csv")[0]
    assert score["Team1Players"] == f"{player_ids['Alice']} | RESERVE:1"
    assert score["Team2Players"] == f"{player_ids['Bob']} | {player_ids['Guest']}"
    assignment = _read_rows(output / "reserve_assignments.csv")[0]
    assert assignment == {
        "Date": "2026-01-02",
        "Slot": "RESERVE:1",
        "PlayerID": player_ids["Guest"],
    }
    staged_pairing = _read_rows(output / "pairings.csv")[0]
    assert staged_pairing == {
        "Player1": min(player_ids["Alice"], player_ids["Bob"]),
        "Player2": max(player_ids["Alice"], player_ids["Bob"]),
        "Count": "3",
    }
    assert tree_hashes(data_dir) == before
    assert not (output / "AllPlayers.csv").exists()
    assert not (output / "seasons_history.csv").exists()
    assert not (output / "Scorebladen.xlsx").exists()


def test_stage_rejects_stale_or_tampered_approval_and_preserves_no_partial_output(
    tmp_path,
):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    review_dir = tmp_path / "review"
    _, proposal_path, approval_path = _write_reviewed_inputs(data_dir, review_dir)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["players"][0]["Name"] = "Changed name"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    output = tmp_path / "stage"
    with pytest.raises(ValueError, match="integrity hash"):
        stage_id_migration(data_dir, proposal_path, approval_path, output)
    assert not output.exists()

    _, proposal_path, approval_path = _write_reviewed_inputs(
        data_dir, tmp_path / "review-stale"
    )
    with (data_dir / "scores_history.csv").open("a", encoding="utf-8") as file:
        file.write("")
    (data_dir / "scores_history.csv").write_text(
        (data_dir / "scores_history.csv").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="changed since"):
        stage_id_migration(data_dir, proposal_path, approval_path, output)
    assert not output.exists()


def test_stage_refuses_overwrite_and_repository_or_datastore_paths(tmp_path):
    data_dir = tmp_path / "source"
    make_migration_fixture(data_dir)
    _, proposal_path, approval_path = _write_reviewed_inputs(
        data_dir, tmp_path / "review"
    )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        stage_id_migration(data_dir, proposal_path, approval_path, existing)
    with pytest.raises(ValueError, match="outside the active data directory"):
        stage_id_migration(
            data_dir, proposal_path, approval_path, data_dir / "staging"
        )
    repository_output = (
        Path(__file__).resolve().parents[1] / "tests" / f"stage-{tmp_path.name}"
    )
    with pytest.raises(ValueError, match="outside the repository"):
        stage_id_migration(
            data_dir, proposal_path, approval_path, repository_output
        )
