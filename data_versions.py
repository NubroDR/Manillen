"""Back up, activate, and roll back validated versioned datastore snapshots."""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from data_paths import (
    ACTIVE_VERSION_MANIFEST,
    DATA_DIR,
    VERSIONED_FILES,
    active_data_dir,
    validate_active_data,
)
from versioned_data import validate_version_directory

_VERSION_ID = re.compile(r"^v_[A-Za-z0-9_-]+$")


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(directory):
    directory = Path(directory)
    hashes = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Refusing to back up symlink: {path}")
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = _file_hash(path)
    return hashes


def _tree_size(directory):
    return sum(
        path.stat().st_size
        for path in Path(directory).rglob("*")
        if path.is_file()
    )


def _assert_external_path(path, data_root):
    path = Path(path).resolve()
    data_root = Path(data_root).resolve()
    repository = Path(__file__).resolve().parent
    if path == data_root or data_root in path.parents:
        raise ValueError("Backup and staging outputs must be outside the datastore.")
    if path == repository or repository in path.parents:
        raise ValueError("Backup and staging outputs must be outside the repository.")
    return path


def create_full_backup(data_root, backup_output):
    """Create and verify a unique, complete copy of the datastore."""
    data_root = Path(data_root).resolve()
    backup_output = _assert_external_path(backup_output, data_root)
    if not data_root.is_dir():
        raise FileNotFoundError(f"Datastore directory does not exist: {data_root}")
    if backup_output.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {backup_output}")
    if not backup_output.parent.is_dir():
        raise FileNotFoundError(
            f"Backup parent directory does not exist: {backup_output.parent}"
        )

    before = _tree_hashes(data_root)
    required_bytes = _tree_size(data_root)
    if shutil.disk_usage(backup_output.parent).free < required_bytes:
        raise OSError("Insufficient free space for a full datastore backup.")

    temporary_parent = Path(tempfile.mkdtemp(
        prefix=f".{backup_output.name}.backup-",
        dir=backup_output.parent,
    ))
    temporary_backup = temporary_parent / "snapshot"
    try:
        shutil.copytree(data_root, temporary_backup)
        if _tree_hashes(temporary_backup) != before:
            raise RuntimeError("Backup verification failed; source changed or copy differs.")
        if _tree_hashes(data_root) != before:
            raise RuntimeError("Datastore changed while the backup was being created.")
        if backup_output.exists():
            raise FileExistsError(f"Refusing to overwrite backup: {backup_output}")
        os.rename(temporary_backup, backup_output)
    finally:
        if temporary_parent.exists():
            shutil.rmtree(temporary_parent)
    return {
        "path": str(backup_output),
        "files": len(before),
        "bytes": required_bytes,
    }


def _read_staging_manifest(staging_dir):
    staging_dir = Path(staging_dir).resolve()
    manifest_path = staging_dir / "staging-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Cannot read staging manifest.") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("state") != "staged_inactive"
        or not isinstance(manifest.get("version_id"), str)
        or not _VERSION_ID.fullmatch(manifest["version_id"])
    ):
        raise ValueError("Staging manifest is invalid or not inactive.")

    actual_hashes = validate_version_directory(staging_dir)
    if manifest.get("files") != actual_hashes:
        raise ValueError("Staging file hashes do not match the staging manifest.")
    return manifest, staging_dir


def _read_current_version(data_root):
    manifest_path = Path(data_root) / ACTIVE_VERSION_MANIFEST
    if not manifest_path.exists():
        return "legacy", None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Cannot read the current active-version manifest.") from error
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != 1:
        raise RuntimeError("Current active-version manifest is invalid.")
    current_version = manifest.get("active_version")
    if current_version != "legacy" and (
        not isinstance(current_version, str) or not _VERSION_ID.fullmatch(current_version)
    ):
        raise RuntimeError("Current active-version ID is invalid.")
    active_data_dir(data_root)
    if current_version != "legacy":
        validate_active_data(data_root)
    return current_version, manifest


def _atomic_write_manifest(data_root, manifest):
    data_root = Path(data_root)
    temporary = data_root / f".{ACTIVE_VERSION_MANIFEST}.{uuid.uuid4().hex}.tmp"
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, data_root / ACTIVE_VERSION_MANIFEST)
    finally:
        temporary.unlink(missing_ok=True)


def activate_staged_version(data_root, staging_dir, backup_output):
    """Back up the datastore, install a staged version, then switch one manifest."""
    data_root = Path(data_root).resolve()
    staging_dir = _assert_external_path(staging_dir, data_root)
    if not data_root.is_dir():
        raise FileNotFoundError(f"Datastore directory does not exist: {data_root}")
    staging_manifest, staging_dir = _read_staging_manifest(staging_dir)
    current_version, _ = _read_current_version(data_root)
    version_id = staging_manifest["version_id"]
    versions_dir = data_root / "versions"
    if versions_dir.is_symlink():
        raise ValueError("The versions directory must not be a symlink.")
    version_output = versions_dir / version_id
    if version_output.exists():
        raise FileExistsError(f"Version already exists; refusing overwrite: {version_id}")
    backup = create_full_backup(data_root, backup_output)

    versions_dir.mkdir(exist_ok=True)
    temporary_version = versions_dir / f".{version_id}.{uuid.uuid4().hex}.tmp"
    try:
        shutil.copytree(
            staging_dir,
            temporary_version,
            ignore=shutil.ignore_patterns("staging-manifest.json"),
        )
        hashes = validate_version_directory(temporary_version)
        if hashes != staging_manifest["files"]:
            raise RuntimeError("Installed version does not match validated staging data.")
        if version_output.exists():
            raise FileExistsError(
                f"Version appeared during activation; refusing overwrite: {version_id}"
            )
        os.rename(temporary_version, version_output)
    finally:
        if temporary_version.exists():
            shutil.rmtree(temporary_version)

    active_manifest = {
        "manifest_version": 1,
        "active_version": version_id,
        "previous_version": current_version,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "files": hashes,
        "row_counts": {
            filename: _csv_row_count(version_output / filename)
            for filename in VERSIONED_FILES
        },
        "backup_path": backup["path"],
    }
    _atomic_write_manifest(data_root, active_manifest)
    validate_active_data(data_root)
    return {"manifest": active_manifest, "backup": backup}


def _csv_row_count(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        return max(sum(1 for _ in csv.reader(file)) - 1, 0)


def _active_data_changes(data_root, manifest):
    version_dir = Path(data_root) / "versions" / manifest["active_version"]
    current_hashes = {
        filename: _file_hash(version_dir / filename)
        for filename in VERSIONED_FILES
    }
    expected_hashes = manifest.get("files", {})
    changed = {}
    for filename in sorted(VERSIONED_FILES):
        if current_hashes[filename] != expected_hashes.get(filename):
            changed[filename] = {
                "rows_at_activation": manifest.get("row_counts", {}).get(filename),
                "rows_now": _csv_row_count(version_dir / filename),
            }
    return changed


def rollback_active_version(data_root, backup_output, confirm_data_loss=False):
    """Switch back atomically, requiring explicit consent if active files changed."""
    data_root = Path(data_root).resolve()
    current_version, manifest = _read_current_version(data_root)
    if manifest is None or current_version == "legacy":
        raise ValueError("There is no active version to roll back.")
    previous_version = manifest.get("previous_version")
    if not isinstance(previous_version, str):
        raise ValueError("Active manifest has no rollback version.")
    if previous_version != "legacy" and not _VERSION_ID.fullmatch(previous_version):
        raise ValueError("Active manifest has an invalid rollback version.")
    if previous_version != "legacy":
        previous_dir = Path(data_root) / "versions" / previous_version
        if not previous_dir.is_dir():
            raise RuntimeError(f"Rollback version is missing: {previous_version}")
        previous_hashes = validate_version_directory(previous_dir)
    else:
        previous_hashes = {}

    changes = _active_data_changes(data_root, manifest)
    if changes and not confirm_data_loss:
        raise ValueError(
            "Active data changed after activation; rollback would discard changes: "
            + json.dumps(changes, sort_keys=True)
            + ". Re-run with explicit data-loss confirmation only after reviewing."
        )

    backup = create_full_backup(data_root, backup_output)
    if previous_version == "legacy":
        rollback_manifest = {
            "manifest_version": 1,
            "active_version": "legacy",
            "previous_version": current_version,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "files": {},
            "row_counts": {},
            "backup_path": backup["path"],
        }
    else:
        rollback_manifest = {
            "manifest_version": 1,
            "active_version": previous_version,
            "previous_version": current_version,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            "files": previous_hashes,
            "row_counts": {
                filename: _csv_row_count(previous_dir / filename)
                for filename in VERSIONED_FILES
            },
            "backup_path": backup["path"],
        }
    _atomic_write_manifest(data_root, rollback_manifest)
    validate_active_data(data_root)
    return {"manifest": rollback_manifest, "backup": backup, "changes": changes}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Back up and manage versioned Manillen data snapshots."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    activate = commands.add_parser("activate")
    activate.add_argument("--data-dir", type=Path, default=DATA_DIR)
    activate.add_argument("--staging", type=Path, required=True)
    activate.add_argument("--backup-output", type=Path, required=True)
    activate.add_argument("--confirm", action="store_true", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--data-dir", type=Path, default=DATA_DIR)
    rollback.add_argument("--backup-output", type=Path, required=True)
    rollback.add_argument("--confirm-data-loss", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "activate":
        result = activate_staged_version(
            args.data_dir, args.staging, args.backup_output
        )
    else:
        result = rollback_active_version(
            args.data_dir,
            args.backup_output,
            confirm_data_loss=args.confirm_data_loss,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
