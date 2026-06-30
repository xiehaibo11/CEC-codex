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
from services.ai_decision_service import (
    call_ai_for_decision,
    save_ai_decision,
)
from services.hyperliquid_symbol_service import (
    get_selected_symbols as get_hyperliquid_selected_symbols,
    get_available_symbol_map as get_hyperliquid_symbol_map,
)

from .helpers import _enforce_price_bounds, _get_realtime_ticker_snapshot


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
        from database.models import HyperliquidPosition
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
            from services.hyperliquid_environment import get_global_trading_mode, get_leverage_settings
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
                if not isinstance(decision, dict):
                    logger.warning(f"Skipping malformed Hyperliquid decision for {account.name}: {decision}")
                    continue

                operation = decision.get("operation", "").lower()
                symbol = decision.get("symbol", "").upper()
                target_portion = float(decision.get("target_portion_of_balance", 0))
                leverage = int(decision.get("leverage", getattr(account, "default_leverage", 1)))
                max_price = decision.get("max_price")
                min_price = decision.get("min_price")
                reason = decision.get("reason", "No reason provided")

                logger.info(
                    f"AI decision for {account.name}: {operation} {symbol} "
                    f"(portion: {target_portion:.2%}, leverage: {leverage}x, max_price: {max_price}, min_price: {min_price}) - {reason}"
                )

                if operation not in ["buy", "sell", "hold", "close"]:
                    logger.warning(f"Invalid operation '{operation}' from AI for {account.name}")
                    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                    continue

                if operation == "hold":
                    # HOLD = do nothing. Ignore all other fields (leverage, TP/SL, etc.)
                    # AI may include extra fields due to compliance behavior, but we enforce
                    # the rule: TP/SL can only be set at entry, not modified during hold.
                    logger.info(f"AI decided to HOLD for {account.name} - no action taken")
                    save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
                    continue

                if symbol not in symbol_whitelist:
                    logger.warning(f"Symbol '{symbol}' not in Hyperliquid watchlist for {account.name}")
                    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                    continue

                # Get leverage settings from HyperliquidWallet (or Account fallback)
                leverage_settings = get_leverage_settings(db, account.id, environment)
                max_leverage = leverage_settings["max_leverage"]
                default_leverage = leverage_settings["default_leverage"]

                if leverage < 1 or leverage > max_leverage:
                    logger.warning(
                        f"Invalid leverage {leverage}x from AI (max: {max_leverage}x), "
                        f"using default {default_leverage}x"
                    )
                    leverage = default_leverage

                if target_portion <= 0 or target_portion > 1:
                    logger.warning(f"Invalid target_portion {target_portion} from AI for {account.name}")
                    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                    continue

                price = prices.get(symbol)
                if not price or price <= 0:
                    logger.warning(f"Invalid price for {symbol} for {account.name}")
                    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                    continue

                order_result = None

                if operation == "buy":
                    # Calculate margin first, then position value with leverage
                    margin = available_balance * target_portion
                    order_value = margin * leverage
                    quantity = round(order_value / price, 6)

                    logger.info(
                        f"Position sizing for {symbol}: "
                        f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                        f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
                    )

                    # Extract TP/SL and time_in_force from AI decision
                    take_profit_price = decision.get("take_profit_price")
                    stop_loss_price = decision.get("stop_loss_price")
                    time_in_force = decision.get("time_in_force", "Ioc")  # Default to Ioc (market-like)
                    tp_execution = decision.get("tp_execution", "limit")  # Default to limit (attempts maker)
                    sl_execution = decision.get("sl_execution", "limit")  # Default to limit

                    # Price validation for BUY operation
                    if max_price is not None:
                        price_to_use = max_price
                        price_to_use, price_deviation_percent, _ = _enforce_price_bounds(
                            symbol=symbol,
                            account_name=account.name,
                            operation="buy",
                            current_price=price,
                            requested_price=price_to_use,
                        )
                        logger.info(
                            f"Using AI-provided max_price for BUY {symbol}: "
                            f"market=${price:.2f}, order=${price_to_use:.2f}, "
                            f"deviation={price_deviation_percent:.2f}%"
                        )
                    else:
                        # AI did not provide max_price - use market price (already within 1%)
                        price_to_use = price
                        logger.warning(
                            f"⚠️  AI COMPLIANCE ISSUE - BUY {symbol}: "
                            f"AI did not provide max_price in decision. "
                            f"Using market price: ${price_to_use:.2f}. "
                            f"Prompt should require max_price for all BUY operations."
                        )

                    logger.info(
                        f"[HYPERLIQUID {environment.upper()}] Placing BUY order: "
                        f"{symbol} size={quantity} leverage={leverage}x TIF={time_in_force} "
                        f"TP={take_profit_price} SL={stop_loss_price}"
                    )

                    # Use native API for all orders
                    order_result = client.place_order_with_tpsl(
                        db=db,
                        symbol=symbol,
                        is_buy=True,
                        size=quantity,
                        price=price_to_use,
                        leverage=leverage,
                        time_in_force=time_in_force,
                        reduce_only=False,
                        take_profit_price=take_profit_price,
                        stop_loss_price=stop_loss_price,
                        tp_execution=tp_execution,
                        sl_execution=sl_execution
                    )

                    # Fallback: If IOC failed due to no liquidity, retry with GTC
                    if order_result and order_result.get('status') == 'error':
                        error_msg = order_result.get('error', '')
                        if 'could not immediately match' in error_msg.lower() or 'no resting orders' in error_msg.lower():
                            logger.warning(
                                f"⚠️  IOC order failed for BUY {symbol} (no liquidity), retrying with GTC limit order..."
                            )
                            order_result = client.place_order_with_tpsl(
                                db=db,
                                symbol=symbol,
                                is_buy=True,
                                size=quantity,
                                price=price_to_use,
                                leverage=leverage,
                                time_in_force="Gtc",  # Changed from Ioc to Gtc
                                reduce_only=False,
                                take_profit_price=take_profit_price,
                                stop_loss_price=stop_loss_price,
                                tp_execution=tp_execution,
                                sl_execution=sl_execution
                            )
                            if order_result and order_result.get('status') in ['filled', 'resting']:
                                logger.info(f"✅ GTC fallback order succeeded for BUY {symbol}")

                elif operation == "sell":
                    # Calculate margin first, then position value with leverage
                    margin = available_balance * target_portion
                    order_value = margin * leverage
                    quantity = round(order_value / price, 6)

                    logger.info(
                        f"Position sizing for {symbol}: "
                        f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                        f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
                    )

                    # Extract TP/SL and time_in_force from AI decision
                    take_profit_price = decision.get("take_profit_price")
                    stop_loss_price = decision.get("stop_loss_price")
                    time_in_force = decision.get("time_in_force", "Ioc")  # Default to Ioc (market-like)
                    tp_execution = decision.get("tp_execution", "limit")  # Default to limit (attempts maker)
                    sl_execution = decision.get("sl_execution", "limit")  # Default to limit

                    # Price validation for SELL operation
                    if min_price is not None:
                        price_to_use = min_price
                        price_to_use, price_deviation_percent, _ = _enforce_price_bounds(
                            symbol=symbol,
                            account_name=account.name,
                            operation="sell",
                            current_price=price,
                            requested_price=price_to_use,
                        )
                        logger.info(
                            f"Using AI-provided min_price for SELL {symbol}: "
                            f"market=${price:.2f}, order=${price_to_use:.2f}, "
                            f"deviation={price_deviation_percent:.2f}%"
                        )
                    else:
                        # AI did not provide min_price - use market price
                        price_to_use = price
                        logger.warning(
                            f"⚠️  AI COMPLIANCE ISSUE - SELL {symbol}: "
                            f"AI did not provide min_price in decision. "
                            f"Using market price: ${price_to_use:.2f}. "
                            f"Prompt should require min_price for all SELL operations."
                        )

                    logger.info(
                        f"[HYPERLIQUID {environment.upper()}] Placing SELL order: "
                        f"{symbol} size={quantity} leverage={leverage}x TIF={time_in_force} "
                        f"TP={take_profit_price} SL={stop_loss_price}"
                    )

                    # Use native API for all orders
                    order_result = client.place_order_with_tpsl(
                        db=db,
                        symbol=symbol,
                        is_buy=False,
                        size=quantity,
                        price=price_to_use,
                        leverage=leverage,
                        time_in_force=time_in_force,
                        reduce_only=False,
                        take_profit_price=take_profit_price,
                        stop_loss_price=stop_loss_price,
                        tp_execution=tp_execution,
                        sl_execution=sl_execution
                    )

                    # Fallback: If IOC failed due to no liquidity, retry with GTC
                    if order_result and order_result.get('status') == 'error':
                        error_msg = order_result.get('error', '')
                        if 'could not immediately match' in error_msg.lower() or 'no resting orders' in error_msg.lower():
                            logger.warning(
                                f"⚠️  IOC order failed for SELL {symbol} (no liquidity), retrying with GTC limit order..."
                            )
                            order_result = client.place_order_with_tpsl(
                                db=db,
                                symbol=symbol,
                                is_buy=False,
                                size=quantity,
                                price=price_to_use,
                                leverage=leverage,
                                time_in_force="Gtc",  # Changed from Ioc to Gtc
                                reduce_only=False,
                                take_profit_price=take_profit_price,
                                stop_loss_price=stop_loss_price,
                                tp_execution=tp_execution,
                                sl_execution=sl_execution
                            )
                            if order_result and order_result.get('status') in ['filled', 'resting']:
                                logger.info(f"✅ GTC fallback order succeeded for SELL {symbol}")

                elif operation == "close":
                    # For full close (target_portion = 1.0), also cancel all pending orders for this symbol
                    # This ensures "complete exit" from a trading plan includes both positions and orders
                    should_cancel_orders = target_portion >= 1.0

                    position_to_close = None
                    for pos in positions:
                        if pos.get('coin') == symbol:
                            position_to_close = pos
                            break

                    if position_to_close:
                        position_size = abs(position_to_close.get('szi', 0))
                        is_long = (position_to_close.get('szi', 0) or 0) > 0
                    else:
                        # Fall back to portfolio snapshot from prompt context
                        logger.warning(
                            f"⚠️  Position {symbol} not found in real-time positions list. "
                            f"Using portfolio snapshot data from AI prompt context. "
                            f"This may indicate position was closed by another operation or data sync issue."
                        )
                        portfolio_positions = portfolio.get('positions') or {}
                        fallback_position = portfolio_positions.get(symbol)
                        if not fallback_position:
                            # No position found - check if there are pending orders to cancel
                            if should_cancel_orders:
                                try:
                                    pending_orders = client.get_open_orders(db, symbol=symbol)
                                    if pending_orders:
                                        logger.info(
                                            f"[CLOSE {symbol}] No position found, but {len(pending_orders)} pending orders exist. "
                                            f"Cancelling all orders as target_portion=1.0 (full exit)."
                                        )
                                        cancelled_count = 0
                                        for order in pending_orders:
                                            order_id = order.get('order_id')
                                            order_type = order.get('order_type', 'Unknown')
                                            if order_id:
                                                try:
                                                    if client.cancel_order(db, order_id, symbol):
                                                        cancelled_count += 1
                                                        logger.info(f"[CLOSE {symbol}] Cancelled {order_type} order #{order_id}")
                                                except Exception as cancel_err:
                                                    logger.warning(f"[CLOSE {symbol}] Failed to cancel order #{order_id}: {cancel_err}")

                                        if cancelled_count > 0:
                                            logger.info(f"[CLOSE {symbol}] Successfully cancelled {cancelled_count}/{len(pending_orders)} pending orders")
                                            save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
                                            continue
                                except Exception as orders_err:
                                    logger.warning(f"[CLOSE {symbol}] Failed to fetch pending orders: {orders_err}")

                            logger.warning(f"Unable to locate Hyperliquid position data for {symbol}; skipping close.")
                            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                            continue
                        quantity = float(fallback_position.get('quantity') or 0)
                        position_size = abs(quantity)
                        is_long = quantity > 0

                    # Validate position exists and size is non-zero
                    if position_size <= 0:
                        logger.warning(f"No position to close for {symbol} (size={position_size}), skipping close operation")
                        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                        continue

                    close_size = position_size * target_portion

                    logger.info(
                        f"[HYPERLIQUID {environment.upper()}] Closing position: "
                        f"{symbol} size={close_size} (closing {'long' if is_long else 'short'})"
                    )

                    current_price = prices.get(symbol, 0)

                    # Price validation for Hyperliquid 1% oracle limit
                    max_price_close = decision.get("max_price")

                    if is_long:
                        ai_close_price = min_price
                        price_field_used = "min_price"
                    else:
                        ai_close_price = max_price_close if max_price_close is not None else min_price
                        price_field_used = "max_price" if max_price_close is not None else "min_price"

                        if max_price_close is None and min_price is not None:
                            logger.warning(
                                f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                                f"Short position provided min_price instead of max_price. "
                                f"Treating min_price=${min_price:.2f} as max_price for compatibility."
                            )

                    if ai_close_price:
                        close_price = ai_close_price
                        close_price, price_deviation_percent, _ = _enforce_price_bounds(
                            symbol=symbol,
                            account_name=account.name,
                            operation="close",
                            current_price=current_price,
                            requested_price=close_price,
                        )

                        # Check if close price is on the wrong side of market OR too close to oracle boundaries
                        if not is_long and close_price < current_price:
                            # Close Short: buy price too low, raise to slightly above market
                            logger.warning(
                                f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                                f"Short close limit ${close_price:.2f} sits below market ${current_price:.2f}. "
                                f"Adjusting to ensure IOC buy can match resting asks."
                            )
                            close_price, price_deviation_percent, _ = _enforce_price_bounds(
                                symbol=symbol,
                                account_name=account.name,
                                operation="close",
                                current_price=current_price,
                                requested_price=current_price * 1.005,
                            )
                        elif not is_long and close_price > current_price * 1.005:
                            # Close Short: buy price too close to +1% oracle limit
                            logger.warning(
                                f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                                f"Short close limit ${close_price:.2f} too close to oracle upper boundary. "
                                f"Market ${current_price:.2f}. Adjusting to 1.005x for safer execution."
                            )
                            close_price, price_deviation_percent, _ = _enforce_price_bounds(
                                symbol=symbol,
                                account_name=account.name,
                                operation="close",
                                current_price=current_price,
                                requested_price=current_price * 1.005,
                            )
                        elif is_long and close_price > current_price:
                            # Close Long: sell price too high, lower to slightly below market
                            logger.warning(
                                f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                                f"Long close limit ${close_price:.2f} sits above market ${current_price:.2f}. "
                                f"Adjusting to ensure IOC sell can match resting bids."
                            )
                            close_price, price_deviation_percent, _ = _enforce_price_bounds(
                                symbol=symbol,
                                account_name=account.name,
                                operation="close",
                                current_price=current_price,
                                requested_price=current_price * 0.995,
                            )
                        elif is_long and close_price < current_price * 0.995:
                            # Close Long: sell price too close to -1% oracle limit
                            logger.warning(
                                f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                                f"Long close limit ${close_price:.2f} too close to oracle lower boundary. "
                                f"Market ${current_price:.2f}. Adjusting to 0.995x for safer execution."
                            )
                            close_price, price_deviation_percent, _ = _enforce_price_bounds(
                                symbol=symbol,
                                account_name=account.name,
                                operation="close",
                                current_price=current_price,
                                requested_price=current_price * 0.995,
                            )

                        logger.info(
                            f"Using AI-provided {price_field_used} for CLOSE {symbol}: "
                            f"market=${current_price:.2f}, order=${close_price:.2f}, "
                            f"deviation={price_deviation_percent:.2f}%"
                        )
                    else:
                        # AI did not provide relevant close price - use safe default
                        fallback_multiplier = 0.995 if is_long else 1.005
                        close_price = current_price * fallback_multiplier
                        close_price, _, _ = _enforce_price_bounds(
                            symbol=symbol,
                            account_name=account.name,
                            operation="close",
                            current_price=current_price,
                            requested_price=close_price,
                        )
                        logger.warning(
                            f"⚠️  AI COMPLIANCE ISSUE - CLOSE {symbol}: "
                            f"AI did not provide {'min_price' if is_long else 'max_price'} in decision. "
                            f"Using fallback price: market=${current_price:.2f}, order=${close_price:.2f}. "
                            f"Prompt should require {'min_price for closing longs' if is_long else 'max_price for closing shorts'} in all CLOSE operations."
                        )

                    # Retry logic with progressive price adjustment for IoC close orders
                    max_retries = 4
                    retry_count = 0
                    order_result = None
                    fallback_gtc_attempted = False

                    # Progressive price multipliers for each retry (conservative start + dense sampling)
                    # For long close (sell): move down to increase match probability
                    # For short close (buy): move up to increase match probability
                    # Strategy: Start conservatively, progressively sample through safe zone to boundary
                    if is_long:
                        price_multipliers = [0.996, 0.994, 0.992, 0.99]  # Selling: 0.6% coverage, 4 sampling points
                    else:
                        price_multipliers = [1.004, 1.006, 1.008, 1.01]  # Buying: 0.6% coverage, 4 sampling points

                    while retry_count < max_retries and order_result is None:
                        # Use AI price for first attempt, then use progressive multipliers
                        if retry_count == 0:
                            attempt_price = close_price
                        else:
                            # Refresh market price for retry attempts
                            current_price_retry = prices.get(symbol, current_price)
                            attempt_price = current_price_retry * price_multipliers[retry_count]
                            attempt_price, _, _ = _enforce_price_bounds(
                                symbol=symbol,
                                account_name=account.name,
                                operation="close",
                                current_price=current_price_retry,
                                requested_price=attempt_price,
                            )
                            logger.info(
                                f"[RETRY {retry_count}/{max_retries}] CLOSE {symbol}: "
                                f"Adjusting price to ${attempt_price:.2f} "
                                f"(market=${current_price_retry:.2f}, multiplier={price_multipliers[retry_count]})"
                            )

                        # Attempt order placement
                        attempt_result = client.place_order_with_tpsl(
                            db=db,
                            symbol=symbol,
                            is_buy=(not is_long),
                            size=close_size,
                            price=attempt_price,
                            leverage=1,
                            time_in_force="Ioc",  # Always use Ioc for closing positions
                            reduce_only=True,
                            take_profit_price=None,
                            stop_loss_price=None
                        )

                        # Check if order succeeded
                        if attempt_result and attempt_result.get('status') == 'filled':
                            order_result = attempt_result
                            if retry_count > 0:
                                logger.info(
                                    f"✅ CLOSE {symbol} succeeded on retry {retry_count} "
                                    f"with price ${attempt_price:.2f}"
                                )
                            break

                        # Check if we should retry
                        error_msg = attempt_result.get('error', '') if attempt_result else ''
                        should_retry = (
                            'could not immediately match' in error_msg.lower() or
                            'no resting orders' in error_msg.lower()
                        )

                        if should_retry and retry_count < max_retries - 1:
                            retry_count += 1
                            logger.warning(
                                f"⚠️  CLOSE {symbol} failed (attempt {retry_count}/{max_retries}): {error_msg}. "
                                f"Will retry with more aggressive price..."
                            )
                        else:
                            # Either non-retryable error or max retries reached
                            order_result = attempt_result
                            if retry_count > 0:
                                logger.error(
                                    f"❌ CLOSE {symbol} failed after {retry_count + 1} attempts. "
                                    f"Last error: {error_msg}"
                                )
                            break

                    # If IOC retries failed, place a final reduce-only GTC order at the safe boundary
                    if (not order_result or order_result.get('status') != 'filled') and not fallback_gtc_attempted:
                        fallback_gtc_attempted = True
                        boundary_multiplier = 0.99 if is_long else 1.01
                        latest_price = prices.get(symbol, current_price)
                        if not latest_price or latest_price <= 0:
                            latest_price = current_price or close_price
                        fallback_price = latest_price * boundary_multiplier
                        fallback_price, _, _ = _enforce_price_bounds(
                            symbol=symbol,
                            account_name=account.name,
                            operation="close",
                            current_price=latest_price,
                            requested_price=fallback_price,
                        )
                        logger.warning(
                            f"⚠️  CLOSE {symbol} entering fallback mode: placing reduce-only GTC at ${fallback_price:.2f} "
                            f"(latest=${latest_price:.2f}). Order will rest until filled."
                        )
                        order_result = client.place_order_with_tpsl(
                            db=db,
                            symbol=symbol,
                            is_buy=(not is_long),
                            size=close_size,
                            price=fallback_price,
                            leverage=1,
                            time_in_force="Gtc",
                            reduce_only=True,
                            take_profit_price=None,
                            stop_loss_price=None
                        )

                else:
                    continue

                if order_result:
                    print(f"[DEBUG] {operation.upper()} order_result: {order_result}")
                    order_status = order_result.get('status')
                    order_id = order_result.get('order_id')

                    # Update decision_kwargs with order IDs for tracking (only when order succeeded)
                    if order_status in ('filled', 'resting'):
                        decision_kwargs["hyperliquid_order_id"] = order_result.get('order_id')
                        decision_kwargs["tp_order_id"] = order_result.get('tp_order_id')
                        decision_kwargs["sl_order_id"] = order_result.get('sl_order_id')

                    if order_status == 'filled':
                        logger.info(
                            f"[HYPERLIQUID] Order executed successfully for {account.name}: "
                            f"{operation.upper()} {symbol} order_id={order_id}"
                        )
                        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)

                        # For full close (target_portion = 1.0), cancel any remaining pending orders
                        if operation == "close" and should_cancel_orders:
                            try:
                                remaining_orders = client.get_open_orders(db, symbol=symbol)
                                if remaining_orders:
                                    logger.info(
                                        f"[CLOSE {symbol}] Position closed. Cancelling {len(remaining_orders)} remaining orders (full exit)."
                                    )
                                    for order in remaining_orders:
                                        oid = order.get('order_id')
                                        otype = order.get('order_type', 'Unknown')
                                        if oid:
                                            try:
                                                if client.cancel_order(db, oid, symbol):
                                                    logger.info(f"[CLOSE {symbol}] Cancelled {otype} order #{oid}")
                                            except Exception as cancel_err:
                                                logger.warning(f"[CLOSE {symbol}] Failed to cancel order #{oid}: {cancel_err}")
                            except Exception as orders_err:
                                logger.warning(f"[CLOSE {symbol}] Failed to fetch remaining orders: {orders_err}")

                        try:
                            from database.snapshot_connection import SnapshotSessionLocal
                            from database.snapshot_models import HyperliquidTrade
                            from decimal import Decimal

                            snapshot_db = SnapshotSessionLocal()
                            try:
                                trade_record = HyperliquidTrade(
                                    account_id=account.id,
                                    environment=environment,
                                    wallet_address=wallet_address,
                                    symbol=symbol,
                                    side=operation,
                                    quantity=Decimal(str(order_result.get('filled_amount', 0))),
                                    price=Decimal(str(order_result.get('average_price', 0))),
                                    leverage=leverage,
                                    order_id=order_id,
                                    order_status=order_status,
                                    trade_value=Decimal(str(order_result.get('filled_amount', 0))) * Decimal(str(order_result.get('average_price', 0))),
                                    fee=Decimal(str(order_result.get('fee', 0)))
                                )
                                snapshot_db.add(trade_record)
                                snapshot_db.commit()
                                logger.info(f"[HYPERLIQUID] Trade record saved for {account.name}")
                            finally:
                                snapshot_db.close()
                        except Exception as trade_err:
                            logger.warning(f"Failed to save Hyperliquid trade record: {trade_err}")

                    elif order_status == 'resting':
                        logger.info(
                            f"[HYPERLIQUID] Order placed (resting) for {account.name}: "
                            f"{operation.upper()} {symbol} order_id={order_id}"
                        )
                        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)

                    else:
                        error_msg = order_result.get('error', 'Unknown error')
                        logger.error(
                            f"[HYPERLIQUID] Order failed for {account.name}: "
                            f"{operation.upper()} {symbol} - {error_msg}"
                        )
                        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                else:
                    logger.error(f"No order result received for {account.name}")
                    save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)

        except Exception as account_err:
            logger.error(f"Error processing Hyperliquid account {account.name}: {account_err}", exc_info=True)
            db.rollback()
        finally:
            db.close()


HYPERLIQUID_TRADE_JOB_ID = "hyperliquid_ai_trade"
