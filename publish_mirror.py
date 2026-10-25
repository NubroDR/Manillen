"""Build a static mirror from a local datastore or a derived snapshot archive."""

import argparse
from pathlib import Path

from build_static_site import build_site, build_site_from_archive
from data_paths import DATA_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the read-only Manillen static mirror."
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
    print(f"Statische mirror gebouwd; buildId={manifest['buildId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
