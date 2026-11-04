"""Resolve the datastore root and its active, versioned data files."""

import json
import os
import re
from pathlib import Path

from versioned_data import VERSIONED_SCHEMAS, validate_version_directory


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MANILLEN_DATA_DIR", BASE_DIR / "data")).resolve()
ACTIVE_VERSION_MANIFEST = "active-version.json"
VERSIONED_FILES = frozenset(VERSIONED_SCHEMAS)
_VERSION_ID_PATTERN = re.compile(r"^v_[A-Za-z0-9_-]+$")


def active_data_dir(data_root=DATA_DIR):
    """Return the directory selected by the active manifest, or the legacy root."""
    data_root = Path(data_root).resolve()
    manifest_path = data_root / ACTIVE_VERSION_MANIFEST
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return data_root
    if not manifest_path.is_file():
        raise RuntimeError(f"Active-version manifest is not a file: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Cannot read active-version manifest: {manifest_path}"
        ) from error
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != 1:
        raise RuntimeError(f"Unsupported active-version manifest: {manifest_path}")

    version_id = manifest.get("active_version")
    if version_id == "legacy":
        return data_root
    if not isinstance(version_id, str) or not _VERSION_ID_PATTERN.fullmatch(version_id):
        raise RuntimeError("Active-version manifest contains an invalid version ID.")
    version_dir = data_root / "versions" / version_id
    resolved_version_dir = version_dir.resolve()
    if (
        version_dir.is_symlink()
        or data_root not in resolved_version_dir.parents
        or not resolved_version_dir.is_dir()
    ):
        raise RuntimeError(
            f"Active data version is missing or outside the datastore: {version_id}"
        )

    missing_files = sorted(
        filename for filename in VERSIONED_FILES
        if not (resolved_version_dir / filename).is_file()
    )
    if missing_files:
        raise RuntimeError(
            "Active data version is missing required files: "
            + ", ".join(missing_files)
        )
    return resolved_version_dir


def validate_active_data(data_root=DATA_DIR):
    """Validate schemas and references in the active version, when one exists."""
    data_root = Path(data_root).resolve()
    directory = active_data_dir(data_root)
    if directory == data_root and not (data_root / ACTIVE_VERSION_MANIFEST).is_file():
        return None
    if directory == data_root:
        return None
    try:
        return validate_version_directory(directory)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Active data version failed validation: {error}") from error


def assert_legacy_data_compatible(data_root=DATA_DIR):
    """Stop legacy-only readers from silently using stale root CSVs after activation."""
    data_root = Path(data_root).resolve()
    manifest_path = data_root / ACTIVE_VERSION_MANIFEST
    if not manifest_path.exists():
        return
    if manifest_path.is_symlink():
        raise RuntimeError("Cannot verify active data through a symlinked manifest.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Cannot verify active data version for this application.") from error
    if not isinstance(manifest, dict) or manifest.get("active_version") != "legacy":
        raise RuntimeError(
            "An ID-based data version is active, but this application path still "
            "uses the legacy name-based CSV schema. Refusing to read or write stale "
            "datastore-root files."
        )


def data_path(filename, data_root=DATA_DIR):
    """Resolve a file to its active version or to the datastore root."""
    filename = os.fspath(filename)
    if Path(filename).name != filename or filename in ("", ".", ".."):
        raise ValueError(f"Data filename must be a simple filename: {filename!r}")
    data_root = Path(data_root).resolve()
    if filename in VERSIONED_FILES:
        return active_data_dir(data_root) / filename
    return data_root / filename
