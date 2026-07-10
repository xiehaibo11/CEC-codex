"""Binance WS silence watchdog + endpoint rotation.

2026-07-09 forensics: fstream.binance.com accepted the aggTrade subscription
but delivered ZERO messages for 5 days (regional silent filtering since 7/4),
while the spot stream works fine. The collector had no reconnect loop, so the
flush timer spun on empty buffers forever with no errors logged. The fix:
a silence watchdog closes the socket after ``SILENCE_TIMEOUT_SECONDS`` without
any market message, and the run loop rotates endpoints (futures -> spot),
labeling the flow source honestly.
"""
from __future__ import annotations

from services.exchanges.binance_ws_collector import (
    ENDPOINTS,
    SILENCE_TIMEOUT_SECONDS,
    next_endpoint_index,
    should_reconnect_for_silence,
)


class TestSilenceWatchdog:
    def test_silence_beyond_timeout_triggers_reconnect(self):
        assert should_reconnect_for_silence(
            last_message_ts=1000.0, now_ts=1000.0 + SILENCE_TIMEOUT_SECONDS + 1
        )

    def test_recent_message_keeps_connection(self):
        assert not should_reconnect_for_silence(last_message_ts=1000.0, now_ts=1030.0)

    def test_no_message_yet_uses_connect_time(self):
        # last_message_ts None -> silence measured from connect; still triggers.
        assert should_reconnect_for_silence(
            last_message_ts=None, now_ts=1000.0 + SILENCE_TIMEOUT_SECONDS + 1,
            connected_ts=1000.0,
        )


class TestEndpointRotation:
    def test_rotates_through_endpoints(self):
        assert next_endpoint_index(0) == 1
        assert next_endpoint_index(1) == 0  # wraps

    def test_endpoint_catalog_has_futures_then_spot(self):
        assert "fstream.binance.com" in ENDPOINTS[0]["url"]
        assert "stream.binance.com" in ENDPOINTS[1]["url"]
        assert ENDPOINTS[1]["source"] == "binance_spot"
