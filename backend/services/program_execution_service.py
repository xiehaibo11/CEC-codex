"""
Program Trader execution service.
Handles signal-triggered and scheduled execution of bound programs.

Architecture:
- Programs are bound to AI Traders via AccountProgramBinding
- Each binding has its own trigger configuration (signal pools, interval)
- Execution uses the AI Trader's wallet for trading
"""

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware UTC.

    Database stores UTC time in 'timestamp without time zone' columns.
    The naive datetime from DB is already UTC, just missing the timezone marker.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

from database.connection import SessionLocal
from database.models import AccountProgramBinding, BinanceWallet
from program_trader.executor import execute_strategy
from program_trader.data_provider import DataProvider
from services.program_execution_context import ProgramExecutionContextMixin
from services.program_execution_logging import ProgramExecutionLoggingMixin
from services.program_execution_trading import ProgramExecutionTradingMixin

logger = logging.getLogger(__name__)


class ProgramExecutionService(
    ProgramExecutionContextMixin,
    ProgramExecutionLoggingMixin,
    ProgramExecutionTradingMixin,
):
    """Manages execution of bound programs when signals trigger."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._running_bindings: Dict[int, bool] = {}
        self._binding_locks: Dict[int, threading.Lock] = {}
        # Binding state cache for scheduled triggers (similar to AI Trader's strategies)
        self._binding_states: Dict[int, dict] = {}  # binding_id -> state dict
        self._last_cache_refresh: Optional[datetime] = None
        self._cache_refresh_interval = 60  # Refresh cache every 60 seconds
        logger.info("[ProgramExecution] Service initialized")

    def on_signal_triggered(
        self,
        symbol: str,
        pool: dict,
        market_data_snapshot: dict,
        triggered_signals: list,
    ):
        """Called when a signal pool triggers - execute bound programs."""
        pool_id = pool.get("pool_id")
        pool_name = pool.get("pool_name", "Unknown")

        logger.info(f"[ProgramExecution] Signal triggered: {pool_name} (pool_id={pool_id}) on {symbol}")

        db = SessionLocal()
        try:
            # Find active bindings that include this pool_id
            all_bindings = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.is_active == True,
                AccountProgramBinding.is_deleted != True
            ).all()

            # Filter bindings that have this pool_id in their signal_pool_ids
            bindings = []
            for binding in all_bindings:
                if binding.signal_pool_ids:
                    try:
                        pool_ids = json.loads(binding.signal_pool_ids)
                        if pool_id in pool_ids:
                            bindings.append(binding)
                    except:
                        pass

            if not bindings:
                logger.debug(f"[ProgramExecution] No bindings for pool_id={pool_id}")
                return

            logger.info(f"[ProgramExecution] Found {len(bindings)} bindings for pool_id={pool_id}")
            raw_trigger_type = pool.get("trigger_type", "signal")
            # Program Trader keeps a stable top-level trigger taxonomy: signal vs scheduled.
            # Wallet tracking is a signal-source subtype and should flow through wallet_event
            # / signal_source_type instead of becoming a third top-level trigger type.
            trigger_type = "signal" if raw_trigger_type == "wallet_signal" else raw_trigger_type
            for binding in bindings:
                self._execute_binding(
                    db,
                    binding,
                    symbol,
                    pool,
                    market_data_snapshot,
                    triggered_signals,
                    trigger_type=trigger_type,
                )

        except Exception as e:
            logger.error(f"[ProgramExecution] Error processing signal: {e}")
        finally:
            db.close()

    def on_price_update(self, symbol: str, price: float, event_time: datetime):
        """Called on price updates - check for scheduled triggers (like AI Trader)."""
        try:
            # Refresh binding cache periodically
            self._maybe_refresh_cache()

            # Check each binding for scheduled trigger
            for binding_id, state in list(self._binding_states.items()):
                if self._should_trigger_scheduled(binding_id, state, event_time):
                    # Scheduled triggers have no specific symbol (empty string)
                    self._execute_scheduled_trigger(binding_id, "", event_time)

        except Exception as e:
            logger.error(f"[ProgramExecution] Error in on_price_update: {e}")

    def _maybe_refresh_cache(self):
        """Refresh binding state cache if needed."""
        now = datetime.now(timezone.utc)
        if (self._last_cache_refresh is None or
            (now - self._last_cache_refresh).total_seconds() >= self._cache_refresh_interval):
            self._refresh_binding_cache()
            self._last_cache_refresh = now

    def _refresh_binding_cache(self):
        """Load active bindings with scheduled trigger enabled into cache."""
        db = SessionLocal()
        try:
            bindings = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.is_active == True,
                AccountProgramBinding.scheduled_trigger_enabled == True,
                AccountProgramBinding.is_deleted != True
            ).all()

            for binding in bindings:
                self._binding_states[binding.id] = {
                    "binding_id": binding.id,
                    "account_id": binding.account_id,
                    "program_id": binding.program_id,
                    "trigger_interval": binding.trigger_interval,
                    "last_trigger_at": _as_utc(binding.last_trigger_at),
                    "signal_pool_ids": json.loads(binding.signal_pool_ids) if binding.signal_pool_ids else [],
                }

            # Remove bindings that are no longer active/enabled
            active_ids = {b.id for b in bindings}
            for bid in list(self._binding_states.keys()):
                if bid not in active_ids:
                    del self._binding_states[bid]

            logger.debug(f"[ProgramExecution] Refreshed cache: {len(self._binding_states)} scheduled bindings")
        except Exception as e:
            logger.error(f"[ProgramExecution] Error refreshing cache: {e}")
        finally:
            db.close()

    def _should_trigger_scheduled(self, binding_id: int, state: dict, event_time: datetime) -> bool:
        """Check if binding should trigger based on scheduled interval."""
        # Check if already running
        if self._running_bindings.get(binding_id, False):
            return False

        trigger_interval = state.get("trigger_interval", 300)
        last_trigger_at = state.get("last_trigger_at")

        now_ts = event_time.timestamp()
        last_ts = last_trigger_at.timestamp() if last_trigger_at else 0
        time_diff = now_ts - last_ts

        if time_diff >= trigger_interval:
            logger.info(
                f"[ProgramExecution] Scheduled trigger for binding {binding_id}: "
                f"interval={trigger_interval}s, elapsed={time_diff:.1f}s"
            )
            return True

        return False

    def _execute_scheduled_trigger(self, binding_id: int, symbol: str, event_time: datetime):
        """Execute a scheduled trigger for a binding."""
        db = SessionLocal()
        try:
            binding = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.id == binding_id,
                AccountProgramBinding.is_active == True,
                AccountProgramBinding.is_deleted != True
            ).first()

            if not binding:
                logger.warning(f"[ProgramExecution] Binding {binding_id} not found or inactive")
                return

            # Build minimal pool/trigger context for scheduled execution
            pool = {
                "pool_id": None,
                "pool_name": None,
            }
            market_data_snapshot = {}
            triggered_signals = []

            # Execute with trigger_type="scheduled"
            self._execute_binding(
                db, binding, symbol, pool, market_data_snapshot, triggered_signals,
                trigger_type="scheduled", event_time=event_time
            )

        except Exception as e:
            logger.error(f"[ProgramExecution] Error executing scheduled trigger: {e}")
        finally:
            db.close()

    def _execute_binding(
        self,
        db,
        binding: AccountProgramBinding,
        symbol: str,
        pool: dict,
        market_data_snapshot: dict,
        triggered_signals: list,
        trigger_type: str = "signal",
        event_time: Optional[datetime] = None,
    ):
        """Execute a single binding (program + account combination)."""
        binding_id = binding.id
        if event_time is None:
            event_time = datetime.now(timezone.utc)

        # Get or create lock for this binding
        if binding_id not in self._binding_locks:
            self._binding_locks[binding_id] = threading.Lock()

        lock = self._binding_locks[binding_id]

        # Check if already running
        if not lock.acquire(blocking=False):
            logger.warning(f"[ProgramExecution] Binding {binding_id} already running, skipping")
            return

        try:
            self._running_bindings[binding_id] = True

            # Update last_trigger_at immediately (like AI Trader does)
            # This resets the scheduled trigger timer for both signal and scheduled triggers
            binding.last_trigger_at = event_time
            db.commit()

            # Also update cache
            if binding_id in self._binding_states:
                self._binding_states[binding_id]["last_trigger_at"] = event_time

            # Load related objects
            program = binding.program
            account = binding.account

            if not program or not account:
                logger.error(f"[ProgramExecution] Binding {binding_id} missing program or account")
                return

            logger.info(f"[ProgramExecution] Executing: {program.name} via {account.name} (trigger: {trigger_type})")

            # Get exchange from binding (default to hyperliquid for backward compatibility)
            exchange = getattr(binding, 'exchange', None) or 'hyperliquid'

            # Get wallet address for this account based on exchange
            wallet_address = self._get_wallet_address(db, account, exchange)

            # Get trading environment and create trading client
            from services.hyperliquid_environment import get_global_trading_mode, get_hyperliquid_client, get_leverage_settings

            environment = get_global_trading_mode(db)
            trading_client = None

            if exchange == "binance":
                # Use Binance trading client
                if wallet_address:  # wallet_address here is actually API key presence indicator
                    try:
                        from services.binance_trading_client import BinanceTradingClient
                        from utils.encryption import decrypt_private_key

                        binance_wallet = db.query(BinanceWallet).filter(
                            BinanceWallet.account_id == account.id,
                            BinanceWallet.environment == (environment or "mainnet"),
                            BinanceWallet.is_active == "true"
                        ).first()

                        if binance_wallet:
                            api_key = decrypt_private_key(binance_wallet.api_key_encrypted)
                            secret_key = decrypt_private_key(binance_wallet.secret_key_encrypted)
                            trading_client = BinanceTradingClient(api_key, secret_key, environment or "mainnet")
                        else:
                            logger.warning(f"[ProgramExecution] No active Binance wallet found for account {account.id} on {environment}")
                    except Exception as e:
                        logger.warning(f"[ProgramExecution] Failed to create Binance trading client: {e}")
                # Get leverage settings from BinanceWallet
                leverage_settings = self._get_binance_leverage_settings(db, account.id, environment or "mainnet")
            else:
                # Use Hyperliquid trading client (default)
                if environment and wallet_address:
                    try:
                        trading_client = get_hyperliquid_client(db, account.id, override_environment=environment)
                    except Exception as e:
                        logger.warning(f"[ProgramExecution] Failed to create Hyperliquid trading client: {e}")
                # Get leverage settings (same as AI Trader)
                leverage_settings = get_leverage_settings(db, account.id, environment or "mainnet")

            max_leverage = leverage_settings["max_leverage"]
            default_leverage = leverage_settings["default_leverage"]

            # Build MarketData with trading client (enable query recording for analysis)
            data_provider = DataProvider(
                db, account.id, environment or "mainnet", trading_client,
                record_queries=True, exchange=exchange
            )
            market_data = self._build_market_data(
                data_provider=data_provider,
                symbol=symbol,
                pool=pool,
                market_data_snapshot=market_data_snapshot,
                triggered_signals=triggered_signals,
                trigger_type=trigger_type,
                signal_source_type="wallet_tracking" if isinstance(pool.get("wallet_event"), dict) else None,
                environment=environment or "mainnet",
                max_leverage=max_leverage,
                default_leverage=default_leverage,
            )

            # Get params (binding override > program default)
            params = {}
            if program.params:
                try:
                    params = json.loads(program.params)
                except:
                    pass
            if binding.params_override:
                try:
                    override = json.loads(binding.params_override)
                    params.update(override)
                except:
                    pass

            # Execute strategy
            result = execute_strategy(program.code, market_data, params)

            # Determine if this is an actual trade (buy/sell/close) that needs quota check
            quota_exceeded = False
            quota_info = {}
            is_trade = False
            if result.success and result.decision:
                op = result.decision.operation.lower() if hasattr(result.decision, 'operation') else (result.decision.action.value if hasattr(result.decision, 'action') else "")
                is_trade = op in ["buy", "sell", "close"]

            # Check daily quota only for actual trades (buy/sell/close), not HOLD/errors
            if is_trade and exchange == "binance" and (environment or "mainnet") == "mainnet":
                binance_wallet = db.query(BinanceWallet).filter(
                    BinanceWallet.account_id == account.id,
                    BinanceWallet.environment == (environment or "mainnet"),
                    BinanceWallet.is_active == "true"
                ).first()
                if binance_wallet and binance_wallet.rebate_working is False:
                    quota_exceeded, quota_info = self._check_binance_daily_quota(db, account.id)
                    if quota_exceeded:
                        logger.warning(
                            f"[ProgramExecution] Binding {binding.id} ({program.name}) quota exceeded - "
                            f"Decision recorded but NOT executed ({quota_info['used']}/{quota_info['limit']})"
                        )
                        # Modify result to indicate quota exceeded
                        result.success = False
                        result.error = f"Daily quota exceeded ({quota_info['used']}/{quota_info['limit']})"

            # Log execution with full context for analysis
            log_id = self._log_execution(
                db, binding, symbol, pool, wallet_address, result, params,
                data_provider, market_data, environment or "mainnet", trigger_type, exchange
            )

            # If quota exceeded, don't proceed to handle decision (no trading)
            if quota_exceeded:
                return

            # Handle decision if successful
            if result.success and result.decision:
                order_result = self._handle_decision(
                    db, binding, result.decision, symbol, wallet_address,
                    exchange=exchange, trading_client=trading_client
                )
                # Update log with order result and create HyperliquidTrade if filled
                # Skip for HOLD decisions - they don't execute orders
                op = result.decision.operation.lower() if hasattr(result.decision, 'operation') else result.decision.action.value
                if log_id and op != "hold":
                    self._update_log_with_order(
                        db, log_id, order_result, binding, result.decision,
                        wallet_address, environment or "mainnet", exchange=exchange
                    )

        except Exception as e:
            logger.error(f"[ProgramExecution] Error executing binding {binding_id}: {e}")
        finally:
            self._running_bindings[binding_id] = False
            lock.release()

# Singleton instance
program_execution_service = ProgramExecutionService()
