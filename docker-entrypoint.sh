#!/bin/sh
set -eu

mkdir -p /app/data /app/data/Scorebladen

for file in AllPlayers.csv pairings.csv pairings_history.csv scores_history.csv reserve_assignments.csv seasons_history.csv seasons_playdays_legacy.csv Scorebladen.xlsx; do
    if [ ! -e "/app/data/$file" ] && [ -e "/app/data-seed/$file" ]; then
        cp "/app/data-seed/$file" "/app/data/$file"
    fi
done

exec "$@"
