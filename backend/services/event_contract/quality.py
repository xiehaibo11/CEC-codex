"""Data quality checks for event-contract prediction and backtesting."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from services.event_contract.constants import PERIOD_SECONDS


class EventContractQualityMixin:
    def _closed_klines(
        self, klines: List[Dict[str, Any]], period: str, now_ts: int
    ) -> List[Dict[str, Any]]:
        interval = PERIOD_SECONDS[period]
        return [item for item in klines if item["timestamp"] + interval <= now_ts]

    def _audit_kline_series(
        self,
        klines: List[Dict[str, Any]],
        cfg: Dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        interval = PERIOD_SECONDS[cfg["period"]]
        timestamps = [int(item["timestamp"]) for item in klines]
        unique_timestamps = sorted(set(timestamps))
        duplicate_count = len(timestamps) - len(unique_timestamps)
        non_monotonic_count = sum(
            1 for prev, cur in zip(timestamps, timestamps[1:]) if cur <= prev
        )

        gaps = []
        for prev, cur in zip(unique_timestamps, unique_timestamps[1:]):
            delta = cur - prev
            if delta > interval:
                gaps.append(
                    {
                        "start": self._to_iso(prev),
                        "end": self._to_iso(cur),
                        "gap_seconds": delta - interval,
                        "missing_bars": max(0, round(delta / interval) - 1),
                    }
                )

        missing_bar_count = sum(item["missing_bars"] for item in gaps)
        decision_timestamps = [
            ts for ts in unique_timestamps if start_ts <= ts + interval <= end_ts
        ]
        expected_bars = max(0, int((end_ts - start_ts) // interval) + 1)
        coverage_pct = (
            round(len(decision_timestamps) / expected_bars * 100, 4)
            if expected_bars
            else 0
        )
        max_gap_seconds = max((item["gap_seconds"] for item in gaps), default=0)
        warnings = []
        if duplicate_count:
            warnings.append(f"duplicate timestamps: {duplicate_count}")
        if non_monotonic_count:
            warnings.append(f"non-monotonic timestamps: {non_monotonic_count}")
        if expected_bars and coverage_pct < cfg["min_data_coverage_pct"]:
            warnings.append(
                f"coverage {coverage_pct}% below {cfg['min_data_coverage_pct']}%"
            )
        if max_gap_seconds > interval * 3:
            warnings.append(f"large kline gap: {max_gap_seconds}s")

        return {
            "period": cfg["period"],
            "interval_seconds": interval,
            "records_loaded": len(klines),
            "decision_records": len(decision_timestamps),
            "expected_decision_records": expected_bars,
            "coverage_pct": coverage_pct,
            "duplicate_count": duplicate_count,
            "non_monotonic_count": non_monotonic_count,
            "gap_count": len(gaps),
            "missing_bar_count": missing_bar_count,
            "max_gap_seconds": max_gap_seconds,
            "sample_gaps": gaps[:20],
            "warnings": warnings,
            "strict": cfg["strict_data_quality"],
        }

    def _validate_data_quality(
        self, audit: Dict[str, Any], cfg: Dict[str, Any]
    ) -> None:
        if cfg["strict_data_quality"] and audit["warnings"]:
            raise ValueError(
                f"K-line data quality check failed: {'; '.join(audit['warnings'])}"
            )

    def _resolve_expiry_index(
        self,
        klines: List[Dict[str, Any]],
        ts_to_index: Dict[int, int],
        expiry_ts: int,
        cfg: Dict[str, Any],
    ) -> Tuple[Optional[int], Optional[int]]:
        expiry_idx = ts_to_index.get(expiry_ts)
        if expiry_idx is not None:
            return expiry_idx, 0

        expiry_idx = self._first_index_at_or_after(klines, expiry_ts)
        if expiry_idx is None or expiry_idx >= len(klines):
            return None, None

        lag_seconds = int(klines[expiry_idx]["timestamp"] - expiry_ts)
        if lag_seconds > cfg["max_expiry_lag_seconds"]:
            return None, lag_seconds
        return expiry_idx, lag_seconds

    def _config_hash(self, cfg: Dict[str, Any]) -> str:
        public_cfg = self._public_config(cfg)
        payload = json.dumps(public_cfg, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _strategy_fingerprint(self, cfg: Dict[str, Any]) -> str:
        """Config hash that ignores the tested window - two runs with the same
        fingerprint on different windows form an honest out-of-sample pair."""
        public_cfg = self._public_config(cfg)
        # Exclude window boundaries and window-derived runtime injections
        for key in ("start_time", "end_time", "reviewer_weights"):
            # reviewer_weights is computed from trades before start_time (pre_window mode),
            # so different windows get different weights despite identical strategy config
            public_cfg.pop(key, None)
        payload = json.dumps(public_cfg, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
