"""Assemble static mirror assets and a derived JSON snapshot in a new directory."""

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from data_paths import DATA_DIR
from generate_static_snapshot import generate_snapshot


ROOT = Path(__file__).resolve().parent
SITE_SOURCE = ROOT / "site"
SITE_ASSETS = (
    "index.html",
    "styles.css",
    "app.js",
    "service-worker-cleanup.js",
    "favicon.svg",
)
MANIFEST_FIELDS = {
    "schemaVersion",
    "generatedAt",
    "buildId",
    "activeSeason",
    "seasons",
}


def _reject_json_constant(value):
    raise ValueError(f"Invalid JSON number: {value}")


def _valid_snapshot_path(relative):
    path = PurePosixPath(relative)
    return (
        path.as_posix() == relative
        and path.suffix == ".json"
        and (
            relative in {
                "manifest.json",
                "players.json",
                "player-routes.json",
                "pairings.json",
                "hall-of-fame.json",
            }
            or (
                len(path.parts) == 2
                and path.parts[0] == "seasons"
                and ":" not in path.parts[1]
            )
            or (
                len(path.parts) == 2
                and path.parts[0] == "players"
                and ":" not in path.parts[1]
            )
        )
    )


def _read_snapshot(snapshot_dir):
    snapshot_dir = Path(snapshot_dir)
    files = {}
    paths = {}
    for path in sorted(snapshot_dir.rglob("*.json")):
        if path.is_symlink():
            raise ValueError(f"Snapshot may not contain symbolic links: {path}")
        relative = path.relative_to(snapshot_dir).as_posix()
        if not _valid_snapshot_path(relative):
            raise ValueError(f"Snapshot contains an unexpected path: {relative}")
        try:
            value = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"Invalid snapshot JSON: {relative}") from error
        paths[relative] = path
        if relative != "manifest.json":
            files[relative] = value

    manifest_path = paths.get("manifest.json")
    if manifest_path is None:
        raise ValueError("Snapshot is missing manifest.json.")
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(manifest, dict) or not MANIFEST_FIELDS.issubset(manifest):
        raise ValueError("Snapshot manifest does not match the required schema.")
    if manifest["schemaVersion"] != 1:
        raise ValueError("Unsupported snapshot schema version.")
    content = json.dumps(
        files,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected_build_id = hashlib.sha256(content).hexdigest()[:16]
    if manifest["buildId"] != expected_build_id:
        raise ValueError("Snapshot buildId does not match its JSON contents.")
    if len(paths) != len(files) + 1:
        raise ValueError("Snapshot contains duplicate or unexpected JSON files.")
    return manifest, paths


def _copy_site_assets(output_dir, build_id):
    assets = {}
    for filename in SITE_ASSETS:
        source = SITE_SOURCE / filename
        if not source.is_file():
            raise FileNotFoundError(f"Static site asset is missing: {source}")
        assets[filename] = source.read_bytes()

    asset_digest = hashlib.sha256()
    for filename, content in assets.items():
        asset_digest.update(filename.encode("utf-8"))
        asset_digest.update(b"\0")
        asset_digest.update(content)
        asset_digest.update(b"\0")
    asset_id = asset_digest.hexdigest()[:12]

    for filename, content in assets.items():
        text = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        if filename == "index.html":
            text = text.replace("{{BUILD_ID}}", build_id)
            text = text.replace("{{ASSET_ID}}", asset_id)
        (output_dir / filename).write_text(text, encoding="utf-8", newline="\n")


def _require_empty_output(output_dir):
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Site output directory must be empty: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def build_site(data_dir, output_dir, generated_at=None):
    output_dir = Path(output_dir)
    _require_empty_output(output_dir)
    manifest = generate_snapshot(
        data_dir,
        output_dir / "data",
        generated_at=generated_at,
    )
    _copy_site_assets(output_dir, manifest["buildId"])
    return manifest


def build_site_from_snapshot(snapshot_dir, output_dir):
    snapshot_dir = Path(snapshot_dir)
    manifest, files = _read_snapshot(snapshot_dir)
    if any(path.suffix != ".json" for path in snapshot_dir.rglob("*") if path.is_file()):
        raise ValueError("Snapshot may contain JSON files only.")

    output_dir = Path(output_dir)
    _require_empty_output(output_dir)
    for relative, source in files.items():
        destination = output_dir / "data" / Path(*PurePosixPath(relative).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    _copy_site_assets(output_dir, manifest["buildId"])
    return manifest


def build_site_from_archive(archive_path, output_dir):
    with tempfile.TemporaryDirectory(prefix="manillen-snapshot-") as temporary:
        snapshot_dir = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            seen = set()
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                relative = PurePosixPath(entry.filename)
                if (
                    relative.is_absolute()
                    or not relative.parts
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or "\\" in entry.filename
                    or ":" in entry.filename
                    or not _valid_snapshot_path(entry.filename)
                    or entry.filename in seen
                ):
                    raise ValueError("Snapshot archive contains an invalid file path.")
                seen.add(entry.filename)
                destination = snapshot_dir.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source:
                    destination.write_bytes(source.read())
        return build_site_from_snapshot(snapshot_dir, output_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assemble the read-only Manillen static mirror."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--data-dir", type=Path)
    source.add_argument("--snapshot-archive", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new, empty output directory for the static site",
    )
    args = parser.parse_args(argv)
    if args.snapshot_archive:
        manifest = build_site_from_archive(args.snapshot_archive, args.output)
    else:
        manifest = build_site(args.data_dir or DATA_DIR, args.output)
    print(f"Statische site gebouwd; buildId={manifest['buildId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
