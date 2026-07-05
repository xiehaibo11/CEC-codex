"""Binance backfill edge coverage."""

from services.exchanges.binance_backfill import BinanceBackfillService


def test_span_periods_start_before_retention_window():
    service = BinanceBackfillService()
    start_ms = 1_751_673_600_000

    assert service._start_time_for_period(start_ms, "1m") == start_ms
    assert service._start_time_for_period(start_ms, "3d") == start_ms - 3 * 24 * 60 * 60 * 1000
    assert service._start_time_for_period(start_ms, "1w") == start_ms - 7 * 24 * 60 * 60 * 1000
    assert service._start_time_for_period(start_ms, "1M") == start_ms - 30 * 24 * 60 * 60 * 1000
