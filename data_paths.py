"""Resolve the writable application's persistent data directory."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MANILLEN_DATA_DIR", BASE_DIR / "data")).resolve()
