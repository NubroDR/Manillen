import csv

from reserve_assignments import (
    get_reserve_assignments,
    reserve_name_matches_pool,
    save_reserve_assignments,
)


def test_reserve_assignment_resolves_by_play_date_and_slot(tmp_path):
    path = tmp_path / "reserve_assignments.csv"
    save_reserve_assignments("2026-09-19", {"Reserve 1": "Jan"}, path)
    save_reserve_assignments("2026-10-03", {"Reserve 1": "Piet"}, path)
    assert get_reserve_assignments("2026-09-19", path) == {"Reserve 1": "Jan"}
    assert get_reserve_assignments("2026-10-03", path) == {"Reserve 1": "Piet"}


def test_pool_player_name_entered_as_reserve_is_detected():
    assert reserve_name_matches_pool("José", ["José", "Zoë"])
    assert not reserve_name_matches_pool("Jeroen", ["José", "Zoë"])
