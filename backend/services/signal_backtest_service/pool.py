"""Pool backtest dispatch and trigger combination."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class PoolDispatchMixin:
    """Pool backtest dispatch and trigger combination."""

    def backtest_pool(
        self, db: Session, pool_id: int, symbol: str,
        kline_min_ts: int = None, kline_max_ts: int = None
    ) -> Dict[str, Any]:
        """
        Backtest a signal pool against historical data.
        For AND logic: evaluates all signals at each check point with pool-level edge detection.
        For OR logic: combines individual signal triggers.

        Trigger timestamp precision by pool composition:
        ┌────────────────────────────┬─────────────────────────────────────────┐
        │ Pool type                  │ Trigger precision                       │
        ├────────────────────────────┼─────────────────────────────────────────┤
        │ Pure factor (OR/AND)       │ K-line close (e.g. 00:00, 04:00)       │
        │ Mixed factor+flow (OR)     │ Factor at K-close, flow at 15s-aligned │
        │ Mixed factor+flow (AND)    │ Whichever condition satisfies last —    │
        │                            │ could be K-close or 15s-aligned         │
        └────────────────────────────┴─────────────────────────────────────────┘
        Factor values persist between K-line closes. In mixed pools, factor
        conditions are evaluated at 15s check points using the latest closed
        K-line value. In pure-factor pools, check points align to K-line
        closes directly, avoiding unnecessary 15s granularity.
        """
        logger.warning(f"[Backtest] START pool_id={pool_id} symbol={symbol} "
                       f"ts_range=[{kline_min_ts}, {kline_max_ts}]")

        self._bucket_cache = {}

        # Get pool definition
        result = db.execute(
            text("""
                SELECT id, pool_name, signal_ids, symbols, enabled, logic, exchange, source_type, source_config
                FROM signal_pools WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
            """),
            {"id": pool_id}
        )
        row = result.fetchone()
        if not row:
            logger.warning(f"[Backtest] Pool {pool_id} NOT FOUND in database")
            return {"error": "Pool not found"}

        source_type = row[7] if len(row) > 7 and row[7] else "market_signals"
        if source_type != "market_signals":
            logger.warning(f"[Backtest] Pool {pool_id} source_type={source_type} does not support backtest")
            return {"error": f"Pool source type '{source_type}' does not support backtest"}

        exchange = row[6] if len(row) > 6 and row[6] else "hyperliquid"

        # Parse signal_ids and symbols - ORM defines as Text
        raw_signal_ids = row[2]
        if isinstance(raw_signal_ids, str):
            try:
                raw_signal_ids = json.loads(raw_signal_ids)
            except json.JSONDecodeError:
                raw_signal_ids = []
        raw_symbols = row[3]
        if isinstance(raw_symbols, str):
            try:
                raw_symbols = json.loads(raw_symbols)
            except json.JSONDecodeError:
                raw_symbols = []

        pool_def = {
            "id": row[0],
            "pool_name": row[1],
            "signal_ids": raw_signal_ids or [],
            "symbols": raw_symbols or [],
            "enabled": row[4],
            "logic": row[5] or "OR"
        }

        signal_ids = pool_def["signal_ids"]
        logger.warning(f"[Backtest] Pool found: name={pool_def['pool_name']}, "
                       f"logic={pool_def['logic']}, signal_ids={signal_ids}")

        if not signal_ids:
            logger.warning(f"[Backtest] Pool {pool_id} has no signals configured")
            return {"error": "Pool has no signals configured"}

        logic = pool_def["logic"]

        # For AND logic, use pool-level detection to match real-time behavior
        if logic == "AND":
            return self._backtest_pool_and_logic(
                db, pool_def, signal_ids, symbol, kline_min_ts, kline_max_ts, exchange
            )

        # For OR logic, also use pool-level edge detection to match real-time behavior
        return self._backtest_pool_or_logic(
            db, pool_def, signal_ids, symbol, kline_min_ts, kline_max_ts, exchange
        )

    def _combine_pool_triggers(
        self, signal_triggers: Dict[int, Dict], signal_names: Dict[int, str], logic: str
    ) -> List[Dict]:
        """
        Combine triggers from multiple signals based on pool logic.

        Args:
            signal_triggers: Dict mapping signal_id to {timestamp: trigger_data}
            signal_names: Dict mapping signal_id to signal name
            logic: 'AND' or 'OR'
        """
        if logic == "OR":
            # OR: Any signal triggers = pool triggers
            all_timestamps = set()
            for triggers in signal_triggers.values():
                all_timestamps.update(triggers.keys())

            combined = []
            for ts in sorted(all_timestamps):
                triggered_signals = []
                for signal_id, triggers in signal_triggers.items():
                    if ts in triggers:
                        triggered_signals.append({
                            "signal_id": signal_id,
                            "signal_name": signal_names.get(signal_id, f"Signal {signal_id}"),
                            "value": triggers[ts].get("value"),
                            "threshold": triggers[ts].get("threshold"),
                        })
                combined.append({
                    "timestamp": ts,
                    "triggered_signals": triggered_signals,
                    "trigger_type": "any",
                })
            return combined

        else:  # AND
            # AND: All signals must trigger at the same timestamp
            if not signal_triggers:
                return []

            # Find timestamps where ALL signals triggered
            common_timestamps = None
            for triggers in signal_triggers.values():
                ts_set = set(triggers.keys())
                if common_timestamps is None:
                    common_timestamps = ts_set
                else:
                    common_timestamps &= ts_set

            if not common_timestamps:
                return []

            combined = []
            for ts in sorted(common_timestamps):
                triggered_signals = []
                for signal_id, triggers in signal_triggers.items():
                    triggered_signals.append({
                        "signal_id": signal_id,
                        "signal_name": signal_names.get(signal_id, f"Signal {signal_id}"),
                        "value": triggers[ts].get("value"),
                        "threshold": triggers[ts].get("threshold"),
                    })
                combined.append({
                    "timestamp": ts,
                    "triggered_signals": triggered_signals,
                    "trigger_type": "all",
                })
            return combined

