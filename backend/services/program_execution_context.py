"""Context, wallet, quota, and MarketData helpers for Program Trader execution."""
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import func

from config.settings import BINANCE_DAILY_QUOTA_LIMIT
from database.models import (
    AIDecisionLog,
    Account,
    BinanceWallet,
    HyperliquidWallet,
    ProgramExecutionLog,
)
from program_trader.data_provider import DataProvider
from program_trader.models import MarketData

logger = logging.getLogger(__name__)


class ProgramExecutionContextMixin:
    """Shared context helpers used while executing a program binding."""

    def _is_premium_user(self, db) -> bool:
        """Membership removed: all features unlocked for self-hosted use."""
        return True

    def _check_binance_daily_quota(self, db, account_id: int) -> Tuple[bool, Dict[str, int]]:
        """Check if Binance mainnet daily quota is exceeded."""
        if self._is_premium_user(db):
            return False, {
                "used": 0,
                "limit": BINANCE_DAILY_QUOTA_LIMIT,
                "remaining": BINANCE_DAILY_QUOTA_LIMIT,
            }

        today_start_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ai_count = db.query(func.count(AIDecisionLog.id)).filter(
            AIDecisionLog.account_id == account_id,
            AIDecisionLog.exchange == "binance",
            AIDecisionLog.hyperliquid_environment == "mainnet",
            AIDecisionLog.created_at >= today_start_utc,
            AIDecisionLog.operation.in_(["buy", "sell", "close"]),
        ).scalar() or 0

        program_count = db.query(func.count(ProgramExecutionLog.id)).filter(
            ProgramExecutionLog.account_id == account_id,
            ProgramExecutionLog.exchange == "binance",
            ProgramExecutionLog.environment == "mainnet",
            ProgramExecutionLog.created_at >= today_start_utc,
            ProgramExecutionLog.decision_action.in_(["buy", "sell", "close"]),
        ).scalar() or 0

        used = ai_count + program_count
        remaining = max(0, BINANCE_DAILY_QUOTA_LIMIT - used)
        return used >= BINANCE_DAILY_QUOTA_LIMIT, {
            "used": used,
            "limit": BINANCE_DAILY_QUOTA_LIMIT,
            "remaining": remaining,
        }

    def _get_wallet_address(self, db, account: Account, exchange: str = "hyperliquid") -> Optional[str]:
        """Get the active wallet address for an account based on exchange."""
        from services.hyperliquid_environment import get_global_trading_mode

        environment = get_global_trading_mode(db)
        if not environment:
            return None

        if exchange == "binance":
            wallet = db.query(BinanceWallet).filter(
                BinanceWallet.account_id == account.id,
                BinanceWallet.environment == environment,
                BinanceWallet.is_active == "true",
            ).first()
            return "binance_configured" if wallet and wallet.api_key_encrypted else None

        wallet = db.query(HyperliquidWallet).filter(
            HyperliquidWallet.account_id == account.id,
            HyperliquidWallet.environment == environment,
            HyperliquidWallet.is_active == "true",
        ).first()
        return wallet.wallet_address if wallet else None

    def _get_binance_leverage_settings(self, db, account_id: int, environment: str) -> dict:
        """Get leverage settings from BinanceWallet."""
        wallet = db.query(BinanceWallet).filter(
            BinanceWallet.account_id == account_id,
            BinanceWallet.environment == environment,
            BinanceWallet.is_active == "true",
        ).first()
        if wallet:
            return {
                "max_leverage": wallet.max_leverage or 10,
                "default_leverage": wallet.default_leverage or 3,
            }
        return {"max_leverage": 10, "default_leverage": 3}

    def _build_market_data(
        self,
        data_provider: DataProvider,
        symbol: str,
        pool: dict,
        market_data_snapshot: dict,
        triggered_signals: list,
        trigger_type: str = "signal",
        signal_source_type: Optional[str] = None,
        environment: str = "mainnet",
        max_leverage: int = 10,
        default_leverage: int = 3,
    ) -> MarketData:
        """Build MarketData object for strategy execution."""
        account_info = data_provider.get_account_info()
        signal_pool_name = pool.get("pool_name", "") or ""
        pool_logic = pool.get("logic", "OR") or "OR"
        wallet_event = pool.get("wallet_event") if signal_source_type == "wallet_tracking" else None
        trigger_market_regime = self._build_trigger_market_regime(
            data_provider,
            symbol,
            triggered_signals,
            trigger_type,
            signal_source_type,
        )

        return MarketData(
            available_balance=account_info.get("available_balance", 0.0),
            total_equity=account_info.get("total_equity", 0.0),
            used_margin=account_info.get("used_margin", 0.0),
            margin_usage_percent=account_info.get("margin_usage_percent", 0.0),
            maintenance_margin=account_info.get("maintenance_margin", 0.0),
            positions=data_provider.get_positions(),
            recent_trades=data_provider.get_recent_trades(),
            open_orders=data_provider.get_open_orders(),
            trigger_symbol=symbol,
            trigger_type=trigger_type,
            signal_pool_name=signal_pool_name,
            pool_logic=pool_logic,
            triggered_signals=triggered_signals or [],
            signal_source_type=signal_source_type,
            wallet_event=wallet_event if isinstance(wallet_event, dict) else None,
            trigger_market_regime=trigger_market_regime,
            environment=environment,
            max_leverage=max_leverage,
            default_leverage=default_leverage,
            _data_provider=data_provider,
        )

    def _build_trigger_market_regime(
        self,
        data_provider: DataProvider,
        symbol: str,
        triggered_signals: list,
        trigger_type: str,
        signal_source_type: Optional[str],
    ):
        if trigger_type != "signal" or signal_source_type == "wallet_tracking" or not symbol:
            return None

        timeframe = "5m"
        if triggered_signals:
            timeframe = triggered_signals[0].get("time_window", "5m")
        return data_provider.get_regime(symbol, timeframe)


def load_json_dict(value: Optional[str]) -> dict:
    """Best-effort JSON dict parser for stored program/binding params."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
