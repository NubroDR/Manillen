#!/bin/sh
set -eu

DATA_DIR="${MANILLEN_DATA_DIR:-/app/data}"
SEED_DIR="/app/data-seed"

mkdir -p "$DATA_DIR" "$DATA_DIR/Scorebladen"

for file in AllPlayers.csv pairings.csv pairings_history.csv scores_history.csv reserve_assignments.csv seasons_history.csv seasons_playdays_legacy.csv Scorebladen.xlsx; do
    if [ ! -e "$DATA_DIR/$file" ] && [ -e "$SEED_DIR/$file" ]; then
        cp "$SEED_DIR/$file" "$DATA_DIR/$file"
    fi
done

exec "$@"
