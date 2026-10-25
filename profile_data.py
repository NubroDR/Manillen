"""Read-only data and repository profiling for the ID migration baseline."""

import argparse
import ast
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

from data_paths import DATA_DIR


CSV_SCHEMAS = {
    "pairings.csv": ("Player1", "Player2", "Count"),
    "pairings_history.csv": ("Date", "Table", "Players", "Season", "Location"),
    "scores_history.csv": (
        "Date",
        "Table",
        "Game",
        "Team1Players",
        "Team2Players",
        "Team1Score",
        "Team2Score",
    ),
    "reserve_assignments.csv": ("Date", "Slot", "Name"),
    "seasons.csv": ("Season", "SeasonNumber", "SeasonStartYear", "Status"),
    "seasons_history.csv": (
        "Season",
        "SeasonNumber",
        "Pool",
        "Gold",
        "Silver",
        "Bronze",
        "RedLantern",
    ),
    "seasons_playdays_legacy.csv": (
        "Season",
        "Date",
        "Location",
        "PlayersPresent",
        "Pool",
    ),
}

CSV_ROUTE_INVENTORY = (
    {
        "file": "AllPlayers.csv",
        "role": "player pool input",
        "read_by": ["manillen_functions.py"],
        "written_by": [],
    },
    {
        "file": "pairings.csv",
        "role": "partner counts",
        "read_by": ["manillen_functions.py"],
        "written_by": ["manillen_functions.py"],
    },
    {
        "file": "pairings_history.csv",
        "role": "saved tables",
        "read_by": ["app.py", "manillen_functions.py", "reserve_assignments.py"],
        "written_by": ["manillen_functions.py"],
    },
    {
        "file": "scores_history.csv",
        "role": "saved scores",
        "read_by": ["app.py", "score_functions.py"],
        "written_by": ["score_functions.py"],
    },
    {
        "file": "reserve_assignments.csv",
        "role": "date-bound reserve names",
        "read_by": ["app.py", "reserve_assignments.py"],
        "written_by": ["reserve_assignments.py"],
    },
    {
        "file": "seasons.csv",
        "role": "season register",
        "read_by": ["app.py", "mirror_app/season_helpers.py"],
        "written_by": ["mirror_app/season_helpers.py"],
    },
    {
        "file": "seasons_history.csv",
        "role": "legacy awards",
        "read_by": ["app.py", "mirror_app/season_helpers.py"],
        "written_by": [],
    },
    {
        "file": "seasons_playdays_legacy.csv",
        "role": "legacy playday metadata",
        "read_by": ["app.py", "mirror_app/season_helpers.py"],
        "written_by": [],
    },
)

VERSIONED_CSV_CANDIDATES = (
    "pairings.csv",
    "pairings_history.csv",
    "scores_history.csv",
    "reserve_assignments.csv",
    "seasons.csv",
    "players.csv",
    "player_aliases.csv",
    "locations.csv",
    "location_aliases.csv",
)

_RESERVE_PATTERN = re.compile(r"^reserve(?:\s+([1-9]\d*)|:([1-9]\d*))$", re.IGNORECASE)
_RESERVE_PREFIX = re.compile(r"^reserve(?:\b|:)", re.IGNORECASE)
_AWARD_FIELDS = ("Gold", "Silver", "Bronze", "RedLantern")


def _normalize_name(value):
    return " ".join(str(value).split()).casefold()


def _is_reserve(value):
    return bool(_RESERVE_PATTERN.fullmatch(str(value).strip()))


def _invalid_reserve_tokens(rows, filename, columns, include_names):
    issues = []
    for row_number, row in enumerate(rows, start=2):
        for column in columns:
            if column == "Slot":
                values = [row.get(column) or ""]
            else:
                values = (row.get(column) or "").split("|")
            for value in values:
                token = value.strip()
                if _RESERVE_PREFIX.match(token) and not _is_reserve(token):
                    issue = {"file": filename, "row": row_number, "column": column}
                    if include_names:
                        issue["value"] = token
                    issues.append(issue)
    return issues


def _read_dict_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _read_players(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file))


def _safe_int(value):
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if str(value).strip() == str(result) else None


def _group_reference(group_id, name_occurrences, include_names):
    source_counts = Counter()
    for counts in name_occurrences.values():
        source_counts.update(counts)
    result = {
        "group": group_id,
        "occurrences": sum(source_counts.values()),
        "sources": {
            source: count for source, count in sorted(source_counts.items())
        },
        "variants": len(name_occurrences),
    }
    if include_names:
        result["values"] = sorted(name_occurrences, key=str.casefold)
    return result


def profile_data(data_dir=DATA_DIR, include_names=False, repo_root=None):
    """Return a deterministic, read-only report for a Manillen data directory."""
    data_dir = Path(data_dir).resolve()
    repo_root = Path(repo_root or Path(__file__).resolve().parent)
    file_report = {}
    rows_by_file = {}
    schema_issues = []

    for filename, expected_schema in CSV_SCHEMAS.items():
        path = data_dir / filename
        if not path.is_file():
            file_report[filename] = {
                "exists": False,
                "expected_columns": list(expected_schema),
                "columns": [],
                "rows": 0,
                "schema_valid": False,
            }
            schema_issues.append({"file": filename, "issue": "missing"})
            rows_by_file[filename] = []
            continue
        columns, rows = _read_dict_csv(path)
        valid = columns == list(expected_schema)
        file_report[filename] = {
            "exists": True,
            "expected_columns": list(expected_schema),
            "columns": columns,
            "rows": len(rows),
            "schema_valid": valid,
        }
        rows_by_file[filename] = rows
        if not valid:
            schema_issues.append({
                "file": filename,
                "issue": "unexpected_columns",
            })

    players_path = data_dir / "AllPlayers.csv"
    player_rows = _read_players(players_path) if players_path.is_file() else []
    roster_values = [
        row[0].strip()
        for row in player_rows
        if row and row[0].strip()
    ]
    file_report["AllPlayers.csv"] = {
        "exists": players_path.is_file(),
        "expected_columns": ["<one player name per row; no header>"],
        "columns": [],
        "rows": len(player_rows),
        "non_empty_names": len(roster_values),
        "schema_valid": all(len(row) == 1 for row in player_rows),
    }
    if not file_report["AllPlayers.csv"]["schema_valid"]:
        schema_issues.append({
            "file": "AllPlayers.csv",
            "issue": "expected_one_column",
        })
    if not players_path.is_file():
        schema_issues.append({"file": "AllPlayers.csv", "issue": "missing"})

    occurrences = defaultdict(lambda: defaultdict(Counter))

    def add_name(value, source):
        raw_value = str(value or "")
        normalized = _normalize_name(raw_value)
        if not normalized or _is_reserve(raw_value):
            return
        occurrences[normalized][raw_value][source] += 1

    for row in player_rows:
        if row and row[0].strip():
            add_name(row[0], "AllPlayers.csv")

    for row in rows_by_file["pairings.csv"]:
        add_name(row.get("Player1"), "pairings.csv")
        add_name(row.get("Player2"), "pairings.csv")

    for row in rows_by_file["pairings_history.csv"]:
        for name in (row.get("Players") or "").split("|"):
            add_name(name.strip(), "pairings_history.csv")

    for row in rows_by_file["scores_history.csv"]:
        for column in ("Team1Players", "Team2Players"):
            for name in (row.get(column) or "").split("|"):
                add_name(name.strip(), "scores_history.csv")

    for row in rows_by_file["reserve_assignments.csv"]:
        add_name(row.get("Name"), "reserve_assignments.csv")

    for row in rows_by_file["seasons_history.csv"]:
        for field in _AWARD_FIELDS:
            for name in (row.get(field) or "").split("|"):
                add_name(name.strip(), "seasons_history.csv")

    roster_counts = Counter(_normalize_name(name) for name in roster_values)
    roster_normalized = set(roster_counts)
    all_normalized = sorted(set(occurrences) | roster_normalized)
    group_ids = {
        normalized: f"name-{index:03d}"
        for index, normalized in enumerate(all_normalized, start=1)
    }

    duplicate_roster = []
    for normalized, count in sorted(roster_counts.items()):
        if count > 1:
            spellings = Counter(
                value for value in roster_values
                if _normalize_name(value) == normalized
            )
            item = {
                "group": group_ids[normalized],
                "entries": count,
                "spellings": len(spellings),
            }
            if include_names:
                item["values"] = sorted(spellings, key=str.casefold)
            duplicate_roster.append(item)

    observed_variants = []
    for normalized, raw_values in sorted(occurrences.items()):
        if len(raw_values) > 1:
            observed_variants.append(_group_reference(
                group_ids[normalized],
                occurrences[normalized],
                include_names,
            ))

    unknown_names = []
    for normalized in sorted(set(occurrences) - roster_normalized):
        unknown_names.append(_group_reference(
            group_ids[normalized],
            occurrences[normalized],
            include_names,
        ))

    roster_spellings = defaultdict(set)
    for name in roster_values:
        roster_spellings[_normalize_name(name)].add(name)
    normalization_collisions = []
    for normalized, spellings in sorted(roster_spellings.items()):
        if len(spellings) > 1:
            item = {
                "group": group_ids[normalized],
                "spellings": len(spellings),
            }
            if include_names:
                item["values"] = sorted(spellings, key=str.casefold)
            normalization_collisions.append(item)

    validation_issues = []
    history_rows = rows_by_file["pairings_history.csv"]
    seen_tables = set()
    expected_pairs = Counter()
    for row_number, row in enumerate(history_rows, start=2):
        play_date = (row.get("Date") or "").strip()
        table = _safe_int(row.get("Table"))
        names = [name.strip() for name in (row.get("Players") or "").split("|")]
        record_issues = []
        try:
            date.fromisoformat(play_date)
        except ValueError:
            record_issues.append("invalid_date")
        if table is None or table < 1:
            record_issues.append("invalid_table")
        elif play_date and (play_date, table) in seen_tables:
            record_issues.append("duplicate_date_table")
        if table is not None and table > 0 and play_date:
            seen_tables.add((play_date, table))
        if len(names) != 4 or any(not name for name in names):
            record_issues.append("expected_four_players")
        normalized_names = [_normalize_name(name) for name in names if name]
        if len(normalized_names) != len(set(normalized_names)):
            record_issues.append("duplicate_player_at_table")
        if record_issues:
            validation_issues.append({
                "file": "pairings_history.csv",
                "row": row_number,
                "issues": record_issues,
            })
        elif len(names) == 4:
            real_players = [
                _normalize_name(name) for name in names if not _is_reserve(name)
            ]
            expected_pairs.update(
                tuple(sorted(pair)) for pair in combinations(real_players, 2)
            )

    invalid_scores = []
    tied_scores = []
    for row_number, row in enumerate(rows_by_file["scores_history.csv"], start=2):
        score1 = _safe_int(row.get("Team1Score"))
        score2 = _safe_int(row.get("Team2Score"))
        issues = []
        if score1 is None or score2 is None:
            issues.append("invalid_score")
        elif score1 < 0 or score2 < 0:
            issues.append("negative_score")
        elif score1 == score2:
            tied_scores.append({
                "row": row_number,
                "date": (row.get("Date") or "").strip(),
                "table": (row.get("Table") or "").strip(),
                "game": (row.get("Game") or "").strip(),
            })
        if issues:
            invalid_scores.append({"row": row_number, "issues": issues})
        for column in ("Team1Players", "Team2Players"):
            if len([
                item for item in (row.get(column) or "").split("|")
                if item.strip()
            ]) != 2:
                invalid_scores.append({
                    "row": row_number,
                    "issues": [f"expected_two_players_in_{column}"],
                })

    actual_pairs = Counter()
    invalid_pair_counts = []
    for row_number, row in enumerate(rows_by_file["pairings.csv"], start=2):
        player1 = _normalize_name(row.get("Player1") or "")
        player2 = _normalize_name(row.get("Player2") or "")
        count = _safe_int(row.get("Count"))
        if not player1 or not player2 or count is None or count < 0:
            invalid_pair_counts.append(row_number)
            continue
        actual_pairs[tuple(sorted((player1, player2)))] += count

    drift = []
    for pair in sorted(set(expected_pairs) | set(actual_pairs)):
        expected = expected_pairs[pair]
        actual = actual_pairs[pair]
        if expected != actual:
            item = {
                "players": [group_ids[name] for name in pair],
                "history_count": expected,
                "pairings_count": actual,
            }
            if include_names:
                item["values"] = list(pair)
            drift.append(item)

    invalid_reserve_tokens = (
        _invalid_reserve_tokens(
            history_rows,
            "pairings_history.csv",
            ("Players",),
            include_names,
        )
        + _invalid_reserve_tokens(
            rows_by_file["scores_history.csv"],
            "scores_history.csv",
            ("Team1Players", "Team2Players"),
            include_names,
        )
        + _invalid_reserve_tokens(
            rows_by_file["reserve_assignments.csv"],
            "reserve_assignments.csv",
            ("Slot",),
            include_names,
        )
    )

    return {
        "report_version": 1,
        "files": file_report,
        "data_quality": {
            "schema_issues": schema_issues,
            "duplicate_roster_names": duplicate_roster,
            "normalization_collisions": normalization_collisions,
            "observed_name_variants": observed_variants,
            "unknown_name_groups": unknown_names,
            "invalid_references": unknown_names,
            "alias_registry": {
                "player_aliases.csv": (data_dir / "player_aliases.csv").is_file(),
                "location_aliases.csv": (data_dir / "location_aliases.csv").is_file(),
                "note": "No alias mapping is inferred or applied.",
            },
            "pairing_history_issues": validation_issues,
            "invalid_reserve_tokens": invalid_reserve_tokens,
            "invalid_pairing_count_rows": invalid_pair_counts,
            "invalid_score_rows": invalid_scores,
            "tied_score_rows": tied_scores,
            "pairing_count_drift": drift,
        },
        "repository_inventory": {
            "mirror_app_imports": _find_mirror_imports(repo_root),
            "csv_routes": list(CSV_ROUTE_INVENTORY),
            "versioned_csv_candidates": list(VERSIONED_CSV_CANDIDATES),
            "read_only_legacy_csvs": [
                "seasons_history.csv",
                "seasons_playdays_legacy.csv",
            ],
            "pool_membership": {
                "current_source": "AllPlayers.csv (one name per row)",
                "pool_member_column_present": False,
                "standings_include_scored_non_pool_players": True,
            },
        },
    }


def _find_mirror_imports(repo_root):
    repo_root = Path(repo_root)
    candidates = [
        repo_root / "app.py",
        repo_root / "manillen_functions.py",
        repo_root / "score_functions.py",
        repo_root / "reserve_assignments.py",
    ]
    tests_dir = repo_root / "tests"
    if tests_dir.is_dir():
        candidates.extend(sorted(tests_dir.rglob("*.py")))

    imports = []
    for path in candidates:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == "mirror_app"
                or (node.module or "").startswith("mirror_app.")
            ):
                imports.append({
                    "file": path.relative_to(repo_root).as_posix(),
                    "line": node.lineno,
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "mirror_app" or alias.name.startswith("mirror_app."):
                        imports.append({
                            "file": path.relative_to(repo_root).as_posix(),
                            "line": node.lineno,
                            "module": alias.name,
                            "names": [],
                        })
    return sorted(imports, key=lambda item: (item["file"], item["line"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Profile Manillen CSV data without modifying source files."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="data directory to inspect (default: configured MANILLEN_DATA_DIR)",
    )
    parser.add_argument(
        "--include-names",
        action="store_true",
        help="include personal names in the report; keep the output private",
    )
    args = parser.parse_args(argv)
    report = profile_data(args.data_dir, include_names=args.include_names)
    json.dump(report, fp=sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
