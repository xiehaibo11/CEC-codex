"""Local L2 orderbook feature loading for event-contract backtests."""

from __future__ import annotations

import bisect
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.event_contract.constants import PERIOD_SECONDS


class EventContractL2Mixin:
    def _load_l2_feature_bundle(
        self,
        db: Session,
        cfg: Dict[str, Any],
        fetch_start_ts: int,
        fetch_end_ts: int,
    ) -> Dict[str, Any]:
        if not cfg.get("enable_l2_features"):
            return {"enabled": False, "features_by_ts": {}, "timestamps": [], "warnings": []}

        max_lag_seconds = int(cfg["max_l2_lag_seconds"])
        rows = db.execute(
            text(
                """
                SELECT timestamp, best_bid, best_ask, spread,
                       bid_depth_5, ask_depth_5, bid_depth_10, ask_depth_10,
                       bid_orders_count, ask_orders_count
                FROM market_orderbook_snapshots
                WHERE exchange = :exchange
                  AND symbol = :symbol
                  AND timestamp BETWEEN :start_ms AND :end_ms
                ORDER BY timestamp
                """
            ),
            {
                "exchange": cfg["exchange"],
                "symbol": cfg["symbol"],
                "start_ms": int((fetch_start_ts - max_lag_seconds) * 1000),
                "end_ms": int(fetch_end_ts * 1000),
            },
        ).mappings().all()

        features_by_ts: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            feature = self._parse_l2_snapshot(row, cfg)
            if feature:
                features_by_ts[feature["timestamp_ms"]] = feature

        return {
            "enabled": True,
            "source": "local_orderbook_snapshots",
            "records_loaded": len(features_by_ts),
            "features_by_ts": features_by_ts,
            "timestamps": sorted(features_by_ts),
            "warnings": [] if features_by_ts else ["no local L2 orderbook snapshots found"],
        }

    def _attach_l2_features(
        self,
        klines: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not bundle.get("enabled") or not bundle.get("timestamps"):
            return klines

        timestamps = bundle["timestamps"]
        features_by_ts = bundle["features_by_ts"]
        max_lag = int(cfg["max_l2_lag_seconds"])

        for item in klines:
            decision_ms = self._decision_timestamp(item, cfg) * 1000
            idx = bisect.bisect_right(timestamps, decision_ms) - 1
            if idx < 0:
                continue
            snapshot_ms = timestamps[idx]
            lag_seconds = (decision_ms - snapshot_ms) / 1000
            if lag_seconds > max_lag:
                continue
            item["l2"] = {
                **features_by_ts[snapshot_ms],
                "lag_seconds": round(lag_seconds, 3),
            }
        return klines

    def _audit_l2_features(
        self,
        klines: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        cfg: Dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        if not cfg.get("enable_l2_features"):
            return {"enabled": False, "warnings": []}

        decision_items = [
            item
            for item in klines
            if start_ts <= self._decision_timestamp(item, cfg) <= end_ts
        ]
        l2_items = [item for item in decision_items if item.get("l2")]
        expected = len(decision_items)
        coverage = round(len(l2_items) / expected * 100, 4) if expected else 0.0
        lags = [float(item["l2"].get("lag_seconds") or 0) for item in l2_items]
        warnings = list(bundle.get("warnings") or [])

        if expected and coverage < cfg["min_l2_coverage_pct"]:
            warnings.append(f"L2 coverage {coverage}% below {cfg['min_l2_coverage_pct']}%")
        if lags and max(lags) > cfg["max_l2_lag_seconds"]:
            warnings.append(f"L2 max lag {max(lags):.2f}s above {cfg['max_l2_lag_seconds']}s")

        audit = {
            "enabled": True,
            "source": bundle.get("source") or "local_orderbook_snapshots",
            "exchange": cfg["exchange"],
            "symbol": cfg["symbol"],
            "period": cfg["period"],
            "interval_seconds": PERIOD_SECONDS[cfg["period"]],
            "records_loaded": int(bundle.get("records_loaded") or 0),
            "decision_records": len(l2_items),
            "expected_decision_records": expected,
            "coverage_pct": coverage,
            "min_required_coverage_pct": cfg["min_l2_coverage_pct"],
            "max_lag_seconds": round(max(lags), 3) if lags else None,
            "avg_lag_seconds": round(sum(lags) / len(lags), 3) if lags else None,
            "warnings": warnings,
            "strict": cfg["strict_l2_quality"],
            "no_future_leakage": True,
        }
        self._validate_l2_quality(audit, cfg)
        return audit

    def _validate_l2_quality(self, audit: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        if audit.get("enabled") and cfg.get("strict_l2_quality") and audit.get("warnings"):
            raise ValueError(f"L2 orderbook data quality check failed: {'; '.join(audit['warnings'])}")

    def _parse_l2_snapshot(self, row: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any] | None:
        timestamp_ms = self._l2_int(row.get("timestamp"))
        bid5 = self._l2_float(row.get("bid_depth_5"))
        ask5 = self._l2_float(row.get("ask_depth_5"))
        bid10 = self._l2_float(row.get("bid_depth_10"))
        ask10 = self._l2_float(row.get("ask_depth_10"))
        best_bid = self._l2_float(row.get("best_bid"))
        best_ask = self._l2_float(row.get("best_ask"))
        if not timestamp_ms or (bid5 <= 0 and bid10 <= 0) or (ask5 <= 0 and ask10 <= 0):
            return None

        spread = self._l2_float(row.get("spread"))
        mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0.0
        spread_bps = spread / mid_price * 10000 if mid_price > 0 else 0.0

        return {
            "timestamp_ms": timestamp_ms,
            "timestamp": timestamp_ms // 1000,
            "source": "local_orderbook_snapshots",
            "exchange": cfg["exchange"],
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": mid_price,
            "spread": spread,
            "spread_bps": spread_bps,
            "bid_depth_5": bid5,
            "ask_depth_5": ask5,
            "bid_depth_10": bid10,
            "ask_depth_10": ask10,
            "depth_ratio_5": bid5 / ask5 if ask5 > 0 else 0.0,
            "depth_ratio_10": bid10 / ask10 if ask10 > 0 else 0.0,
            "imbalance_5": self._l2_imbalance(bid5, ask5),
            "imbalance_10": self._l2_imbalance(bid10, ask10),
            "bid_orders_count": self._l2_int(row.get("bid_orders_count")) or 0,
            "ask_orders_count": self._l2_int(row.get("ask_orders_count")) or 0,
        }

    def _l2_imbalance(self, bid_depth: float, ask_depth: float) -> float:
        total = bid_depth + ask_depth
        return (bid_depth - ask_depth) / total if total > 0 else 0.0

    def _l2_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _l2_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
