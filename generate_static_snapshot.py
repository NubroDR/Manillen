"""Generate a versioned, derived JSON snapshot for the static public mirror."""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from data_paths import DATA_DIR, data_path
from manillen_core.data_helpers import (
    load_pairing_counts,
    load_pairing_records,
    load_reserve_assignments,
)
from manillen_core.score_helpers import (
    compute_standings,
    is_valid_game_score,
    load_scores,
)
from manillen_core.reference_adapter import ReferenceAdapter
from manillen_core.reference_helpers import is_reserve_reference
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


def _player_slug(name):
    candidate = unicodedata.normalize("NFKD", str(name).strip())
    candidate = "".join(ch for ch in candidate if not unicodedata.combining(ch))
    candidate = candidate.casefold().replace("&", " and ")
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate)
    candidate = candidate.strip("-")
    return candidate or "speler"


def _team_players(value):
    return [token.strip() for token in str(value).split("|") if token.strip()]


def _player_profile(name, season_by_date, hall_of_fame, scores, all_history, assignments):
    seasons = {}
    total = {
        "wins": 0,
        "losses": 0,
        "gamesPlayed": 0,
        "pointsFor": 0,
        "pointsAgainst": 0,
    }
    awards = []
    for row in hall_of_fame:
        if row.get("Player") == name:
            for award in ("Gold", "Silver", "Bronze", "RedLantern"):
                count = row.get(award, 0)
                if count:
                    awards.append({"award": award, "count": count})

    def season_entry(season):
        return seasons.setdefault(season, {
            "season": season,
            "gamesPlayed": 0,
            "wins": 0,
            "losses": 0,
            "pointsFor": 0,
            "pointsAgainst": 0,
            "playdays": {},
        })

    for row in all_history:
        play_date = row["Date"]
        date_assignments = assignments.get(play_date, {})
        players_present = {
            date_assignments.get(player, player)
            for player in row["Players"]
        }
        if name not in players_present:
            continue
        entry = season_entry(season_by_date.get(play_date, "onbekend"))
        locations = entry["playdays"].setdefault(play_date, set())
        if row.get("Location"):
            locations.add(row["Location"])

    for row in scores:
        if not is_valid_game_score(row["Team1Score"], row["Team2Score"]):
            continue
        team1_players = _team_players(row["Team1Players"])
        team2_players = _team_players(row["Team2Players"])
        if name not in team1_players and name not in team2_players:
            continue
        season = season_by_date.get(row["Date"], "onbekend")
        entry = season_entry(season)
        team1_score = int(row["Team1Score"])
        team2_score = int(row["Team2Score"])
        if name in team1_players:
            entry["pointsFor"] += team1_score
            entry["pointsAgainst"] += team2_score
            if team1_score > team2_score:
                entry["wins"] += 1
            else:
                entry["losses"] += 1
        else:
            entry["pointsFor"] += team2_score
            entry["pointsAgainst"] += team1_score
            if team2_score > team1_score:
                entry["wins"] += 1
            else:
                entry["losses"] += 1
        entry["gamesPlayed"] += 1
        total["gamesPlayed"] += 1
        total["pointsFor"] += team1_score if name in team1_players else team2_score
        total["pointsAgainst"] += team2_score if name in team1_players else team1_score
        if (name in team1_players and team1_score > team2_score) or (name in team2_players and team2_score > team1_score):
            total["wins"] += 1
        else:
            total["losses"] += 1
    season_rows = []
    for season, values in sorted(seasons.items(), key=lambda item: item[0]):
        games_played = values["gamesPlayed"]
        playdays = [
            {
                "date": play_date,
                "locations": sorted(locations, key=str.casefold),
            }
            for play_date, locations in sorted(values["playdays"].items())
        ]
        season_rows.append({
            "season": season,
            "gamesPlayed": games_played,
            "wins": values["wins"],
            "losses": values["losses"],
            "pointsFor": values["pointsFor"],
            "pointsAgainst": values["pointsAgainst"],
            "pointDiff": values["pointsFor"] - values["pointsAgainst"],
            "winRate": round(values["wins"] / games_played, 3) if games_played else 0.0,
            "playdaysAttended": len(playdays),
            "playdays": playdays,
        })
    return {
        "name": name,
        "slug": _player_slug(name),
        "gamesPlayed": total["gamesPlayed"],
        "wins": total["wins"],
        "losses": total["losses"],
        "pointsFor": total["pointsFor"],
        "pointsAgainst": total["pointsAgainst"],
        "pointDiff": total["pointsFor"] - total["pointsAgainst"],
        "winRate": round(total["wins"] / total["gamesPlayed"], 3) if total["gamesPlayed"] else 0.0,
        "awards": awards,
        "seasons": season_rows,
    }


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
    adapter = ReferenceAdapter(data_dir)
    pairings_path = data_path("pairings.csv", data_dir)
    history_path = data_path("pairings_history.csv", data_dir)
    scores_path = data_path("scores_history.csv", data_dir)
    assignments_path = data_path("reserve_assignments.csv", data_dir)
    seasons_path = data_path("seasons.csv", data_dir)
    legacy_seasons_path = data_dir / "seasons_history.csv"
    legacy_playdays_path = data_dir / "seasons_playdays_legacy.csv"

    players = adapter.player_pool()
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
    season_by_date = {row["Date"]: row["Season"] for row in all_history}
    assignments = {}
    for row in all_history:
        assignments.setdefault(row["Date"], {})
    for play_date, values in load_reserve_assignments(assignments_path).items():
        assignments.setdefault(play_date, {}).update({
            adapter.player_name(slot): adapter.player_name(reference)
            for slot, reference in values.items()
        })

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

    partner_rows = []
    for player1, player2, count in load_pairing_counts(str(pairings_path)):
        player1, player2 = sorted(
            (player1, player2),
            key=str.casefold,
        )
        partner_rows.append({
            "player1": player1,
            "player2": player2,
            "count": count,
        })
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
    profile_names = set(players)
    profile_names.update(row["Player"] for row in hall_of_fame)
    profile_names.update(
        player for row in all_history for player in row["Players"]
    )
    profile_names.update(
        player
        for row in all_scores
        for team in (row["Team1Players"], row["Team2Players"])
        for player in _team_players(team)
    )
    profile_names.update(
        player
        for row in partner_rows
        for player in (row["player1"], row["player2"])
    )
    files = {
        "players.json": players,
        "pairings.json": partner_rows,
        "hall-of-fame.json": hall_of_fame,
    }
    profiles_by_id = {}
    profile_routes = {}
    profile_slugs = {}
    for player in sorted(profile_names, key=str.casefold):
        if is_reserve_reference(player):
            continue
        player_id = adapter.find_player_id(player)
        canonical_name = (
            adapter.player_name(player_id) if player_id is not None else player
        )
        profile_path = _player_slug(canonical_name)
        profile_key = (
            ("id", player_id)
            if player_id is not None
            else ("name", canonical_name.casefold())
        )
        existing_key = profile_slugs.get(profile_path)
        if existing_key is not None and existing_key != profile_key:
            raise ValueError(f"Player profile slug collision: {profile_path}")
        profile_slugs[profile_path] = profile_key
        if player_id is not None:
            profiles_by_id.setdefault(
                player_id,
                _player_profile(
                    canonical_name,
                    season_by_date,
                    hall_of_fame,
                    all_scores,
                    all_history,
                    assignments,
                ),
            )
            profile = profiles_by_id[player_id]
        else:
            profile = _player_profile(
                canonical_name,
                season_by_date,
                hall_of_fame,
                all_scores,
                all_history,
                assignments,
            )
        route_key = (
            player_id
            if adapter.is_versioned and player_id is not None
            else profile_path
        )
        profile_routes[profile_path] = route_key
        files[f"players/{route_key}.json"] = profile
        if route_key != profile_path:
            files[f"players/{profile_path}.json"] = profile

    if adapter.is_versioned:
        aliases_path = adapter.data_dir / "player_aliases.csv"
        with aliases_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                player_id = row["PlayerID"]
                profile = profiles_by_id.get(player_id)
                if profile is None:
                    canonical_name = adapter.player_name(player_id)
                    profile = _player_profile(
                        canonical_name,
                        season_by_date,
                        hall_of_fame,
                        all_scores,
                        all_history,
                        assignments,
                    )
                    profiles_by_id[player_id] = profile
                    files[f"players/{player_id}.json"] = profile
                    canonical_slug = _player_slug(canonical_name)
                    existing_key = profile_slugs.get(canonical_slug)
                    if (
                        existing_key is not None
                        and existing_key != ("id", player_id)
                    ):
                        raise ValueError(
                            f"Player profile slug collision: {canonical_slug}"
                        )
                    profile_slugs[canonical_slug] = ("id", player_id)
                    profile_routes[canonical_slug] = player_id
                    files[f"players/{canonical_slug}.json"] = profile
                profile_path = _player_slug(row["Alias"])
                existing_key = profile_slugs.get(profile_path)
                if existing_key is not None and existing_key != ("id", player_id):
                    raise ValueError(
                        f"Player profile slug collision: {profile_path}"
                    )
                profile_slugs[profile_path] = ("id", player_id)
                profile_routes[profile_path] = player_id
                files[f"players/{profile_path}.json"] = profile

    files["player-routes.json"] = profile_routes
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
