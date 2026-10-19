import atexit
import os
import shutil
import tempfile
from pathlib import Path


_isolated_data_dir = Path(tempfile.mkdtemp(prefix="manillen-pytest-data-"))
os.environ["MANILLEN_DATA_DIR"] = str(_isolated_data_dir)
atexit.register(shutil.rmtree, _isolated_data_dir, ignore_errors=True)
