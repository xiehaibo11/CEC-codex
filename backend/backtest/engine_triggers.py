"""
Trigger generation for the Program Backtest Engine.

Builds signal trigger events (scheduled triggers are generated dynamically in
the event loop) and estimates total trigger counts for progress reporting.
Mixed into ProgramBacktestEngine; relies on self.db.
"""

import logging
from typing import List

from .models import BacktestConfig, TriggerEvent

logger = logging.getLogger(__name__)


class TriggerGenerationMixin:
    """Signal trigger generation and trigger-count estimation."""

    def _generate_trigger_events(self, config: BacktestConfig) -> List[TriggerEvent]:
        """Generate signal trigger events only. Scheduled triggers are handled dynamically."""
        from services.signal_backtest_service import signal_backtest_service
        from services.market_regime_service import get_market_regime

        events = []

        # Generate signal triggers
        for pool_id in config.signal_pool_ids:
            for symbol in config.symbols:
                try:
                    pool_result = signal_backtest_service.backtest_pool(
                        self.db, pool_id, symbol,
                        config.start_time_ms, config.end_time_ms
                    )

                    if "error" in pool_result:
                        logger.warning(f"Signal backtest error for pool {pool_id}: {pool_result['error']}")
                        continue

                    for t in pool_result.get("triggers", []):
                        # Get market regime at trigger time
                        regime_data = None
                        try:
                            regime_result = get_market_regime(
                                self.db, symbol, "5m",
                                use_realtime=True,
                                timestamp_ms=t["timestamp"],
                                exchange=config.exchange
                            )
                            if regime_result:
                                regime_data = {
                                    "regime": regime_result.get("regime", "noise"),
                                    "conf": regime_result.get("confidence", 0.0),
                                    "direction": regime_result.get("direction", "neutral"),
                                    "reason": regime_result.get("reason", ""),
                                    "indicators": regime_result.get("indicators", {}),
                                }
                        except Exception as e:
                            logger.debug(f"Failed to get regime at {t['timestamp']}: {e}")

                        events.append(TriggerEvent(
                            timestamp=t["timestamp"],
                            trigger_type="signal",
                            symbol=symbol,
                            pool_id=pool_id,
                            pool_name=pool_result.get("pool_name"),
                            pool_logic=pool_result.get("logic"),
                            triggered_signals=t.get("triggered_signals", []),
                            market_regime=regime_data,
                        ))
                except Exception as e:
                    logger.error(f"Failed to get signal triggers for pool {pool_id}: {e}")

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)

        # Log signal triggers count (scheduled triggers are dynamic)
        logger.info(f"Generated {len(events)} signal trigger events")

        return events

    def estimate_total_triggers(
        self,
        config: BacktestConfig,
        signal_triggers: List[TriggerEvent],
    ) -> int:
        """
        Estimate total trigger count including dynamic scheduled triggers.
        Uses same algorithm as run_event_loop_generator but only counts.
        """
        if not config.scheduled_interval_sec:
            return len(signal_triggers)

        scheduled_interval_ms = config.scheduled_interval_sec * 1000
        total = 0
        last_trigger_time = config.start_time_ms

        for signal_trigger in signal_triggers:
            # Count scheduled triggers before this signal
            next_scheduled_time = last_trigger_time + scheduled_interval_ms
            while next_scheduled_time < signal_trigger.timestamp:
                total += 1
                last_trigger_time = next_scheduled_time
                next_scheduled_time = last_trigger_time + scheduled_interval_ms
            # Count signal trigger
            total += 1
            last_trigger_time = signal_trigger.timestamp

        # Count remaining scheduled triggers
        next_scheduled_time = last_trigger_time + scheduled_interval_ms
        while next_scheduled_time <= config.end_time_ms:
            total += 1
            last_trigger_time = next_scheduled_time
            next_scheduled_time = last_trigger_time + scheduled_interval_ms

        return total
