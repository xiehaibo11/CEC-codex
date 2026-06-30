"""Hyper AI read-only query handlers: system overview, wallet status, API reference,
market data (klines/regime/flow), system logs, contact, trading environment, watchlist."""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database.models import SystemConfig

logger = logging.getLogger(__name__)


def execute_get_system_overview(db: Session) -> str:
    """Get high-level system status summary."""
    from database.models import (
        Account, HyperliquidWallet, BinanceWallet, PromptTemplate,
        TradingProgram, SignalPool, AccountPromptBinding, AccountProgramBinding,
        HyperliquidPosition
    )

    try:
        result = {
            "wallets": {"hyperliquid": {}, "binance": {}},
            "ai_traders": {"total": 0, "active": 0, "using_prompt": 0, "using_program": 0},
            "strategies": {"prompts": 0, "programs": 0},
            "signal_pools": {"hyperliquid": 0, "binance": 0},
            "open_positions": {}
        }

        # Count wallets by exchange and environment
        hl_wallets = db.query(
            HyperliquidWallet.environment, func.count(HyperliquidWallet.id)
        ).filter(HyperliquidWallet.is_active == "true").group_by(HyperliquidWallet.environment).all()
        for env, count in hl_wallets:
            result["wallets"]["hyperliquid"][env] = count

        bn_wallets = db.query(
            BinanceWallet.environment, func.count(BinanceWallet.id)
        ).filter(BinanceWallet.is_active == "true").group_by(BinanceWallet.environment).all()
        for env, count in bn_wallets:
            result["wallets"]["binance"][env] = count

        # Count AI Traders
        total_traders = db.query(Account).filter(Account.is_active == "true", Account.is_deleted != True).count()
        active_traders = db.query(Account).filter(
            Account.is_active == "true",
            Account.auto_trading_enabled == "true",
            Account.is_deleted != True
        ).count()
        result["ai_traders"]["total"] = total_traders
        result["ai_traders"]["active"] = active_traders

        # Count by strategy type
        prompt_bindings = db.query(AccountPromptBinding).filter(AccountPromptBinding.is_deleted != True).count()
        program_bindings = db.query(AccountProgramBinding).filter(
            AccountProgramBinding.is_active == True,
            AccountProgramBinding.is_deleted != True
        ).count()
        result["ai_traders"]["using_prompt"] = prompt_bindings
        result["ai_traders"]["using_program"] = program_bindings

        # Count strategies
        user_prompts = db.query(PromptTemplate).filter(
            PromptTemplate.is_system == "false",
            PromptTemplate.is_deleted == "false"
        ).count()
        programs = db.query(TradingProgram).filter(TradingProgram.is_deleted != True).count()
        result["strategies"]["prompts"] = user_prompts
        result["strategies"]["programs"] = programs

        # Count signal pools by exchange
        pools = db.query(
            SignalPool.exchange, func.count(SignalPool.id)
        ).filter(SignalPool.enabled == True, SignalPool.is_deleted != True).group_by(SignalPool.exchange).all()
        for exchange, count in pools:
            result["signal_pools"][exchange or "hyperliquid"] = count

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"[get_system_overview] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_wallet_status(db: Session, exchange: str = "all", environment: str = "all") -> str:
    """Get wallet balance and position summary using real-time API (same as frontend)."""
    from database.models import HyperliquidWallet, BinanceWallet, Account
    from services.hyperliquid_environment import get_hyperliquid_client
    from services.binance_trading_client import BinanceTradingClient
    from utils.encryption import decrypt_private_key

    try:
        wallets = []

        # Query Hyperliquid wallets - use real-time API
        if exchange in ["all", "hyperliquid"]:
            hl_query = db.query(HyperliquidWallet, Account).join(
                Account, HyperliquidWallet.account_id == Account.id
            ).filter(HyperliquidWallet.is_active == "true")

            if environment != "all":
                hl_query = hl_query.filter(HyperliquidWallet.environment == environment)

            for wallet, account in hl_query.all():
                try:
                    # Use get_hyperliquid_client to support API Wallet mode
                    client = get_hyperliquid_client(db, account.id, override_environment=wallet.environment)
                    account_state = client.get_account_state(db)

                    wallet_info = {
                        "exchange": "hyperliquid",
                        "environment": wallet.environment,
                        "wallet_address": wallet.wallet_address[:10] + "..." + wallet.wallet_address[-6:],
                        "trader_id": account.id,
                        "trader_name": account.name,
                        "balance": {
                            "total_equity": float(account_state.get("total_equity", 0)),
                            "available_balance": float(account_state.get("available_balance", 0)),
                            "used_margin": float(account_state.get("used_margin", 0))
                        },
                        "positions": [],
                        "last_updated": "real-time"
                    }

                    # Get positions from API response
                    for pos in account_state.get("positions", []):
                        szi = float(pos.get("szi", 0) or 0)
                        if szi != 0:
                            wallet_info["positions"].append({
                                "symbol": pos.get("coin", ""),
                                "size": abs(szi),
                                "side": "long" if szi > 0 else "short",
                                "unrealized_pnl": float(pos.get("unrealized_pnl", 0) or 0)
                            })

                    wallets.append(wallet_info)
                except Exception as e:
                    logger.warning(f"[get_wallet_status] Failed to get Hyperliquid data for {account.name}: {e}")
                    wallets.append({
                        "exchange": "hyperliquid",
                        "environment": wallet.environment,
                        "wallet_address": wallet.wallet_address[:10] + "..." + wallet.wallet_address[-6:],
                        "trader_id": account.id,
                        "trader_name": account.name,
                        "balance": {"total_equity": 0, "available_balance": 0, "used_margin": 0},
                        "positions": [],
                        "error": str(e)
                    })

        # Query Binance wallets - use real-time API
        if exchange in ["all", "binance"]:
            bn_query = db.query(BinanceWallet, Account).join(
                Account, BinanceWallet.account_id == Account.id
            ).filter(BinanceWallet.is_active == "true")

            if environment != "all":
                bn_query = bn_query.filter(BinanceWallet.environment == environment)

            for wallet, account in bn_query.all():
                try:
                    # Decrypt API keys
                    api_key = decrypt_private_key(wallet.api_key_encrypted)
                    secret_key = decrypt_private_key(wallet.secret_key_encrypted)
                    client = BinanceTradingClient(api_key, secret_key, wallet.environment)
                    balance = client.get_balance()

                    wallet_info = {
                        "exchange": "binance",
                        "environment": wallet.environment,
                        "trader_id": account.id,
                        "trader_name": account.name,
                        "balance": {
                            "total_equity": float(balance.get("total_equity", 0)),
                            "available_balance": float(balance.get("available_balance", 0)),
                            "unrealized_pnl": float(balance.get("unrealized_pnl", 0))
                        },
                        "positions": [],
                        "last_updated": "real-time"
                    }
                    wallets.append(wallet_info)
                except Exception as e:
                    logger.warning(f"[get_wallet_status] Failed to get Binance data for {account.name}: {e}")
                    wallets.append({
                        "exchange": "binance",
                        "environment": wallet.environment,
                        "trader_id": account.id,
                        "trader_name": account.name,
                        "balance": {"total_equity": 0, "available_balance": 0, "unrealized_pnl": 0},
                        "positions": [],
                        "error": str(e)
                    })

        return json.dumps({"wallets": wallets}, indent=2)

    except Exception as e:
        logger.error(f"[get_wallet_status] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_api_reference(doc_type: str, api_type: str = "all", lang: str = "en") -> str:
    """Get API reference documentation."""
    try:
        if doc_type == "prompt":
            # Read prompt variables reference document
            filename = "PROMPT_VARIABLES_REFERENCE_ZH.md" if lang == "zh" else "PROMPT_VARIABLES_REFERENCE.md"
            doc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", filename)

            try:
                with open(doc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return json.dumps({"doc_type": "prompt", "lang": lang, "content": content})
            except FileNotFoundError:
                return json.dumps({"error": f"Document not found: {filename}"})

        elif doc_type == "program":
            # Return MarketData/Decision API docs from ai_program_service
            from services.ai_program_service import MARKET_API_DOCS, DECISION_API_DOCS

            if api_type == "market":
                content = MARKET_API_DOCS
            elif api_type == "decision":
                content = DECISION_API_DOCS
            else:
                content = MARKET_API_DOCS + "\n\n" + DECISION_API_DOCS

            return json.dumps({"doc_type": "program", "api_type": api_type, "content": content})

        else:
            return json.dumps({"error": f"Invalid doc_type: {doc_type}"})

    except Exception as e:
        logger.error(f"[get_api_reference] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_klines(db: Session, symbol: str, period: str = "1h", limit: int = 50, exchange: str = "hyperliquid") -> str:
    """Get K-line data for a symbol."""
    from database.models import CryptoKline

    try:
        limit = min(max(limit, 1), 200)

        klines = db.query(CryptoKline).filter(
            CryptoKline.exchange == exchange,
            CryptoKline.symbol == symbol.upper(),
            CryptoKline.period == period,
            CryptoKline.environment == "mainnet"
        ).order_by(CryptoKline.timestamp.desc()).limit(limit).all()

        candles = []
        for k in reversed(klines):
            candles.append({
                "time": datetime.utcfromtimestamp(k.timestamp).strftime("%Y-%m-%d %H:%M UTC"),
                "open": float(k.open_price) if k.open_price else 0,
                "high": float(k.high_price) if k.high_price else 0,
                "low": float(k.low_price) if k.low_price else 0,
                "close": float(k.close_price) if k.close_price else 0,
                "volume": float(k.volume) if k.volume else 0
            })

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "candles": candles,
            "count": len(candles)
        }, indent=2)

    except Exception as e:
        logger.error(f"[get_klines] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_market_regime(db: Session, symbol: str, period: str = "1h", exchange: str = "hyperliquid") -> str:
    """Get market regime classification for a symbol."""
    try:
        from program_trader.data_provider import DataProvider

        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)
        regime = data_provider.get_regime(symbol.upper(), period)

        if regime:
            return json.dumps({
                "symbol": symbol.upper(),
                "period": period,
                "exchange": exchange,
                "regime": regime.regime,
                "confidence": regime.conf
            }, indent=2)
        else:
            return json.dumps({
                "symbol": symbol.upper(),
                "period": period,
                "exchange": exchange,
                "regime": "unknown",
                "confidence": 0,
                "note": "Unable to determine market regime"
            })

    except Exception as e:
        logger.error(f"[get_market_regime] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_market_flow(db: Session, symbol: str, period: str = "1h", exchange: str = "hyperliquid") -> str:
    """Get market flow data for a symbol."""
    try:
        from program_trader.data_provider import DataProvider

        data_provider = DataProvider(db=db, account_id=0, environment="mainnet", exchange=exchange)

        flow = {}
        for metric in ["CVD", "OI", "OI_DELTA", "TAKER", "FUNDING"]:
            result = data_provider.get_flow(symbol.upper(), metric, period)
            if result:
                flow[metric] = result

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "exchange": exchange,
            "flow": flow
        }, indent=2)

    except Exception as e:
        logger.error(f"[get_market_flow] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_system_logs(db: Session, level: str = "error", limit: int = 20, trader_id: int = None) -> str:
    """Get recent system logs enriched with error registry metadata."""
    from services.system_logger import system_logger
    from services.error_registry import classify_error, get_severity_summary

    try:
        limit = min(max(limit, 1), 50)

        # Map level to min_level for system_logger
        min_level = None
        if level == "error":
            min_level = "ERROR"
        elif level == "warning":
            min_level = "WARNING"

        raw_logs = system_logger.get_logs(limit=limit, min_level=min_level)

        # Determine user's exchange from their wallets
        user_exchange = None
        try:
            from database.models import Account, HyperliquidWallet
            account = db.query(Account).first()
            if account:
                has_hl = db.query(HyperliquidWallet).filter(
                    HyperliquidWallet.account_id == account.id
                ).first() is not None
                has_bn = False
                try:
                    from database.models import BinanceWallet
                    has_bn = db.query(BinanceWallet).filter(
                        BinanceWallet.account_id == account.id
                    ).first() is not None
                except Exception:
                    pass
                if has_hl and not has_bn:
                    user_exchange = "hyperliquid"
                elif has_bn and not has_hl:
                    user_exchange = "binance"
        except Exception:
            pass

        # Enrich logs with registry metadata
        logs = []
        for log in raw_logs:
            msg = log.get("message", "")
            entry = {
                "time": log.get("timestamp", ""),
                "level": log.get("level", "INFO"),
                "category": log.get("category", ""),
                "message": msg,
            }
            match = classify_error(msg)
            if match:
                entry["registry"] = match
                # Mark irrelevant exchange errors
                if user_exchange and match["exchange"] not in ("all", user_exchange):
                    entry["registry"]["relevance"] = "other_exchange"
            logs.append(entry)

        # Build severity summary
        severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0, "NOISE": 0, "UNKNOWN": 0}
        for log in logs:
            reg = log.get("registry")
            sev = reg["severity"] if reg else "UNKNOWN"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        result = {
            "logs": logs,
            "total": len(logs),
            "severity_summary": severity_counts,
        }
        if user_exchange:
            result["user_exchange"] = user_exchange

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"[get_system_logs] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_contact_config() -> str:
    """Get support channel URLs."""
    import requests

    try:
        # Try to fetch from external API
        resp = requests.get("https://www.akooi.com/api/config/contact", timeout=5)
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)
    except Exception as e:
        logger.warning(f"[get_contact_config] Failed to fetch from API: {e}")

    # Fallback to defaults
    return json.dumps({
        "twitter": {"url": "https://x.com/GptHammer3309", "enabled": True},
        "telegram": {"url": "https://t.me/+RqxjT7Gttm9hOGEx", "enabled": True},
        "github": {"url": "https://github.com/xiehaibo11/CEC-codex", "enabled": True}
    }, indent=2)


def execute_get_trading_environment(db: Session) -> str:
    """Get current global trading environment."""
    from services.hyperliquid_environment import get_global_trading_mode

    try:
        environment = get_global_trading_mode(db)
        return json.dumps({
            "current_environment": environment,
            "description": "testnet" if environment == "testnet" else "mainnet (real money)",
            "note": "Environment affects which wallets are used and which exchange endpoints are called. To switch, use the mode switcher in the top-right of the UI."
        }, indent=2)
    except Exception as e:
        logger.error(f"[get_trading_environment] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_watchlist(db: Session) -> str:
    """Get symbol watchlist for all exchanges."""
    from services import hyperliquid_symbol_service, binance_symbol_service

    try:
        # Get Hyperliquid watchlist
        hl_selected = hyperliquid_symbol_service.get_selected_symbols()
        hl_default = [s["symbol"] for s in hyperliquid_symbol_service.DEFAULT_SYMBOLS]
        hl_is_default = set(hl_selected) == set(hl_default)

        # Get Binance watchlist
        bn_selected = binance_symbol_service.get_selected_symbols()
        bn_default = [s["symbol"] for s in binance_symbol_service.DEFAULT_SYMBOLS]
        bn_is_default = set(bn_selected) == set(bn_default)

        result = {
            "hyperliquid": {
                "symbols": hl_selected,
                "is_default_config": hl_is_default,
                "default_symbols": hl_default,
                "max_symbols": hyperliquid_symbol_service.MAX_WATCHLIST_SYMBOLS
            },
            "binance": {
                "symbols": bn_selected,
                "is_default_config": bn_is_default,
                "default_symbols": bn_default,
                "max_symbols": binance_symbol_service.MAX_WATCHLIST_SYMBOLS
            },
            "note": "Watchlist determines which symbols the system collects data for (K-lines, OI, CVD, funding). If you want to trade a symbol, it must be in the watchlist first."
        }

        # Add warning if using defaults
        warnings = []
        if hl_is_default:
            warnings.append("Hyperliquid watchlist is using default config (only BTC). Consider adding symbols you want to trade.")
        if bn_is_default:
            warnings.append("Binance watchlist is using default config (only BTC). Consider adding symbols you want to trade.")
        if warnings:
            result["warnings"] = warnings

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"[get_watchlist] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_update_watchlist(db: Session, exchange: str, symbols: List[str]) -> str:
    """Update symbol watchlist for a specific exchange."""
    from services import hyperliquid_symbol_service, binance_symbol_service

    try:
        if exchange not in ["hyperliquid", "binance"]:
            return json.dumps({"error": "exchange must be 'hyperliquid' or 'binance'"})

        if not symbols or not isinstance(symbols, list):
            return json.dumps({"error": "symbols must be a non-empty list"})

        # Normalize symbols to uppercase
        symbols = [s.upper() for s in symbols]

        if exchange == "hyperliquid":
            updated = hyperliquid_symbol_service.update_selected_symbols(symbols)
        else:
            updated = binance_symbol_service.update_selected_symbols(symbols)

        return json.dumps({
            "success": True,
            "exchange": exchange,
            "updated_symbols": updated,
            "note": "Watchlist updated. Data collection will now include these symbols. It may take a few minutes for historical data to be backfilled."
        }, indent=2)

    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.error(f"[update_watchlist] Error: {e}")
        return json.dumps({"error": str(e)})


