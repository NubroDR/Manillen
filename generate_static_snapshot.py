"""Generate a versioned, derived JSON snapshot for the static public mirror."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from data_paths import DATA_DIR
from manillen_core.data_helpers import (
    load_all_players,
    load_pairing_counts,
    load_pairing_records,
    load_reserve_assignments,
)
from manillen_core.score_helpers import (
    compute_standings,
    is_valid_game_score,
    load_scores,
)
from manillen_core.season_helpers import (
    MIN_GAMES_FOR_AWARD,
    compute_closed_season_awards,
    compute_hall_of_fame,
    load_legacy_seasons,
    load_seasons,
    load_season_playdays,
)


def _season_key(season):
    return quote(str(season), safe="-_.~")


def _standings_rows(rows):
    return [
        {
            "player": row["player"],
            "wins": row["wins"],
            "gamesPlayed": row["games_played"],
            "pointsFor": row["points_for"],
            "pointsAgainst": row["points_against"],
            "pointDiff": row["point_diff"],
        }
        for row in rows
    ]


def _table_standings_rows(rows, players):
    results = {
        row["player"].removesuffix("*"): {
            "wins": row["wins"],
            "losses": row["games_played"] - row["wins"],
        }
        for row in rows
    }
    standings = [
        {
            "player": player,
            **results.get(
                player.removesuffix("*"),
                {"wins": 0, "losses": 0},
            ),
        }
        for player in players
    ]
    return sorted(
        standings,
        key=lambda row: (
            -row["wins"],
            -(row["wins"] + row["losses"]),
            row["player"].removesuffix("*").casefold(),
        ),
    )


def _resolved_team_players(value, assignments):
    names = [name.strip() for name in value.split("|") if name.strip()]
    return " | ".join(
        f"{assignments.get(name, name)}*"
        if name.casefold().startswith("reserve ")
        else name
        for name in names
    )


def _season_snapshot(
    season,
    season_number,
    status,
    pool_size,
    history_path,
    scores_path,
    assignments_path,
    all_history,
    all_scores,
    assignments,
):
    season_history = (
        all_history
        if season is None
        else [row for row in all_history if row["Season"] == season]
    )
    season_dates = sorted({row["Date"] for row in season_history}, reverse=True)
    playdays = []
    for play_date in season_dates:
        table_records = sorted(
            (row for row in season_history if row["Date"] == play_date),
            key=lambda row: row["Table"],
        )
        date_assignments = assignments.get(play_date, {})
        tables = []
        for record in table_records:
            players = [
                f"{date_assignments.get(player, player)}*"
                if player.casefold().startswith("reserve ")
                else player
                for player in record["Players"]
            ]
            table_standings = compute_standings(
                str(scores_path),
                play_date=play_date,
                season=season,
                history_filename=str(history_path),
                reserve_assignments_filename=str(assignments_path),
                table_number=record["Table"],
            )
            tables.append({
                "table": record["Table"],
                "players": players,
                "location": record["Location"],
                "standings": _table_standings_rows(table_standings, players),
            })
        location = next(
            (record["Location"] for record in table_records if record["Location"]),
            "",
        )
        day_standings = compute_standings(
            str(scores_path),
            play_date=play_date,
            season=season,
            history_filename=str(history_path),
            reserve_assignments_filename=str(assignments_path),
        )
        playdays.append({
            "date": play_date,
            "location": location,
            "playersPresent": len({
                player
                for record in table_records
                for player in record["Players"]
            }),
            "tables": tables,
            "standings": _standings_rows(day_standings),
        })

    season_scores = [
        {
            "date": row["Date"],
            "table": row["Table"],
            "game": row["Game"],
            "team1Players": _resolved_team_players(
                row["Team1Players"],
                assignments.get(row["Date"], {}),
            ),
            "team2Players": _resolved_team_players(
                row["Team2Players"],
                assignments.get(row["Date"], {}),
            ),
            "team1Score": row["Team1Score"],
            "team2Score": row["Team2Score"],
            "validScore": is_valid_game_score(
                row["Team1Score"], row["Team2Score"],
            ),
        }
        for row in all_scores
        if row["Date"] in season_dates
    ]
    season_scores.sort(
        key=lambda row: (row["date"], -row["table"], -row["game"]),
        reverse=True,
    )

    return {
        "season": season or "all",
        "seasonNumber": season_number,
        "status": status,
        "poolSize": pool_size,
        "standings": _standings_rows(compute_standings(
            str(scores_path),
            season=season,
            history_filename=str(history_path),
            reserve_assignments_filename=str(assignments_path),
        )),
        "playdays": playdays,
        "scores": season_scores,
        "legacyPlaydays": [],
        "awards": {
            field: "" for field in ("Gold", "Silver", "Bronze", "RedLantern")
        },
    }


def build_snapshot(data_dir):
    """Build deterministic JSON-serializable derived data from a CSV directory."""
    data_dir = Path(data_dir).resolve()
    players_path = data_dir / "AllPlayers.csv"
    pairings_path = data_dir / "pairings.csv"
    history_path = data_dir / "pairings_history.csv"
    scores_path = data_dir / "scores_history.csv"
    assignments_path = data_dir / "reserve_assignments.csv"
    seasons_path = data_dir / "seasons.csv"
    legacy_seasons_path = data_dir / "seasons_history.csv"
    legacy_playdays_path = data_dir / "seasons_playdays_legacy.csv"

    players = load_all_players(str(players_path))
    seasons = load_seasons(seasons_path)
    active = [season for season in seasons if season["Status"] == "actief"]
    if len(active) != 1:
        raise ValueError("Er moet precies één actief seizoen zijn.")
    active_season = active[0]["Season"]
    legacy_seasons = load_legacy_seasons(
        legacy_seasons_path,
        legacy_playdays_path,
        players,
    )
    current_seasons = {
        row["Season"]: row for row in seasons
    }
    legacy_by_label = {
        row["Season"]: row for row in legacy_seasons
    }
    all_labels = set(current_seasons) | set(legacy_by_label)
    all_history = load_pairing_records(history_path)
    all_scores = load_scores(scores_path)
    assignments = {}
    for row in all_history:
        assignments.setdefault(row["Date"], {})
    for play_date, values in load_reserve_assignments(assignments_path).items():
        assignments.setdefault(play_date, {}).update(values)

    tool_awards = dict(compute_closed_season_awards(
        seasons_path,
        scores_path,
        history_path,
        players,
        MIN_GAMES_FOR_AWARD,
    ))
    season_payloads = {}
    season_index = []
    for label in sorted(
        all_labels,
        key=lambda name: (
            current_seasons.get(name, {}).get(
                "SeasonNumber", legacy_by_label.get(name, {}).get("SeasonNumber", 0)
            ),
            name,
        ),
    ):
        current = current_seasons.get(label)
        legacy = legacy_by_label.get(label)
        season_number = (
            current["SeasonNumber"] if current else legacy["SeasonNumber"]
        )
        status = current["Status"] if current else "legacy"
        pool_size = len(players) if current else legacy["Pool"]
        payload = _season_snapshot(
            label,
            season_number,
            status,
            pool_size,
            history_path,
            scores_path,
            assignments_path,
            all_history,
            all_scores,
            assignments,
        )
        if legacy:
            payload["legacyPlaydays"] = [
                {
                    "date": row.get("Date", ""),
                    "location": row.get("Location", ""),
                    "playersPresent": row.get("PlayersPresent", ""),
                }
                for row in legacy["Playdays"]
            ]
            for field in ("Gold", "Silver", "Bronze", "RedLantern"):
                payload["awards"][field] = legacy[field]
        payload["awards"].update(tool_awards.get(label, {}))
        season_payloads[label] = payload
        season_index.append({
            "season": label,
            "seasonNumber": season_number,
            "status": status,
            "poolSize": pool_size,
            "hasIndividualData": bool(
                payload["playdays"] or payload["scores"]
            ),
        })

    partner_rows = [
        {"player1": player1, "player2": player2, "count": count}
        for player1, player2, count in load_pairing_counts(str(pairings_path))
    ]
    partner_rows.sort(
        key=lambda row: (
            -row["count"],
            row["player1"].casefold(),
            row["player2"].casefold(),
        )
    )
    hall_of_fame = compute_hall_of_fame(
        players,
        legacy_seasons_path,
        tuple(sorted(tool_awards.items())),
    )
    all_season_payload = _season_snapshot(
        None,
        0,
        "all",
        len(players),
        history_path,
        scores_path,
        assignments_path,
        all_history,
        all_scores,
        assignments,
    )
    all_season_payload["awards"] = {
        field: "" for field in ("Gold", "Silver", "Bronze", "RedLantern")
    }
    files = {
        "players.json": players,
        "pairings.json": partner_rows,
        "hall-of-fame.json": hall_of_fame,
    }
    for label, payload in season_payloads.items():
        files[f"seasons/{_season_key(label)}.json"] = payload
    files["seasons/all.json"] = all_season_payload
    manifest = {
        "schemaVersion": 1,
        "generatedAt": None,
        "buildId": None,
        "activeSeason": active_season,
        "seasons": season_index,
    }
    return manifest, files


def generate_snapshot(data_dir, output_dir, generated_at=None):
    """Write a fresh JSON snapshot directory and return its manifest."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Snapshot output directory must be empty: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest, files = build_snapshot(data_dir)
    content = json.dumps(
        files,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    build_id = hashlib.sha256(content).hexdigest()[:16]
    manifest["buildId"] = build_id
    manifest["generatedAt"] = (
        generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    files["manifest.json"] = manifest
    for relative_path, value in files.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a derived JSON snapshot for the static Manillen mirror."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new, empty directory for the generated snapshot",
    )
    args = parser.parse_args(argv)
    manifest = generate_snapshot(args.data_dir, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
