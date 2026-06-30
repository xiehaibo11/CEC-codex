"""
Signal Detection Service - main orchestrator.

Detects signal triggers based on market flow data.
Uses edge-triggered logic: only triggers when condition changes from False to True.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any

from .states import SignalState, PoolState
from .conditions import ConditionCheckMixin
from .metrics import MetricMixin
from .persistence import TriggerLogMixin

logger = logging.getLogger(__name__)


class SignalDetectionService(ConditionCheckMixin, MetricMixin, TriggerLogMixin):
    """
    Service for detecting signal triggers based on market flow data.
    Implements edge-triggered logic to avoid repeated triggers.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Signal states for edge detection: {(signal_id, symbol): SignalState}
        self.signal_states: Dict[tuple, SignalState] = {}

        # Pool states for edge detection: {(pool_id, symbol): PoolState}
        self.pool_states: Dict[tuple, PoolState] = {}

        # Cache of enabled signal pools and their signals
        self._signal_pools_cache: List[dict] = []
        self._signals_cache: Dict[int, dict] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 60  # Refresh cache every 60 seconds

        # Callbacks for signal triggers (used by trading_strategy.py)
        self._trigger_callbacks: List[callable] = []

        logger.info("SignalDetectionService initialized")

    def subscribe_signal_triggers(self, callback: callable) -> None:
        """Register a callback to be called when a signal pool triggers.

        Callback signature: callback(symbol: str, pool: dict, market_data: dict, triggered_signals: list)
        """
        if callback not in self._trigger_callbacks:
            self._trigger_callbacks.append(callback)
            logger.info(f"Signal trigger callback registered: {callback.__name__ if hasattr(callback, '__name__') else callback}")

    def unsubscribe_signal_triggers(self, callback: callable) -> None:
        """Unregister a signal trigger callback."""
        if callback in self._trigger_callbacks:
            self._trigger_callbacks.remove(callback)
            logger.info(f"Signal trigger callback unregistered: {callback.__name__ if hasattr(callback, '__name__') else callback}")

    def detect_signals(
        self, symbol: str, market_data: Dict[str, Any], exchange: str = None
    ) -> List[dict]:
        """
        Detect triggered signals for a symbol based on current market data.
        Returns list of triggered pools (edge-triggered at pool level).

        Args:
            symbol: Trading symbol (e.g., "BTC")
            market_data: Current market data context
            exchange: Filter by exchange ("hyperliquid", "binance", or None for all)

        Pool-level logic:
        - OR: Pool triggers when ANY signal condition is met (and pool was not active)
        - AND: Pool triggers when ALL signal conditions are met (and pool was not active)
        """
        triggered_pools = []

        try:
            # Refresh cache if needed
            self._refresh_cache_if_needed()

            # Get all enabled signal pools that monitor this symbol
            relevant_pools = [
                pool for pool in self._signal_pools_cache
                if pool.get("enabled") and symbol in pool.get("symbols", [])
                and (exchange is None or pool.get("exchange", "hyperliquid") == exchange)
            ]

            if not relevant_pools:
                return []

            # Process each pool
            for pool in relevant_pools:
                pool_trigger = self._check_pool_trigger(pool, symbol, market_data)
                if pool_trigger:
                    triggered_pools.append(pool_trigger)
                    # Notify all registered callbacks
                    self._notify_callbacks(symbol, pool_trigger, market_data)

        except Exception as e:
            logger.error(f"Error detecting signals for {symbol}: {e}", exc_info=True)

        return triggered_pools

    def _notify_callbacks(self, symbol: str, pool_trigger: dict, market_data: Dict[str, Any]) -> None:
        """Notify all registered callbacks about a signal pool trigger."""
        pool_name = pool_trigger.get("pool_name", "Unknown")
        pool_id = pool_trigger.get("pool_id")
        print(f"[SignalDetection] _notify_callbacks called for pool {pool_name}, callbacks count: {len(self._trigger_callbacks)}")

        # Bot push notification for signal pool triggers
        try:
            from database.connection import SessionLocal
            from api.bot_routes import get_notification_config_dict
            from services.bot_event_service import enqueue_system_event, push_event_to_all_channels
            import asyncio
            db = SessionLocal()
            try:
                notif_config = get_notification_config_dict(db)
                signal_pools_config = notif_config.get("signal_pools", {})
                # Check if this specific pool has notification enabled
                pool_id_str = str(pool_id) if pool_id else None
                if pool_id_str and signal_pools_config.get(pool_id_str, False):
                    triggered_signals = pool_trigger.get("signals_triggered", [])
                    event_data = {
                        "pool_name": pool_name,
                        "pool_id": pool_id,
                        "symbol": symbol,
                        "triggered_signals": triggered_signals,
                    }
                    if pool_trigger.get("trigger_type") == "wallet_signal":
                        event_data["wallet_event"] = pool_trigger.get("wallet_event")
                    results = enqueue_system_event(db, "signal_triggered", event_data)
                    if results:
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(push_event_to_all_channels(db, results))
                        except RuntimeError:
                            asyncio.run(push_event_to_all_channels(db, results))
            finally:
                db.close()
        except Exception as notif_err:
            logger.warning(f"Failed to send bot notification for signal pool: {notif_err}")

        if not self._trigger_callbacks:
            print("[SignalDetection] No callbacks registered, skipping notification!")
            return

        # Note: trigger_result uses "signals_triggered" key
        triggered_signals = pool_trigger.get("signals_triggered", [])
        for callback in self._trigger_callbacks:
            try:
                print(f"[SignalDetection] Calling callback: {callback}")
                callback(symbol, pool_trigger, market_data, triggered_signals)
                print(f"[SignalDetection] Callback completed successfully")
            except Exception as e:
                print(f"[SignalDetection] Error in callback: {e}")
                logger.error(f"Error in signal trigger callback: {e}", exc_info=True)

    def _refresh_cache_if_needed(self):
        """Refresh signal pools and signals cache if TTL expired"""
        now = time.time()
        if now - self._cache_time < self._cache_ttl:
            return

        try:
            from database.connection import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                # Load enabled signal pools
                result = db.execute(
                    text("""
                        SELECT id, pool_name, signal_ids, symbols, enabled, logic, exchange, source_type
                        FROM signal_pools
                        WHERE enabled = true
                          AND (is_deleted IS NULL OR is_deleted = false)
                          AND COALESCE(source_type, 'market_signals') = 'market_signals'
                    """)
                )
                self._signal_pools_cache = []
                for row in result.fetchall():
                    # Parse signal_ids and symbols - ORM defines as Text
                    signal_ids = row[2]
                    if isinstance(signal_ids, str):
                        try:
                            signal_ids = json.loads(signal_ids)
                        except json.JSONDecodeError:
                            signal_ids = []
                    symbols = row[3]
                    if isinstance(symbols, str):
                        try:
                            symbols = json.loads(symbols)
                        except json.JSONDecodeError:
                            symbols = []
                    self._signal_pools_cache.append({
                        "id": row[0],
                        "pool_name": row[1],
                        "signal_ids": signal_ids or [],
                        "symbols": symbols or [],
                        "enabled": row[4],
                        "logic": row[5] or "OR",
                        "exchange": row[6] or "hyperliquid",
                        "source_type": row[7] or "market_signals",
                    })

                # Load all enabled signals
                result = db.execute(
                    text("SELECT id, signal_name, description, trigger_condition, enabled, exchange FROM signal_definitions WHERE enabled = true AND (is_deleted IS NULL OR is_deleted = false)")
                )
                self._signals_cache = {}
                for row in result.fetchall():
                    # Parse trigger_condition - ORM defines as Text, so it may be string
                    trigger_cond = row[3]
                    if isinstance(trigger_cond, str):
                        try:
                            trigger_cond = json.loads(trigger_cond)
                        except json.JSONDecodeError:
                            trigger_cond = {}
                    self._signals_cache[row[0]] = {
                        "id": row[0],
                        "signal_name": row[1],
                        "description": row[2],
                        "trigger_condition": trigger_cond,
                        "enabled": row[4],
                        "exchange": row[5] or "hyperliquid"
                    }

                self._cache_time = now
                logger.debug(f"Signal cache refreshed: {len(self._signal_pools_cache)} pools, {len(self._signals_cache)} signals")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to refresh signal cache: {e}")

    def _check_pool_trigger(
        self, pool: dict, symbol: str, market_data: Dict[str, Any]
    ) -> Optional[dict]:
        """
        Check if a signal pool should trigger based on its logic (AND/OR).
        Implements edge-triggered logic at pool level.
        """
        pool_id = pool["id"]
        pool_name = pool["pool_name"]
        signal_ids = pool.get("signal_ids", [])
        logic = pool.get("logic", "OR").upper()

        if not signal_ids:
            return None

        # Get or create pool state
        pool_state_key = (pool_id, symbol)
        if pool_state_key not in self.pool_states:
            self.pool_states[pool_state_key] = PoolState(pool_id=pool_id, symbol=symbol)
        pool_state = self.pool_states[pool_state_key]

        # Check each signal's condition (without triggering)
        signals_met = {}
        signal_details = {}

        for signal_id in signal_ids:
            signal_def = self._signals_cache.get(signal_id)
            if not signal_def or not signal_def.get("enabled"):
                continue

            condition_result = self._check_signal_condition(
                signal_id, signal_def, symbol, market_data
            )
            if condition_result is not None:
                signals_met[signal_id] = condition_result["condition_met"]
                signal_details[signal_id] = condition_result

        if not signals_met:
            return None

        # Determine pool condition based on logic
        if logic == "AND":
            pool_condition_met = all(signals_met.values())
        else:  # OR
            pool_condition_met = any(signals_met.values())

        # Edge detection at pool level
        was_active = pool_state.is_active
        should_trigger = pool_condition_met and not was_active

        # DEBUG LOG: Edge detection state (only when state changes or trigger happens)
        if should_trigger or (pool_condition_met != was_active):
            print(f"[EdgeDetect] pool={pool_id}:{pool_name} symbol={symbol} was_active={was_active} pool_met={pool_condition_met} trigger={should_trigger} state_id={id(pool_state)} states_count={len(self.pool_states)}", flush=True)

        # Update pool state
        pool_state.is_active = pool_condition_met
        pool_state.signal_conditions_met = signals_met
        pool_state.last_check_time = time.time()

        # Log signal conditions for debugging
        met_signals = [sid for sid, met in signals_met.items() if met]
        if met_signals:
            logger.info(
                f"[PoolCheck] {pool_name} ({logic}) on {symbol}: "
                f"signals_met={met_signals}, pool_active={pool_condition_met}, "
                f"was_active={was_active}, trigger={should_trigger}"
            )

        if should_trigger:
            # Build trigger result with all signal details
            trigger_result = {
                "pool_id": pool_id,
                "pool_name": pool_name,
                "symbol": symbol,
                "logic": logic,
                "trigger_time": time.time(),
                "signals_triggered": [
                    signal_details[sid] for sid in met_signals
                ],
                "all_signals": signal_details,
            }
            # Log to database and get trigger_log_id for tracking
            trigger_log_id = self._log_pool_trigger(trigger_result)
            trigger_result["trigger_log_id"] = trigger_log_id
            return trigger_result

        return None

    def get_signal_states(self) -> Dict[str, Any]:
        """Get current signal states for debugging/monitoring"""
        return {
            "signal_states": {
                f"{state.signal_id}:{state.symbol}": {
                    "is_active": state.is_active,
                    "last_value": state.last_value,
                    "last_check_time": state.last_check_time,
                }
                for state_key, state in self.signal_states.items()
            },
            "pool_states": {
                f"{state.pool_id}:{state.symbol}": {
                    "is_active": state.is_active,
                    "signal_conditions_met": state.signal_conditions_met,
                    "last_check_time": state.last_check_time,
                }
                for state_key, state in self.pool_states.items()
            }
        }

    def reset_state(self, signal_id: int = None, pool_id: int = None, symbol: str = None):
        """Reset signal and pool states (useful for testing)"""
        if signal_id is None and pool_id is None and symbol is None:
            self.signal_states.clear()
            self.pool_states.clear()
        else:
            # Reset signal states
            if signal_id is not None or symbol is not None:
                keys_to_remove = [
                    k for k in self.signal_states.keys()
                    if (signal_id is None or k[0] == signal_id) and
                       (symbol is None or k[1] == symbol)
                ]
                for k in keys_to_remove:
                    del self.signal_states[k]

            # Reset pool states
            if pool_id is not None or symbol is not None:
                keys_to_remove = [
                    k for k in self.pool_states.keys()
                    if (pool_id is None or k[0] == pool_id) and
                       (symbol is None or k[1] == symbol)
                ]
                for k in keys_to_remove:
                    del self.pool_states[k]


# Singleton instance
signal_detection_service = SignalDetectionService()
