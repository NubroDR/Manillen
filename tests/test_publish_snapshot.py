from github_publish import SNAPSHOT_FILES as NAS_SNAPSHOT_FILES
from publish_mirror import SNAPSHOT_FILES as PAGES_SNAPSHOT_FILES


def test_season_sources_are_published_but_test_fixture_is_not():
    expected_sources = {
        "seasons.csv",
        "seasons_history.csv",
        "seasons_playdays_legacy.csv",
    }

    assert expected_sources.issubset(NAS_SNAPSHOT_FILES)
    assert expected_sources.issubset(PAGES_SNAPSHOT_FILES)
    assert "hall_of_fame_check.csv" not in NAS_SNAPSHOT_FILES
    assert "hall_of_fame_check.csv" not in PAGES_SNAPSHOT_FILES
