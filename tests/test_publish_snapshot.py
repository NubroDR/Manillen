from pathlib import Path

from github_publish import SNAPSHOT_ARCHIVE


def test_publisher_transfers_one_derived_snapshot_archive():
    assert SNAPSHOT_ARCHIVE == "static_snapshot.zip"


def test_docker_image_includes_the_generator_imports_used_by_publisher():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    contents = dockerfile.read_text(encoding="utf-8")

    assert "github_publish.py generate_static_snapshot.py ./" in contents
    assert "COPY manillen_core/ ./manillen_core/" in contents
