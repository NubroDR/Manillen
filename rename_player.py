"""Rename a player without changing their stable ID or historical references."""

import argparse
import csv
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from data_paths import DATA_DIR, VERSIONED_FILES, active_data_dir, validate_active_data
from data_versions import _read_current_version, activate_staged_version
from manillen_core.reference_helpers import normalize_reference_name
from manillen_core.reference_adapter import ReferenceAdapter
from versioned_data import VERSIONED_SCHEMAS, validate_version_directory


def _read_csv(path, expected_headers):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != tuple(expected_headers):
            raise ValueError(f"Unexpected CSV schema: {Path(path).name}")
        return list(reader)


def _write_csv(path, headers, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def rename_player(data_root, player_id, new_name, backup_output):
    """Create and activate a renamed version after a verified full backup."""
    data_root = Path(data_root).resolve()
    current_version, manifest = _read_current_version(data_root)
    if current_version == "legacy" or manifest is None:
        raise ValueError("Player renames require an active ID-based data version.")

    active_dir = active_data_dir(data_root)
    actual_hashes = validate_active_data(data_root)
    if actual_hashes != manifest.get("files"):
        raise RuntimeError(
            "Active data differs from its manifest; refusing to rename a player."
        )

    new_name = str(new_name or "").strip()
    normalized_new_name = normalize_reference_name(new_name)
    if not normalized_new_name:
        raise ValueError("The new player name must not be empty.")

    adapter = ReferenceAdapter(data_root)
    old_name = adapter.player_name(player_id)
    if normalize_reference_name(old_name) == normalized_new_name:
        raise ValueError("The new name must differ from the current name.")
    try:
        mapped_id = adapter.player_id(new_name)
    except ValueError:
        mapped_id = None
    if mapped_id is not None and mapped_id != player_id:
        raise ValueError("The new name is already assigned to another player.")

    players = _read_csv(
        active_dir / "players.csv", VERSIONED_SCHEMAS["players.csv"]
    )
    matching_rows = [row for row in players if row["PlayerID"] == player_id]
    if len(matching_rows) != 1:
        raise ValueError("The requested player ID is not in the active dataset.")
    matching_rows[0]["Name"] = new_name

    aliases = _read_csv(
        active_dir / "player_aliases.csv",
        VERSIONED_SCHEMAS["player_aliases.csv"],
    )
    aliases = [
        row for row in aliases
        if normalize_reference_name(row["Alias"]) != normalized_new_name
    ]
    previous_name_alias = next((
        row for row in aliases
        if normalize_reference_name(row["Alias"])
        == normalize_reference_name(old_name)
        and row["PlayerID"] == player_id
    ), None)
    if previous_name_alias is None:
        aliases.append({
            "Alias": old_name,
            "PlayerID": player_id,
            "Source": "rename",
        })
    else:
        previous_name_alias["Source"] = "rename"

    with tempfile.TemporaryDirectory(prefix="manillen-player-rename-") as temp:
        staging_dir = Path(temp)
        for filename in VERSIONED_FILES:
            shutil.copyfile(active_dir / filename, staging_dir / filename)
        _write_csv(
            staging_dir / "players.csv",
            VERSIONED_SCHEMAS["players.csv"],
            players,
        )
        _write_csv(
            staging_dir / "player_aliases.csv",
            VERSIONED_SCHEMAS["player_aliases.csv"],
            aliases,
        )

        validation_hashes = validate_version_directory(staging_dir)
        version_id = f"v_{uuid.uuid4().hex[:12]}"
        (staging_dir / "staging-manifest.json").write_text(
            json.dumps({
                "version_id": version_id,
                "state": "staged_inactive",
                "files": validation_hashes,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = activate_staged_version(
            data_root,
            staging_dir,
            backup_output,
        )

    return {
        **result,
        "player_id": player_id,
        "old_name": old_name,
        "new_name": new_name,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rename a player while preserving their stable ID."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--player-id", required=True)
    parser.add_argument("--new-name", required=True)
    parser.add_argument("--backup-output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = rename_player(
        args.data_dir,
        args.player_id,
        args.new_name,
        args.backup_output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
