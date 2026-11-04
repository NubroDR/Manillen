import json
import os
from pathlib import Path

import pytest

from data_paths import DATA_DIR, active_data_dir, data_path, VERSIONED_FILES


def test_data_directory_uses_temporary_environment_override():
    configured_path = Path(os.environ["MANILLEN_DATA_DIR"]).resolve()

    assert DATA_DIR == configured_path
    assert DATA_DIR != (Path(__file__).resolve().parents[1] / "data").resolve()


def _activate_version(data_root, version_id="v_test123"):
    version_dir = data_root / "versions" / version_id
    version_dir.mkdir(parents=True)
    for filename in VERSIONED_FILES:
        content = f"{filename}\n".encode()
        (version_dir / filename).write_bytes(content)
    (data_root / "active-version.json").write_text(json.dumps({
        "manifest_version": 1,
        "active_version": version_id,
    }), encoding="utf-8")
    return version_dir


def test_data_path_uses_active_manifest_only_for_versioned_files(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    root_pairings = data_root / "pairings.csv"
    root_pairings.write_text("legacy", encoding="utf-8")
    root_template = data_root / "Scorebladen.xlsx"
    root_template.write_text("template", encoding="utf-8")
    version_dir = _activate_version(data_root)

    assert active_data_dir(data_root) == version_dir
    assert data_path("pairings.csv", data_root) == version_dir / "pairings.csv"
    assert data_path("Scorebladen.xlsx", data_root) == root_template
    assert root_pairings.read_text(encoding="utf-8") == "legacy"


def test_data_path_uses_legacy_root_when_manifest_is_absent(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()

    assert active_data_dir(data_root) == data_root
    assert data_path("pairings.csv", data_root) == data_root / "pairings.csv"


@pytest.mark.parametrize(
    ("manifest", "version_tree", "message"),
    [
        ("not-json", True, "Cannot read active-version manifest"),
        ({"manifest_version": 2, "active_version": "v_test123", "files": {}},
         True, "Unsupported active-version manifest"),
        ({"manifest_version": 1, "active_version": "../outside", "files": {}},
         True, "invalid version ID"),
        ({"manifest_version": 1, "active_version": "v_missing", "files": {}},
         True, "missing or outside"),
    ],
)
def test_invalid_active_manifest_fails_closed(
    tmp_path, manifest, version_tree, message
):
    data_root = tmp_path / "store"
    data_root.mkdir()
    if version_tree:
        _activate_version(data_root)
    contents = manifest if isinstance(manifest, str) else json.dumps(manifest)
    (data_root / "active-version.json").write_text(contents, encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        active_data_dir(data_root)


def test_active_manifest_requires_all_versioned_files(tmp_path):
    data_root = tmp_path / "store"
    data_root.mkdir()
    version_dir = _activate_version(data_root)
    (version_dir / "players.csv").unlink()

    with pytest.raises(RuntimeError, match="missing required files"):
        data_path("players.csv", data_root)


@pytest.mark.parametrize("filename", ["../pairings.csv", "folder\\scores.csv", ""])
def test_data_path_rejects_non_filename_input(tmp_path, filename):
    with pytest.raises(ValueError, match="simple filename"):
        data_path(filename, tmp_path)
