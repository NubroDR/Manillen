import os
from pathlib import Path

from data_paths import DATA_DIR


def test_data_directory_uses_temporary_environment_override():
    configured_path = Path(os.environ["MANILLEN_DATA_DIR"]).resolve()

    assert DATA_DIR == configured_path
    assert DATA_DIR != (Path(__file__).resolve().parents[1] / "data").resolve()
