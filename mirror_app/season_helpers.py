"""Pure season, legacy award, and Hall of Fame helpers."""

import csv
import os
import shutil
import tempfile
from pathlib import Path

try:
    from .data_helpers import DEFAULT_SEASON, load_pairing_records
    from .score_helpers import compute_standings, load_scores
except ImportError:
    from data_helpers import DEFAULT_SEASON, load_pairing_records
    from score_helpers import compute_standings, load_scores


SEASONS_HEADER = ("Season", "SeasonNumber", "SeasonStartYear", "Status")
AWARD_FIELDS = ("Gold", "Silver", "Bronze", "RedLantern")
MIN_GAMES_FOR_AWARD = 3
LEGACY_SEASON_FILE = "seasons_history.csv"
LEGACY_PLAYDAYS_FILE = "seasons_playdays_legacy.csv"
HALL_OF_FAME_CHECK_FILE = "hall_of_fame_check.csv"


def _atomic_write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _ensure_preseason_backup(history_path):
    backup_path = Path(f"{history_path}.bak-pre-seasons")
    if backup_path.exists():
        if not backup_path.is_file():
            raise OSError(f"Season migration backup is not a file: {backup_path}")
        return backup_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with Path(history_path).open("rb") as source, backup_path.open("xb") as backup:
            created = True
            shutil.copyfileobj(source, backup)
            backup.flush()
            os.fsync(backup.fileno())
    except FileExistsError:
        pass
    except Exception:
        if created:
            backup_path.unlink(missing_ok=True)
        raise
    return backup_path


def migrate_pairing_history(history_path, default_season=DEFAULT_SEASON):
    """Back up and atomically add/fill the explicit Season column."""
    history_path = Path(history_path)
    if not history_path.exists():
        return False

    _ensure_preseason_backup(history_path)
    with history_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        original_fields = list(reader.fieldnames or [])
        if not original_fields:
            return False
        rows = list(reader)

    fields = original_fields + (["Season"] if "Season" not in original_fields else [])
    changed = "Season" not in original_fields
    for row in rows:
        for field in fields:
            row.setdefault(field, "")
        if not (row.get("Season") or "").strip():
            row["Season"] = default_season
            changed = True
    if changed:
        _atomic_write_csv(history_path, fields, rows)
    return changed


def ensure_season_data(data_dir):
    """Create the initial register and safely migrate an existing history file."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    seasons_path = data_dir / "seasons.csv"
    if not seasons_path.exists() or seasons_path.stat().st_size == 0:
        _atomic_write_csv(seasons_path, SEASONS_HEADER, [{
            "Season": DEFAULT_SEASON,
            "SeasonNumber": "11",
            "SeasonStartYear": "2026",
            "Status": "actief",
        }])
    migrate_pairing_history(data_dir / "pairings_history.csv")


def load_seasons(seasons_path):
    path = Path(seasons_path)
    if not path.exists():
        return []
    seasons = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            label = (row.get("Season") or "").strip()
            if not label:
                continue
            try:
                number = int(row.get("SeasonNumber", ""))
                start_year = int(row.get("SeasonStartYear", ""))
            except (TypeError, ValueError):
                continue
            seasons.append({
                "Season": label,
                "SeasonNumber": number,
                "SeasonStartYear": start_year,
                "Status": (row.get("Status") or "").strip().casefold(),
            })
    return sorted(seasons, key=lambda row: row["SeasonNumber"])


def get_active_season(seasons_path):
    active = [row for row in load_seasons(seasons_path) if row["Status"] == "actief"]
    if len(active) != 1:
        raise ValueError("Er moet precies één actief seizoen zijn.")
    return active[0]


def save_seasons(seasons_path, seasons):
    rows = [{
        "Season": row["Season"],
        "SeasonNumber": row["SeasonNumber"],
        "SeasonStartYear": row["SeasonStartYear"],
        "Status": row["Status"],
    } for row in seasons]
    _atomic_write_csv(seasons_path, SEASONS_HEADER, rows)


def next_season_values(seasons_path):
    seasons = load_seasons(seasons_path)
    if not seasons:
        return {"Season": DEFAULT_SEASON, "SeasonNumber": 11, "SeasonStartYear": 2026}
    number = max(row["SeasonNumber"] for row in seasons) + 1
    start_year = max(row["SeasonStartYear"] for row in seasons) + 1
    return {
        "Season": f"{start_year}-{start_year + 1}",
        "SeasonNumber": number,
        "SeasonStartYear": start_year,
    }


def append_season_and_close_current(seasons_path, new_label):
    seasons = load_seasons(seasons_path)
    active = [row for row in seasons if row["Status"] == "actief"]
    if len(active) != 1:
        raise ValueError("Er moet precies één actief seizoen zijn.")
    label = str(new_label).strip()
    if not label or any(row["Season"] == label for row in seasons):
        raise ValueError("Seizoensnaam is leeg of bestaat al.")
    next_values = next_season_values(seasons_path)
    for row in active:
        row["Status"] = "afgesloten"
    seasons.append({
        **next_values,
        "Season": label,
        "Status": "actief",
    })
    save_seasons(seasons_path, seasons)


def reopen_season(seasons_path, season_label):
    seasons = load_seasons(seasons_path)
    selected = next((row for row in seasons if row["Season"] == season_label), None)
    if selected is None or selected["Status"] != "afgesloten":
        raise ValueError("Alleen een bestaand afgesloten seizoen kan worden heropend.")
    if any(
        row["Status"] == "actief" and row["SeasonNumber"] > selected["SeasonNumber"]
        for row in seasons
    ):
        raise ValueError("Heropenen kan niet zolang een opvolgend seizoen actief is.")
    for row in seasons:
        if row["Status"] == "actief":
            row["Status"] = "afgesloten"
    selected["Status"] = "actief"
    save_seasons(seasons_path, seasons)


def season_for_date(history_path):
    return {row["Date"]: row["Season"] for row in load_pairing_records(history_path)}


def scores_for_season(scores_path, history_path, season_label):
    dates = {
        row["Date"]
        for row in load_pairing_records(history_path)
        if row["Season"] == season_label
    }
    return [row for row in load_scores(scores_path) if row["Date"] in dates]


def _canonical_player(name, pool_names):
    clean = " ".join(str(name).split())
    pool_by_fold = {player.casefold(): player for player in pool_names}
    if clean.casefold() in pool_by_fold:
        return pool_by_fold[clean.casefold()]
    if clean.casefold() == "fred g" and "frederik" in pool_by_fold:
        return pool_by_fold["frederik"]
    if clean.casefold() == "jp":
        return pool_by_fold.get("j.-p.", clean)
    shortened = clean.rsplit(" ", 1)[0] if " " in clean else clean
    if shortened.casefold() in pool_by_fold:
        return pool_by_fold[shortened.casefold()]
    if clean.endswith(" B") and shortened.casefold() == "johan":
        return pool_by_fold.get("johan", shortened)
    return shortened if shortened != clean else clean


def load_legacy_seasons(seasons_path, playdays_path=None, pool_players=None):
    path = Path(seasons_path)
    playdays_by_season = {}
    if playdays_path and Path(playdays_path).exists():
        with Path(playdays_path).open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                playdays_by_season.setdefault(row.get("Season", "").strip(), []).append(row)
    if not path.exists():
        return []
    result = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            try:
                pool_size = int(row.get("Pool", ""))
                number = int(row.get("SeasonNumber", ""))
            except (TypeError, ValueError):
                continue
            awards = {
                field: (row.get(field) or "").strip()
                for field in AWARD_FIELDS
            }
            if pool_players is not None:
                awards = {
                    field: " | ".join(
                        _canonical_player(name.strip(), pool_players)
                        for name in awards[field].split("|")
                        if name.strip()
                    )
                    for field in AWARD_FIELDS
                }
            result.append({
                "Season": (row.get("Season") or "").strip(),
                "SeasonNumber": number,
                "Pool": pool_size,
                **awards,
                "Playdays": playdays_by_season.get((row.get("Season") or "").strip(), []),
            })
    return result


def compute_legacy_hall_of_fame(seasons_path, pool_players):
    pool_players = list(dict.fromkeys(str(name).strip() for name in pool_players if str(name).strip()))
    totals = {
        name: {"Gold": 0, "Silver": 0, "Bronze": 0, "RedLantern": 0}
        for name in pool_players
    }
    for season in load_legacy_seasons(seasons_path):
        for field in AWARD_FIELDS:
            for legacy_name in season[field].split("|"):
                legacy_name = legacy_name.strip()
                if legacy_name:
                    name = _canonical_player(legacy_name, pool_players)
                    totals.setdefault(name, {award: 0 for award in AWARD_FIELDS})
                    totals[name][field] += 1
    return totals


def compute_tool_awards(standings, pool_players, minimum_games=MIN_GAMES_FOR_AWARD):
    pool_by_fold = {str(name).casefold(): str(name) for name in pool_players}
    eligible = [
        row for row in standings
        if row["player"].casefold() in pool_by_fold
        and row["games_played"] >= minimum_games
    ]
    eligible.sort(key=lambda row: (
        -row["wins"],
        -row["games_played"],
        -row["point_diff"],
        row["player"].casefold(),
    ))
    awards = {}
    for place, medal in enumerate(("Gold", "Silver", "Bronze")):
        if place < len(eligible):
            awards[medal] = pool_by_fold[eligible[place]["player"].casefold()]
    if eligible:
        awards["RedLantern"] = pool_by_fold[eligible[-1]["player"].casefold()]
    return awards


def compute_closed_season_awards(
    seasons_path,
    scores_path,
    history_path,
    pool_players,
    minimum_games=MIN_GAMES_FOR_AWARD,
):
    """Compute awards only for closed seasons from their score history."""
    result = []
    for season in load_seasons(seasons_path):
        if season["Status"] != "afgesloten":
            continue
        standings = compute_standings(
            str(scores_path),
            season=season["Season"],
            history_filename=str(history_path),
        )
        result.append((
            season["Season"],
            compute_tool_awards(standings, pool_players, minimum_games),
        ))
    return result


def compute_hall_of_fame(pool_players, legacy_seasons_path, tool_seasons=()):
    pool_players = list(dict.fromkeys(str(name).strip() for name in pool_players if str(name).strip()))
    totals = compute_legacy_hall_of_fame(legacy_seasons_path, pool_players)
    for season, awards in tool_seasons:
        for field in AWARD_FIELDS:
            name = awards.get(field)
            if name:
                totals.setdefault(name, {award: 0 for award in AWARD_FIELDS})[field] += 1
    return [
        {"Player": name, **awards, "InPool": name in pool_players}
        for name, awards in sorted(
            totals.items(),
            key=lambda item: (
                -item[1]["Gold"],
                -item[1]["Silver"],
                -item[1]["Bronze"],
                item[0].casefold(),
            ),
        )
    ]
