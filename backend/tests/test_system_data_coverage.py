"""System data coverage calculations."""

from api.system.coverage import calculate_daily_coverage_pct


def test_daily_coverage_marks_any_records_as_nonzero():
    assert calculate_daily_coverage_pct(records=1, expected_records=1440) == 1
    assert calculate_daily_coverage_pct(records=0, expected_records=1440) == 0


def test_daily_coverage_still_caps_at_100():
    assert calculate_daily_coverage_pct(records=2000, expected_records=1440) == 100
