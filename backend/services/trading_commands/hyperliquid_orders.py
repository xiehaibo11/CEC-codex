"""
Trading Commands - Hyperliquid AI-driven order placement.

Real perpetual trading on Hyperliquid (testnet/mainnet). All routing, price
clamping, sizing, leverage validation, retry, and order-placement logic is
preserved exactly as the original ``trading_commands`` implementation.
"""
import logging
from typing import Dict, Optional, Iterable, Any

from database.connection import SessionLocal
from database.models import Account
from services.ai_decision_service import call_ai_for_decision
from services.hyperliquid_symbol_service import (
    get_selected_symbols as get_hyperliquid_selected_symbols,
    get_available_symbol_map as get_hyperliquid_symbol_map,
)

from .helpers import _get_realtime_ticker_snapshot
from .hyperliquid_execution import _execute_hyperliquid_decision


logger = logging.getLogger(__name__)


def test_hyperliquid_function():
    return "test_success"

def place_ai_driven_hyperliquid_order(
    account_ids: Optional[Iterable[int]] = None,
    account_id: Optional[int] = None,
    bypass_auto_trading: bool = False,
    trigger_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Place Hyperliquid perpetual contract order based on AI decision.

    This function handles real trading on Hyperliquid exchange, supporting:
    - Perpetual contract trading (long/short)
    - Leverage (1x-50x based on account configuration)
    - Environment isolation (testnet/mainnet)
    - Position management

    Args:
        account_ids: Optional iterable of account IDs to process
        account_id: Optional single account ID to process
        trigger_context: Optional context about what triggered this decision (signal or scheduled)
    """

    try:
        from services.hyperliquid_environment import get_hyperliquid_client
    except Exception as e:
        logger.error(f"Error in place_ai_driven_hyperliquid_order start: {e}", exc_info=True)
        return

    # First, get accounts list with minimal database connection
    accounts = []
    db = SessionLocal()
    # PostgreSQL handles concurrent access natively
    try:
        # Handle single account strategy trigger (manual trigger)
        if account_id is not None:
            account = db.query(Account).filter(Account.id == account_id, Account.is_deleted != True).first()
            if not account or account.is_active != "true":
                logger.debug(f"Account {account_id} not found or inactive")
                return

            if not bypass_auto_trading and getattr(account, "auto_trading_enabled", "false") != "true":
                logger.debug(
                    "Account %s auto trading disabled - skipping Hyperliquid AI order",
                    account_id,
                )
                return

            accounts = [account]
        else:
            # Get all active accounts with auto trading enabled
            accounts = db.query(Account).filter(
                Account.is_active == "true",
                Account.auto_trading_enabled == "true",
                Account.is_deleted != True
            ).all()

            if not accounts:
                logger.debug("No active accounts with auto trading enabled")
                return

            if account_ids is not None:
                id_set = {int(acc_id) for acc_id in account_ids}
                accounts = [acc for acc in accounts if acc.id in id_set]
                if not accounts:
                    logger.debug(f"No matching Hyperliquid accounts for provided IDs: {account_ids}")
                    return
    finally:
        db.close()

    # Determine configured Hyperliquid symbols
    selected_symbols = get_hyperliquid_selected_symbols()
    if not selected_symbols:
        logger.info("No Hyperliquid watchlist configured, skipping Hyperliquid trading")
        return

    env_db = SessionLocal()
    try:
        from services.hyperliquid_environment import get_global_trading_mode
        prompt_environment = get_global_trading_mode(env_db)
    except Exception as err:
        logger.warning(f"Failed to get global trading mode for ticker snapshot: {err}")
        prompt_environment = "mainnet"
    finally:
        env_db.close()

    realtime_tickers = _get_realtime_ticker_snapshot(selected_symbols, environment=prompt_environment)
    prices = {
        symbol: float(ticker.get("price", 0) or 0)
        for symbol, ticker in realtime_tickers.items()
        if float(ticker.get("price", 0) or 0) > 0
    }
    if not prices:
        logger.info("Failed to fetch market prices, skipping Hyperliquid trading")
        return

    # Sampling data availability (informational)
    from services.sampling_pool import sampling_pool
    available_symbols = []
    for sym in selected_symbols:
        samples_data = sampling_pool.get_samples(sym)
        if samples_data:
            available_symbols.append(sym)

    if available_symbols:
        logger.info(f"Available sampling symbols for Hyperliquid: {', '.join(available_symbols)}")
    else:
        logger.info("No sampling data available for configured Hyperliquid symbols")

    symbol_metadata_map = get_hyperliquid_symbol_map()
    prompt_symbol_metadata = {}
    for sym in selected_symbols:
        entry = dict(symbol_metadata_map.get(sym, {}))
        entry.setdefault("name", sym)
        prompt_symbol_metadata[sym] = entry
    symbol_whitelist = set(selected_symbols)

    # Process each account with separate database connections
    for account in accounts:
        # Each account gets its own database connection
        db = SessionLocal()
        # PostgreSQL handles concurrent access natively
        try:
            # Validate account configuration completeness
            validation_errors = []

            # Check model configuration
            if not account.api_key or not account.model:
                validation_errors.append("AI model/API key not configured")

            # Check strategy configuration
            from database.models import AccountStrategyConfig
            strategy = db.query(AccountStrategyConfig).filter(
                AccountStrategyConfig.account_id == account.id,
                AccountStrategyConfig.enabled == "true"
            ).first()
            if not strategy:
                validation_errors.append("trading strategy not configured or disabled")

            # If there are validation errors, skip this account with clear warning
            if validation_errors:
                logger.info(
                    f"AI Trader '{account.name}' (ID: {account.id}) skipped - "
                    f"Configuration incomplete: {', '.join(validation_errors)}. "
                    f"Please complete configuration in AI Traders management page."
                )
                continue

            # Get global trading mode (environment) for Hyperliquid
            from services.hyperliquid_environment import get_global_trading_mode
            environment = get_global_trading_mode(db)
            logger.info(f"Processing Hyperliquid trading for account: {account.name} (environment: {environment})")

            # Get Hyperliquid client (will check wallet configuration)
            try:
                client = get_hyperliquid_client(db, account.id, override_environment=environment)
            except ValueError as wallet_err:
                logger.info(
                    f"AI Trader '{account.name}' (ID: {account.id}) skipped - "
                    f"Hyperliquid wallet not configured. {str(wallet_err)} "
                    f"Please configure wallet in AI Traders management page."
                )
                continue
            except Exception as client_err:
                logger.error(f"Failed to get Hyperliquid client for {account.name}: {client_err}")
                continue
            wallet_address = getattr(client, "wallet_address", None)
            decision_kwargs = {"wallet_address": wallet_address, "exchange": "hyperliquid"}

            # Get tracking fields for decision analysis (failures should not affect core business)
            try:
                from database.models import AccountPromptBinding
                binding = db.query(AccountPromptBinding).filter(
                    AccountPromptBinding.account_id == account.id,
                    AccountPromptBinding.is_deleted != True
                ).first()
                decision_kwargs["prompt_template_id"] = binding.prompt_template_id if binding else None
            except Exception as e:
                logger.warning(f"Failed to get prompt_template_id for {account.name}: {e}")
                decision_kwargs["prompt_template_id"] = None

            # Get signal_trigger_id from trigger_context (only present for signal-triggered decisions)
            decision_kwargs["signal_trigger_id"] = (
                trigger_context.get("signal_trigger_id") if trigger_context else None
            )

            # Get real account state from Hyperliquid
            try:
                account_state = client.get_account_state(db)
                available_balance = account_state['available_balance']
                total_equity = account_state['total_equity']
                margin_usage = account_state['margin_usage_percent']

                logger.info(
                    f"Hyperliquid account state for {account.name}: "
                    f"equity=${total_equity:.2f}, available=${available_balance:.2f}, "
                    f"margin_usage={margin_usage:.1f}%"
                )

            except Exception as state_err:
                logger.error(f"Failed to get account state for {account.name}: {state_err}")
                continue

            # Get open positions from Hyperliquid (must check before skipping due to equity)
            # include_timing=True to get position opened times for AI prompt context
            try:
                positions = client.get_positions(db, include_timing=True)
                logger.info(f"Account {account.name} has {len(positions)} open positions")
            except Exception as pos_err:
                logger.error(f"Failed to get positions for {account.name}: {pos_err}")
                positions = []

            # Check equity after getting positions - allow close operations even with zero equity
            if total_equity <= 0 and len(positions) == 0:
                logger.warning(
                    f"⚠️  Account {account.name} (ID: {account.id}) skipped - No balance to trade! "
                    f"Equity: ${total_equity:.2f}, Positions: 0. "
                    f"Please deposit funds to wallet {wallet_address} to enable trading."
                )
                continue

            if total_equity <= 0 and len(positions) > 0:
                logger.warning(
                    f"⚠️  Account {account.name} (ID: {account.id}) has ZERO equity but {len(positions)} open positions! "
                    f"Equity: ${total_equity:.2f}, Allowing AI to decide on close/risk management operations."
                )

            # Build portfolio data for AI (using Hyperliquid real data)
            portfolio = {
                'cash': available_balance,
                'frozen_cash': account_state.get('used_margin', 0),
                'positions': {},
                'total_assets': total_equity
            }

            for pos in positions:
                symbol = pos['coin']
                portfolio['positions'][symbol] = {
                    'quantity': pos['szi'],  # Signed size
                    'avg_cost': pos['entry_px'],
                    'current_value': pos['position_value'],
                    'unrealized_pnl': pos['unrealized_pnl'],
                    'leverage': pos['leverage']
                }

            # Build Hyperliquid state for prompt context
            hyperliquid_state = {
                'total_equity': total_equity,
                'available_balance': available_balance,
                'used_margin': account_state.get('used_margin', 0),
                'margin_usage_percent': margin_usage,
                'maintenance_margin': account_state.get('maintenance_margin', 0),
                'positions': positions
            }

            # Call AI for trading decision with trigger context
            decisions = call_ai_for_decision(
                db,
                account,
                portfolio,
                prices,
                symbols=selected_symbols,
                hyperliquid_state=hyperliquid_state,
                symbol_metadata=prompt_symbol_metadata,
                trigger_context=trigger_context,
                exchange="hyperliquid",
            )

            if not decisions:
                logger.warning(f"Failed to get AI decision for {account.name}, skipping")
                continue

            decision_priority = {"close": 0, "sell": 1, "buy": 2, "hold": 3}
            ordered_decisions = sorted(
                decisions,
                key=lambda d: decision_priority.get(str(d.get("operation", "")).lower(), 4),
            )

            for decision in ordered_decisions:
                _execute_hyperliquid_decision(
                    db=db,
                    account=account,
                    client=client,
                    decision=decision,
                    portfolio=portfolio,
                    positions=positions,
                    prices=prices,
                    available_balance=available_balance,
                    environment=environment,
                    wallet_address=wallet_address,
                    symbol_whitelist=symbol_whitelist,
                    decision_kwargs=decision_kwargs,
                    trigger_context=trigger_context,
                )

        except Exception as account_err:
            logger.error(f"Error processing Hyperliquid account {account.name}: {account_err}", exc_info=True)
            db.rollback()
        finally:
            db.close()


HYPERLIQUID_TRADE_JOB_ID = "hyperliquid_ai_trade"
