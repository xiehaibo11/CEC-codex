"""Local market-flow feature loading for event-contract runs.

Supplies real taker buy/sell (CVD), open interest, and funding-rate features
from the local market-flow collector tables, aligned to K-line decision
timestamps with NO look-ahead: a bar only sees flow records stamped at or
before its own close. Field names mirror the CoinGlass feature interface
(cvd_delta_norm / taker_delta_norm / oi_change_pct / funding_rate) so the
downstream reversal-evidence scoring consumes either source unchanged.
Liquidation data has no local collector and remains CoinGlass-only.
"""

from __future__ import annotations

import bisect
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.event_contract.constants import PERIOD_SECONDS

# Trailing window (in bars) for the normalized CVD measure - matches the
# 30-bar window of the OHLCV proxy it replaces.
CVD_WINDOW_BARS = 30


class EventContractFlowMixin:
    def _load_flow_feature_bundle(
        self,
        db: Session,
        cfg: Dict[str, Any],
        fetch_start_ts: int,
        fetch_end_ts: int,
    ) -> Dict[str, Any]:
        if not cfg.get("enable_flow_features", True):
            return {"enabled": False, "warnings": []}

        interval = PERIOD_SECONDS[cfg["period"]]
        # Extra lookback so the first decision bars still get a full CVD window.
        start_ms = int((fetch_start_ts - CVD_WINDOW_BARS * interval) * 1000)
        end_ms = int(fetch_end_ts * 1000)

        taker_rows, taker_exchange = self._load_flow_taker_rows(db, cfg, start_ms, end_ms)
        metric_rows = db.execute(
            text(
                """
                SELECT timestamp, open_interest, funding_rate
                FROM market_asset_metrics
                WHERE exchange = :exchange AND symbol = :symbol
                  AND timestamp BETWEEN :start_ms AND :end_ms
                ORDER BY timestamp
                """
            ),
            {
                "exchange": cfg["exchange"],
                "symbol": cfg["symbol"],
                "start_ms": start_ms,
                "end_ms": end_ms,
            },
        ).mappings().all()

        taker_ts: List[int] = []
        buy_prefix: List[float] = [0.0]
        sell_prefix: List[float] = [0.0]
        for row in taker_rows:
            taker_ts.append(int(row["timestamp"]))
            buy_prefix.append(buy_prefix[-1] + float(row["taker_buy_volume"] or 0))
            sell_prefix.append(sell_prefix[-1] + float(row["taker_sell_volume"] or 0))

        metric_ts: List[int] = []
        metrics: List[Dict[str, Any]] = []
        for row in metric_rows:
            metric_ts.append(int(row["timestamp"]))
            metrics.append(
                {
                    "open_interest": float(row["open_interest"]) if row["open_interest"] is not None else None,
                    "funding_rate": float(row["funding_rate"]) if row["funding_rate"] is not None else None,
                }
            )

        warnings: List[str] = []
        if not taker_ts:
            warnings.append("no local taker-volume records found")
        if not metric_ts:
            warnings.append("no local OI/funding records found")
        return {
            "enabled": True,
            "source": "local_market_flow",
            "taker_exchange": taker_exchange,
            "metrics_exchange": cfg["exchange"] if metric_ts else None,
            "taker_records": len(taker_ts),
            "metric_records": len(metric_ts),
            "taker_ts": taker_ts,
            "buy_prefix": buy_prefix,
            "sell_prefix": sell_prefix,
            "metric_ts": metric_ts,
            "metrics": metrics,
            "warnings": warnings,
        }

    def _load_flow_taker_rows(self, db: Session, cfg: Dict[str, Any], start_ms: int, end_ms: int):
        """Taker aggregates for the run's exchange, falling back to the venue
        with the most records when the primary has none. Cross-venue BTC taker
        flow is correlated but not identical, so the source is reported."""
        query = text(
            """
            SELECT timestamp, taker_buy_volume, taker_sell_volume
            FROM market_trades_aggregated
            WHERE exchange = :exchange AND symbol = :symbol
              AND timestamp BETWEEN :start_ms AND :end_ms
            ORDER BY timestamp
            """
        )
        params = {"symbol": cfg["symbol"], "start_ms": start_ms, "end_ms": end_ms}
        rows = db.execute(query, {**params, "exchange": cfg["exchange"]}).mappings().all()
        if rows:
            return rows, cfg["exchange"]
        fallback = db.execute(
            text(
                """
                SELECT exchange, COUNT(*) AS n FROM market_trades_aggregated
                WHERE symbol = :symbol AND timestamp BETWEEN :start_ms AND :end_ms
                GROUP BY exchange ORDER BY n DESC LIMIT 1
                """
            ),
            params,
        ).mappings().first()
        if not fallback:
            return [], None
        rows = db.execute(query, {**params, "exchange": fallback["exchange"]}).mappings().all()
        return rows, fallback["exchange"]

    def _attach_flow_features(
        self,
        klines: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not bundle.get("enabled"):
            return klines
        interval = PERIOD_SECONDS[cfg["period"]]
        max_lag_ms = int(cfg.get("max_flow_lag_seconds") or 60) * 1000
        taker_ts = bundle["taker_ts"]
        buy_prefix = bundle["buy_prefix"]
        sell_prefix = bundle["sell_prefix"]
        metric_ts = bundle["metric_ts"]
        metrics = bundle["metrics"]

        for item in klines:
            decision_ms = self._decision_timestamp(item, cfg) * 1000
            feature: Dict[str, Any] = {
                "source": "local_market_flow",
                "available_metrics": [],
            }

            if taker_ts:
                # Records stamped at or before the bar close only (no look-ahead).
                end_idx = bisect.bisect_right(taker_ts, decision_ms)
                if end_idx > 0 and decision_ms - taker_ts[end_idx - 1] <= max_lag_ms:
                    win_start_ms = decision_ms - CVD_WINDOW_BARS * interval * 1000
                    start_idx = bisect.bisect_left(taker_ts, win_start_ms)
                    buy = buy_prefix[end_idx] - buy_prefix[start_idx]
                    sell = sell_prefix[end_idx] - sell_prefix[start_idx]
                    total = buy + sell
                    if total > 0:
                        delta_norm = (buy - sell) / total
                        feature["available_metrics"].append("pair_taker_volume")
                        feature["cvd_delta_norm"] = delta_norm
                        feature["taker_delta_norm"] = delta_norm
                        feature["taker_buy_sell_ratio"] = buy / sell if sell else 1.0
                        feature["taker_exchange"] = bundle.get("taker_exchange")
                        feature["taker_lag_seconds"] = round((decision_ms - taker_ts[end_idx - 1]) / 1000, 3)

            if metric_ts:
                idx = bisect.bisect_right(metric_ts, decision_ms) - 1
                if idx >= 0 and decision_ms - metric_ts[idx] <= max_lag_ms:
                    row = metrics[idx]
                    if row["open_interest"] is not None:
                        feature["available_metrics"].append("open_interest")
                        feature["open_interest"] = row["open_interest"]
                        prev_idx = bisect.bisect_right(metric_ts, decision_ms - interval * 1000) - 1
                        prev_oi = metrics[prev_idx]["open_interest"] if prev_idx >= 0 else None
                        feature["oi_change_pct"] = (
                            (row["open_interest"] - prev_oi) / prev_oi * 100 if prev_oi else 0.0
                        )
                    if row["funding_rate"] is not None:
                        feature["available_metrics"].append("funding_rate")
                        feature["funding_rate"] = row["funding_rate"]
                    feature["metrics_lag_seconds"] = round((decision_ms - metric_ts[idx]) / 1000, 3)

            if feature["available_metrics"]:
                item["flow"] = feature
        return klines

    def _audit_flow_features(
        self,
        klines: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        cfg: Dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        if not bundle.get("enabled"):
            return {"enabled": False, "warnings": []}
        decision_items = [
            item
            for item in klines
            if start_ts <= self._decision_timestamp(item, cfg) <= end_ts
        ]
        flow_items = [item for item in decision_items if item.get("flow")]
        taker_items = [
            item for item in flow_items if "pair_taker_volume" in item["flow"]["available_metrics"]
        ]
        expected = len(decision_items)
        coverage = round(len(flow_items) / expected * 100, 4) if expected else 0.0
        taker_coverage = round(len(taker_items) / expected * 100, 4) if expected else 0.0
        min_coverage = float(cfg.get("min_flow_coverage_pct") or 90)
        warnings = list(bundle.get("warnings") or [])
        if expected and coverage < min_coverage:
            warnings.append(f"flow coverage {coverage}% below {min_coverage}%")
        audit = {
            "enabled": True,
            "source": "local_market_flow",
            "taker_exchange": bundle.get("taker_exchange"),
            "metrics_exchange": bundle.get("metrics_exchange"),
            "records_loaded": int(bundle.get("taker_records") or 0) + int(bundle.get("metric_records") or 0),
            "decision_records": len(flow_items),
            "expected_decision_records": expected,
            "coverage_pct": coverage,
            "taker_coverage_pct": taker_coverage,
            "min_required_coverage_pct": min_coverage,
            "liquidation_available": False,
            "warnings": warnings,
            "strict": bool(cfg.get("strict_flow_quality", False)),
            "no_future_leakage": True,
        }
        if cfg.get("strict_flow_quality") and warnings:
            raise ValueError(f"Market-flow data quality check failed: {'; '.join(warnings)}")
        return audit
