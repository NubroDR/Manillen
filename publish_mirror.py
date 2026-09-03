from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MIRROR = ROOT / "mirror_app"
DATA = MIRROR / "data"
OUTPUT = ROOT / "docs"
SNAPSHOT_FILES = ("pairings.csv", "pairings_history.csv", "scores_history.csv")
SOURCE_DATA = ROOT / "data"
PAGE_TITLE = "Manillen | Publieke mirror"


def _shinylive_command():
    candidates = [
        ROOT / ".venv" / "Scripts" / "shinylive.exe",
        Path(sys.executable).with_name("shinylive.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    command = shutil.which("shinylive")
    if command:
        return command
    raise FileNotFoundError(
        "Shinylive is niet gevonden. Activeer .venv en voer 'pip install shinylive' uit."
    )


def _set_page_title():
    index_file = OUTPUT / "index.html"
    content = index_file.read_text(encoding="utf-8")
    content = content.replace("<title>Shiny App</title>", f"<title>{PAGE_TITLE}</title>")
    index_file.write_text(content, encoding="utf-8")


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    copied = []
    for filename in SNAPSHOT_FILES:
        source = SOURCE_DATA / filename
        destination = DATA / filename
        if source.exists():
            shutil.copy2(source, destination)
            copied.append(filename)
        elif destination.exists():
            destination.unlink()
    subprocess.run([_shinylive_command(), "export", str(MIRROR), str(OUTPUT)], cwd=ROOT, check=True)
    _set_page_title()
    print("Mirror gepubliceerd als Shinylive-export.")
    print(f"Snapshots gekopieerd naar: {DATA}")
    print(f"Bestanden: {', '.join(copied) if copied else 'geen (bronbestanden ontbreken)'}")
    print(f"Export geschreven naar: {OUTPUT}")
    print("Voer daarna handmatig git add, git commit en git push uit.")


if __name__ == "__main__":
    main()