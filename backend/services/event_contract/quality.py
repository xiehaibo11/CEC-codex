"""Data quality checks for event-contract prediction and backtesting."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from services.event_contract.constants import PERIOD_SECONDS


class EventContractQualityMixin:
    def preview_data_quality(self, db, config: Dict[str, Any]) -> Dict[str, Any]:
        """Audit data coverage for a backtest window WITHOUT running the backtest.

        Runs the same kline/L2/CoinGlass audits as run_backtest but never raises
        on quality warnings, so the UI can show coverage and would-block reasons
        before the user launches a task that would otherwise fail mid-flight.
        """
        cfg = self._normalize_config(config, prediction=False)
        strict_flags = {
            "kline": bool(cfg.get("strict_data_quality")),
            "l2": bool(cfg.get("strict_l2_quality")),
            "coinglass": bool(cfg.get("strict_coinglass_quality")),
            "flow": bool(cfg.get("strict_flow_quality")),
        }
        # Audits must report, not abort: strict validation is what kills real runs.
        cfg = {
            **cfg,
            "strict_data_quality": False,
            "strict_l2_quality": False,
            "strict_coinglass_quality": False,
            "strict_flow_quality": False,
        }
        start_ts = int(cfg["start_time"].timestamp())
        end_ts = int(cfg["end_time"].timestamp())
        interval = PERIOD_SECONDS[cfg["period"]]
        load_start = start_ts - cfg["warmup_bars"] * interval
        load_end = end_ts + cfg["expiry_minutes"] * 60 + interval

        klines = self._load_klines(
            db,
            cfg["exchange"],
            cfg["symbol"],
            cfg["period"],
            load_start,
            load_end,
            cfg["environment"],
        )
        klines, sanitize_report = self._sanitize_klines(klines)
        kline_audit = self._audit_kline_series(klines, cfg, start_ts, end_ts)
        kline_audit["sanitize"] = sanitize_report
        kline_audit["warnings"] = list(kline_audit["warnings"]) + list(sanitize_report["warnings"])

        l2_audit = None
        if cfg.get("enable_l2_features") and klines:
            l2_bundle = self._load_l2_feature_bundle(
                db, cfg, load_start, self._decision_timestamp(klines[-1], cfg)
            )
            if l2_bundle.get("enabled"):
                klines = self._attach_l2_features(klines, l2_bundle, cfg)
                l2_audit = self._audit_l2_features(
                    klines, l2_bundle, cfg, start_ts, end_ts
                )

        coinglass_audit = None
        if cfg.get("enable_coinglass_features"):
            coinglass_bundle = self._load_coinglass_feature_bundle(
                cfg, load_start, load_end, start_ts, end_ts
            )
            if coinglass_bundle.get("enabled"):
                coinglass_audit = coinglass_bundle.get("audit")

        flow_audit = None
        if cfg.get("enable_flow_features", True) and klines:
            flow_bundle = self._load_flow_feature_bundle(
                db, cfg, load_start, self._decision_timestamp(klines[-1], cfg)
            )
            if flow_bundle.get("enabled"):
                klines = self._attach_flow_features(klines, flow_bundle, cfg)
                flow_audit = self._audit_flow_features(
                    klines, flow_bundle, cfg, start_ts, end_ts
                )

        would_block: List[Dict[str, Any]] = []
        for source, audit in (
            ("kline", kline_audit),
            ("l2", l2_audit),
            ("coinglass", coinglass_audit),
            ("flow", flow_audit),
        ):
            if audit and strict_flags[source] and audit.get("warnings"):
                would_block.append({"source": source, "warnings": audit["warnings"]})

        return {
            "symbol": cfg["symbol"],
            "exchange": cfg["exchange"],
            "period": cfg["period"],
            "start_time": self._to_iso(start_ts),
            "end_time": self._to_iso(end_ts),
            "kline": kline_audit,
            "l2": l2_audit,
            "coinglass": coinglass_audit,
            "flow": flow_audit,
            "strict": strict_flags,
            "would_block": would_block,
            "ok": not would_block,
        }

    def _sanitize_klines(
        self, klines: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Boundary cleaning for kline series entering prediction/backtest.

        Sorts by timestamp, drops duplicate timestamps (keep first), and drops
        bars that violate hard business rules (non-positive OHLC, negative
        volume, high < low). Corrupt bars would otherwise flow straight into
        feature computation and settlement. Returns (clean, report).
        """
        seen: set = set()
        clean: List[Dict[str, Any]] = []
        dropped_invalid = 0
        dropped_duplicate = 0
        for item in sorted(klines, key=lambda k: int(k["timestamp"])):
            ts = int(item["timestamp"])
            if ts in seen:
                dropped_duplicate += 1
                continue
            o, h, lo, c = item["open"], item["high"], item["low"], item["close"]
            volume = item.get("volume") or 0
            if (
                any(v is None for v in (o, h, lo, c))
                or min(o, h, lo, c) <= 0
                or volume < 0
                or h < lo
            ):
                dropped_invalid += 1
                continue
            seen.add(ts)
            clean.append(item)
        # Outlier pass: extreme single-bar moves are flagged for review but
        # NEVER dropped - real flash moves exist and fabricating a smoother
        # series would corrupt settlement against actual market prices.
        extreme_move_bars = 0
        max_abs_move_pct = 0.0
        for prev, cur in zip(clean, clean[1:]):
            prev_close = prev["close"]
            if not prev_close:
                continue
            move_pct = abs(cur["close"] - prev_close) / prev_close * 100
            max_abs_move_pct = max(max_abs_move_pct, move_pct)
            if move_pct > 10.0:
                extreme_move_bars += 1
        warnings: List[str] = []
        if dropped_invalid:
            warnings.append(f"corrupt bars dropped: {dropped_invalid}")
        if extreme_move_bars:
            warnings.append(
                f"extreme single-bar moves >10%: {extreme_move_bars} (kept; verify source)"
            )
        report = {
            "input_bars": len(klines),
            "output_bars": len(clean),
            "dropped_invalid_bars": dropped_invalid,
            "dropped_duplicate_bars": dropped_duplicate,
            "extreme_move_bars": extreme_move_bars,
            "max_abs_move_pct": round(max_abs_move_pct, 4),
            "warnings": warnings,
        }
        return clean, report

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
