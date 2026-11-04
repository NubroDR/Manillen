import csv
import json

import pytest

import data_versions
from data_paths import active_data_dir, assert_legacy_data_compatible
from generate_static_snapshot import build_snapshot
from migrate_ids import build_id_proposal, calculate_proposal_hash
from stage_ids import stage_id_migration
from test_migrate_ids import make_migration_fixture, tree_hashes
from versioned_data import validate_version_directory


def _make_staging(tmp_path, name="staging"):
    data_root = tmp_path / "store"
    make_migration_fixture(data_root)
    review_dir = tmp_path / f"{name}-review"
    review_dir.mkdir()
    proposal = build_id_proposal(data_root)
    for player in proposal["players"]:
        if player["PoolMember"] == 0:
            player["Active"] = 1
    for location in proposal["locations"]:
        location["Active"] = 1
    proposal["proposal_sha256"] = calculate_proposal_hash(proposal)
    proposal_path = review_dir / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    approval_path = review_dir / "approval.json"
    approval_path.write_text(json.dumps({
        "status": "approved",
        "proposal_sha256": proposal["proposal_sha256"],
        "approved_by": "test reviewer",
        "approved_at": "2026-11-04T10:00:00+01:00",
    }), encoding="utf-8")
    staging_dir = tmp_path / f"{name}-output"
    stage_id_migration(data_root, proposal_path, approval_path, staging_dir)
    return data_root, staging_dir


def test_full_backup_is_unique_complete_and_verified(tmp_path):
    data_root, _ = _make_staging(tmp_path)
    original_hashes = tree_hashes(data_root)
    backup_path = tmp_path / "backups" / "before-migration"
    backup_path.parent.mkdir()

    result = data_versions.create_full_backup(data_root, backup_path)

    assert result["files"] == len(original_hashes)
    assert tree_hashes(backup_path) == original_hashes
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        data_versions.create_full_backup(data_root, backup_path)
    assert tree_hashes(data_root) == original_hashes


def test_full_backup_refuses_insufficient_space_and_unsafe_paths(tmp_path, monkeypatch):
    data_root, _ = _make_staging(tmp_path)
    parent = tmp_path / "backups"
    parent.mkdir()
    monkeypatch.setattr(
        data_versions.shutil,
        "disk_usage",
        lambda path: type("Usage", (), {"free": 0})(),
    )
    with pytest.raises(OSError, match="Insufficient free space"):
        data_versions.create_full_backup(data_root, parent / "backup")
    with pytest.raises(ValueError, match="outside the datastore"):
        data_versions.create_full_backup(data_root, data_root / "backup")


def test_full_backup_failure_leaves_no_partial_backup(tmp_path, monkeypatch):
    data_root, _ = _make_staging(tmp_path)
    backup_parent = tmp_path / "backups"
    backup_parent.mkdir()
    backup_path = backup_parent / "failed-copy"

    def fail_copy(*args, **kwargs):
        raise OSError("simulated backup failure")

    monkeypatch.setattr(data_versions.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="simulated backup failure"):
        data_versions.create_full_backup(data_root, backup_path)
    assert not backup_path.exists()
    assert not list(backup_parent.iterdir())


def test_activation_backs_up_before_atomic_switch_and_legacy_app_fails_closed(
    tmp_path,
):
    data_root, staging_dir = _make_staging(tmp_path)
    original_hashes = tree_hashes(data_root)
    backup_path = tmp_path / "backups" / "before-activation"
    backup_path.parent.mkdir()

    result = data_versions.activate_staged_version(
        data_root, staging_dir, backup_path
    )

    active = result["manifest"]
    assert tree_hashes(backup_path) == original_hashes
    assert active_data_dir(data_root) == data_root / "versions" / active["active_version"]
    assert active["previous_version"] == "legacy"
    assert set(active["files"]) == set(active["row_counts"])
    with pytest.raises(RuntimeError, match="legacy name-based CSV schema"):
        assert_legacy_data_compatible(data_root)
    assert (data_root / "pairings.csv").is_file()
    assert (data_root / "versions" / active["active_version"] / "pairings.csv").is_file()
    with pytest.raises(RuntimeError, match="legacy name-based CSV schema"):
        build_snapshot(data_root)


def test_staging_validator_rejects_unknown_references(tmp_path):
    _, staging_dir = _make_staging(tmp_path)
    pairings_path = staging_dir / "pairings_history.csv"
    pairings_path.write_text(
        pairings_path.read_text(encoding="utf-8").replace(
            "RESERVE:1", "plr_aaaaa"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown player reference"):
        validate_version_directory(staging_dir)


def test_interruption_before_manifest_replace_leaves_legacy_version_active(
    tmp_path, monkeypatch
):
    data_root, staging_dir = _make_staging(tmp_path)
    backup_path = tmp_path / "backups" / "before-interrupted-switch"
    backup_path.parent.mkdir()
    real_replace = data_versions.os.replace

    def interrupt_manifest_replace(source, destination):
        if str(destination).endswith("active-version.json"):
            raise OSError("simulated interruption before atomic switch")
        return real_replace(source, destination)

    monkeypatch.setattr(data_versions.os, "replace", interrupt_manifest_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        data_versions.activate_staged_version(
            data_root, staging_dir, backup_path
        )

    assert active_data_dir(data_root) == data_root
    assert not (data_root / "active-version.json").exists()
    assert backup_path.is_dir()
    assert list((data_root / "versions").iterdir())


def test_rollback_to_legacy_after_backup_without_new_data(tmp_path):
    data_root, staging_dir = _make_staging(tmp_path)
    activation_backup = tmp_path / "backups" / "activate"
    activation_backup.parent.mkdir()
    data_versions.activate_staged_version(data_root, staging_dir, activation_backup)

    rollback = data_versions.rollback_active_version(
        data_root,
        tmp_path / "backups" / "rollback",
    )

    assert rollback["manifest"]["active_version"] == "legacy"
    assert active_data_dir(data_root) == data_root
    assert (data_root / "active-version.json").is_file()
    assert (tmp_path / "backups" / "rollback").is_dir()


def test_rollback_reports_new_rows_and_requires_explicit_data_loss_confirmation(
    tmp_path,
):
    data_root, staging_dir = _make_staging(tmp_path)
    backups = tmp_path / "backups"
    backups.mkdir()
    data_versions.activate_staged_version(
        data_root, staging_dir, backups / "activate"
    )
    scores_path = active_data_dir(data_root) / "scores_history.csv"
    with (active_data_dir(data_root) / "players.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        players_by_name = {
            row["Name"]: row["PlayerID"] for row in csv.DictReader(file)
        }
    with scores_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "2026-01-02", "1", "2",
            f"{players_by_name['Alice']} | RESERVE:1",
            f"{players_by_name['Bob']} | {players_by_name['Guest']}",
            "101", "50",
        ])

    with pytest.raises(ValueError, match="scores_history.csv"):
        data_versions.rollback_active_version(
            data_root, backups / "rollback-refused"
        )
    assert not (backups / "rollback-refused").exists()

    rollback = data_versions.rollback_active_version(
        data_root,
        backups / "rollback-confirmed",
        confirm_data_loss=True,
    )
    assert rollback["changes"]["scores_history.csv"] == {
        "rows_at_activation": 1,
        "rows_now": 2,
    }
    assert active_data_dir(data_root) == data_root
