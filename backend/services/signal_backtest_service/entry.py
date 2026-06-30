"""Public backtest entry points for single signals."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.signal_backtest_service.base import logger, TIMEFRAME_MS


class BacktestEntryMixin:
    """Public backtest entry points for single signals."""

    def backtest_signal(
        self, db: Session, signal_id: int, symbol: str,
        kline_min_ts: int = None, kline_max_ts: int = None
    ) -> Dict[str, Any]:
        """
        Backtest a signal against historical data.
        Returns only trigger points - K-lines should be fetched separately via market API.

        Args:
            db: Database session
            signal_id: Signal definition ID
            symbol: Trading symbol (e.g., 'BTC')
            kline_min_ts: Minimum K-line timestamp in milliseconds (for filtering triggers)
            kline_max_ts: Maximum K-line timestamp in milliseconds (for filtering triggers)
        """
        logger.warning(f"[Backtest] START signal_id={signal_id} symbol={symbol} "
                       f"ts_range=[{kline_min_ts}, {kline_max_ts}]")

        # Clear bucket cache for fresh data
        self._bucket_cache = {}

        # Get signal definition
        result = db.execute(
            text("""
                SELECT id, signal_name, description, trigger_condition, enabled, exchange
                FROM signal_definitions WHERE id = :id AND (is_deleted IS NULL OR is_deleted = false)
            """),
            {"id": signal_id}
        )
        row = result.fetchone()
        if not row:
            logger.warning(f"[Backtest] Signal {signal_id} NOT FOUND in database")
            return {"error": "Signal not found"}

        exchange = row[5] if len(row) > 5 and row[5] else "hyperliquid"

        # Debug: log raw row data and types
        logger.warning(f"[Backtest] DB row: id={row[0]}, name={row[1]}, exchange={exchange}, "
                       f"trigger_condition type={type(row[3])}")

        # Handle trigger_condition - may be string (SQLite/some drivers) or dict (PostgreSQL JSONB)
        trigger_condition = row[3]
        if isinstance(trigger_condition, str):
            import json
            try:
                trigger_condition = json.loads(trigger_condition)
                logger.warning(f"[Backtest] Parsed trigger_condition from JSON string")
            except json.JSONDecodeError as e:
                logger.warning(f"[Backtest] Failed to parse trigger_condition: {e}")
                trigger_condition = {}

        signal_def = {
            "id": row[0],
            "signal_name": row[1],
            "description": row[2],
            "trigger_condition": trigger_condition if isinstance(trigger_condition, dict) else {},
            "enabled": row[4]
        }

        condition = signal_def.get("trigger_condition", {})
        metric = condition.get("metric") if isinstance(condition, dict) else None
        time_window = condition.get("time_window", "5m") if isinstance(condition, dict) else "5m"

        logger.warning(f"[Backtest] Signal found: name={signal_def['signal_name']}, "
                       f"metric={metric}, time_window={time_window}, condition={condition}")

        if not metric:
            logger.warning(f"[Backtest] Signal {signal_id} has no metric configured")
            return {"error": "Signal has no metric configured"}

        # Find triggers within the specified time range
        triggers = self._find_triggers_in_range(
            db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
        )

        logger.warning(f"[Backtest] END signal_id={signal_id} success, {len(triggers)} triggers found")
        return {
            "signal_id": signal_id,
            "signal_name": signal_def["signal_name"],
            "symbol": symbol,
            "time_window": time_window,
            "condition": condition,
            "trigger_count": len(triggers),
            "triggers": triggers,
        }

    def backtest_temp_signal(
        self, db: Session, symbol: str, trigger_condition: Dict,
        kline_min_ts: int = None, kline_max_ts: int = None,
        exchange: str = "hyperliquid"
    ) -> Dict[str, Any]:
        """
        Backtest a temporary signal configuration without saving to database.
        Used for AI signal creation preview.

        Args:
            db: Database session
            symbol: Trading symbol (e.g., 'BTC')
            trigger_condition: Signal trigger condition dict
            kline_min_ts: Minimum K-line timestamp in milliseconds
            kline_max_ts: Maximum K-line timestamp in milliseconds
            exchange: Exchange name (hyperliquid or binance)
        """
        # Clear bucket cache for fresh data
        self._bucket_cache = {}

        # Build temporary signal definition
        signal_def = {
            "id": None,
            "signal_name": "Temporary Preview",
            "description": "AI-generated signal preview",
            "trigger_condition": trigger_condition,
            "enabled": True
        }

        metric = trigger_condition.get("metric")
        time_window = trigger_condition.get("time_window", "5m")

        if not metric:
            return {"error": "Signal has no metric configured"}

        # Find triggers within the specified time range
        triggers = self._find_triggers_in_range(
            db, signal_def, symbol, time_window, kline_min_ts, kline_max_ts, exchange
        )

        return {
            "signal_id": None,
            "signal_name": "Temporary Preview",
            "symbol": symbol,
            "time_window": time_window,
            "condition": trigger_condition,
            "trigger_count": len(triggers),
            "triggers": triggers,
        }

