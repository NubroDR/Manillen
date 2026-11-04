import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _shell_paths():
    if os.name == "nt":
        git = shutil.which("git")
        if not git:
            pytest.skip("Git Bash is required to exercise docker-entrypoint.sh.")
        git_root = Path(git).resolve().parents[1]
        bash = git_root / "bin" / "bash.exe"
        cygpath = git_root / "usr" / "bin" / "cygpath.exe"
        if not bash.is_file() or not cygpath.is_file():
            pytest.skip("Git Bash and cygpath are required to exercise the entrypoint.")
        return [str(bash), "--noprofile", "--norc"], cygpath
    shell = shutil.which("sh")
    if not shell:
        pytest.skip("A POSIX shell is required to exercise docker-entrypoint.sh.")
    return [shell], None


def _shell_path(path, converter):
    if converter is None:
        return str(path)
    return subprocess.run(
        [str(converter), "-u", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_docker_entrypoint_seeds_only_missing_files_in_configured_data_dir(
    tmp_path,
):
    shell, converter = _shell_paths()
    repository = Path(__file__).resolve().parents[1]
    entrypoint = repository / "docker-entrypoint.sh"
    seed_dir = tmp_path / "image-seed"
    data_dir = tmp_path / "mounted-data"
    seed_dir.mkdir()
    data_dir.mkdir()
    existing_players = data_dir / "AllPlayers.csv"
    existing_players.write_text("User player\n", encoding="utf-8")
    (seed_dir / "AllPlayers.csv").write_text("Image seed\n", encoding="utf-8")
    (seed_dir / "pairings.csv").write_text(
        "Player1,Player2,Count\n", encoding="utf-8"
    )
    active_manifest = data_dir / "active-version.json"
    active_manifest.write_text('{"active_version":"v_active"}\n', encoding="utf-8")

    script = entrypoint.read_text(encoding="utf-8").replace(
        "/app/data-seed",
        _shell_path(seed_dir, converter),
    )
    test_entrypoint = tmp_path / "docker-entrypoint.sh"
    test_entrypoint.write_text(script, encoding="utf-8")
    environment = os.environ.copy()
    environment["MANILLEN_DATA_DIR"] = _shell_path(data_dir, converter)

    result = subprocess.run(
        shell + [
            _shell_path(test_entrypoint, converter),
            "sh",
            "-c",
            "printf entrypoint-started",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "entrypoint-started"
    assert existing_players.read_text(encoding="utf-8") == "User player\n"
    assert (data_dir / "pairings.csv").read_text(encoding="utf-8") == (
        "Player1,Player2,Count\n"
    )
    assert active_manifest.read_text(encoding="utf-8") == (
        '{"active_version":"v_active"}\n'
    )
    assert (data_dir / "Scorebladen").is_dir()
