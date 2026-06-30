"""
Signal Detection Service - trigger logging / persistence helpers.

Writes signal and pool trigger records to the database.
"""

import logging

from .states import _get_market_regime_for_trigger

logger = logging.getLogger(__name__)


class TriggerLogMixin:
    """Mixin providing database logging for signal/pool triggers."""

    def _log_pool_trigger(self, trigger_result: dict) -> int | None:
        """Log pool trigger to database and return the trigger_log_id."""
        try:
            import json
            from collections import Counter
            from database.connection import SessionLocal
            from sqlalchemy import text

            # Timeframe order for tie-breaking (smaller = more granular = preferred)
            TIMEFRAME_ORDER = {"1m": 1, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "4h": 6, "1d": 7}

            db = SessionLocal()
            try:
                def _format_signal_for_log(s: dict) -> dict:
                    """Format signal data for logging, handling standard, taker_volume, and macd signals."""
                    base = {
                        "signal_id": s["signal_id"],
                        "signal_name": s["signal_name"],
                        "metric": s["metric"],
                    }
                    if s["metric"] == "taker_volume":
                        # taker_volume uses different field names
                        base["current_value"] = s.get("ratio")  # Use ratio as display value
                        base["threshold"] = s.get("ratio_threshold")
                        base["direction"] = s.get("actual_direction")
                        base["volume"] = s.get("total")
                        base["volume_threshold"] = s.get("volume_threshold")
                    elif s["metric"] == "macd":
                        # MACD event-based signal
                        base["event_types"] = s.get("event_types")
                        base["triggered_event"] = s.get("triggered_event")
                        base["values"] = s.get("values")
                        base["cross_strength"] = s.get("cross_strength")
                    else:
                        base["current_value"] = s.get("current_value")
                        base["threshold"] = s.get("threshold")
                        base["operator"] = s.get("operator")
                    # Persist factor effectiveness if present
                    if "factor_effectiveness" in s:
                        base["factor_effectiveness"] = s["factor_effectiveness"]
                    return base

                # Build trigger value data
                trigger_value_data = {
                    "logic": trigger_result["logic"],
                    "signals_triggered": [
                        _format_signal_for_log(s)
                        for s in trigger_result["signals_triggered"]
                    ],
                }

                # Add debug snapshots for Binance triggers (for troubleshooting)
                debug_snapshots = []
                for s in trigger_result["signals_triggered"]:
                    if "debug_snapshot" in s:
                        debug_snapshots.append({
                            "signal_id": s["signal_id"],
                            "signal_name": s["signal_name"],
                            "snapshot": s["debug_snapshot"]
                        })
                if debug_snapshots:
                    trigger_value_data["debug_snapshots"] = debug_snapshots

                trigger_value_json = json.dumps(trigger_value_data)

                # Determine the most common time_window from triggered signals
                time_windows = [
                    s.get("time_window", "5m")
                    for s in trigger_result["signals_triggered"]
                ]
                if time_windows:
                    # Count occurrences of each time_window
                    tw_counts = Counter(time_windows)
                    max_count = max(tw_counts.values())
                    # Get all time_windows with max count (handle ties)
                    candidates = [tw for tw, count in tw_counts.items() if count == max_count]
                    # On tie, prefer smaller (more granular) timeframe
                    trigger_timeframe = min(candidates, key=lambda x: TIMEFRAME_ORDER.get(x, 99))
                else:
                    logger.warning("No time_window found in triggered signals, using default 5m")
                    trigger_timeframe = "5m"

                # Get market regime for this trigger using the determined timeframe
                market_regime = _get_market_regime_for_trigger(
                    trigger_result["symbol"], trigger_timeframe
                )

                # Insert and return the new trigger_log_id
                result = db.execute(
                    text("""
                        INSERT INTO signal_trigger_logs
                        (pool_id, symbol, trigger_value, triggered_at, market_regime)
                        VALUES (:pool_id, :symbol, CAST(:trigger_value AS jsonb), NOW(), :market_regime)
                        RETURNING id
                    """),
                    {
                        "pool_id": trigger_result["pool_id"],
                        "symbol": trigger_result["symbol"],
                        "trigger_value": trigger_value_json,
                        "market_regime": market_regime,
                    }
                )
                trigger_log_id = result.scalar()
                db.commit()

                signals_info = ", ".join([
                    s["signal_name"] for s in trigger_result["signals_triggered"]
                ])
                logger.info(
                    f"Pool triggered: {trigger_result['pool_name']} ({trigger_result['logic']}) "
                    f"on {trigger_result['symbol']} - signals: [{signals_info}] "
                    f"(trigger_log_id={trigger_log_id}, regime_tf={trigger_timeframe})"
                )
                return trigger_log_id
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to log pool trigger: {e}")
            return None

    def _log_taker_volume_trigger(self, trigger_result: dict):
        """Log taker_volume signal trigger to database"""
        try:
            import json
            from database.connection import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                trigger_value_json = json.dumps({
                    "direction": trigger_result["actual_direction"],
                    "buy": trigger_result["buy"],
                    "sell": trigger_result["sell"],
                    "total": trigger_result["total"],
                    "ratio": trigger_result["ratio"],
                    "ratio_threshold": trigger_result["ratio_threshold"],
                    "volume_threshold": trigger_result["volume_threshold"],
                })

                # Get market regime for this trigger
                market_regime = _get_market_regime_for_trigger(trigger_result["symbol"])

                db.execute(
                    text("""
                        INSERT INTO signal_trigger_logs
                        (signal_id, symbol, trigger_value, triggered_at, market_regime)
                        VALUES (:signal_id, :symbol, CAST(:trigger_value AS jsonb), NOW(), :market_regime)
                    """),
                    {
                        "signal_id": trigger_result["signal_id"],
                        "symbol": trigger_result["symbol"],
                        "trigger_value": trigger_value_json,
                        "market_regime": market_regime,
                    }
                )
                db.commit()
                logger.info(
                    f"Taker volume signal triggered: {trigger_result['signal_name']} on {trigger_result['symbol']} "
                    f"(direction={trigger_result['actual_direction']}, ratio={trigger_result['ratio']:.2f}, "
                    f"buy={trigger_result['buy']:.0f}, sell={trigger_result['sell']:.0f})"
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to log taker volume trigger: {e}")

    def _log_trigger(self, trigger_result: dict):
        """Log signal trigger to database"""
        try:
            import json
            from database.connection import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                # Store trigger details as JSONB
                trigger_value_json = json.dumps({
                    "value": trigger_result["trigger_value"],
                    "threshold": trigger_result["threshold"],
                    "operator": trigger_result["operator"],
                    "metric": trigger_result["metric"],
                })

                # Get market regime for this trigger
                market_regime = _get_market_regime_for_trigger(trigger_result["symbol"])

                db.execute(
                    text("""
                        INSERT INTO signal_trigger_logs
                        (signal_id, symbol, trigger_value, triggered_at, market_regime)
                        VALUES (:signal_id, :symbol, CAST(:trigger_value AS jsonb), NOW(), :market_regime)
                    """),
                    {
                        "signal_id": trigger_result["signal_id"],
                        "symbol": trigger_result["symbol"],
                        "trigger_value": trigger_value_json,
                        "market_regime": market_regime,
                    }
                )
                db.commit()
                logger.info(
                    f"Signal triggered: {trigger_result['signal_name']} on {trigger_result['symbol']} "
                    f"(value={trigger_result['trigger_value']:.4f}, threshold={trigger_result['threshold']})"
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to log signal trigger: {e}")
