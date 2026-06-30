"""
Trading Commands - Binance AI-driven order placement (account orchestration).

Iterates active accounts, loads wallet/credentials and account state, requests
AI decisions, and dispatches each decision to ``_execute_binance_decision``.
Logic is preserved exactly as the original ``trading_commands`` implementation.
"""
import logging
from typing import Dict, Optional, Iterable, Any, List

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Account
from services.market_data import get_last_price
from services.ai_decision_service import call_ai_for_decision
from services.binance_symbol_service import (
    get_selected_symbols as get_binance_selected_symbols,
)

from .binance_execution import _execute_binance_decision


logger = logging.getLogger(__name__)


def place_ai_driven_binance_order(
    account_ids: Optional[Iterable[int]] = None,
    account_id: Optional[int] = None,
    bypass_auto_trading: bool = False,
    trigger_context: Optional[Dict[str, Any]] = None,
    samples: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Place Binance perpetual contract order based on AI decision.

    This function handles real trading on Binance exchange, supporting:
    - Perpetual contract trading (long/short)
    - Leverage configuration
    - Position management

    Args:
        account_ids: Optional iterable of account IDs to process
        account_id: Optional single account ID to process
        bypass_auto_trading: Skip auto_trading_enabled check
        trigger_context: Optional context about what triggered this decision
    """
    from services.binance_trading_client import BinanceTradingClient
    from database.models import BinanceWallet

    # Get accounts list
    accounts = []
    db = SessionLocal()
    try:
        if account_id is not None:
            account = db.query(Account).filter(Account.id == account_id, Account.is_deleted != True).first()
            if not account or account.is_active != "true":
                logger.debug(f"Account {account_id} not found or inactive")
                return

            if not bypass_auto_trading and getattr(account, "auto_trading_enabled", "false") != "true":
                logger.debug(f"Account {account_id} auto trading disabled - skipping Binance AI order")
                return

            accounts = [account]
        else:
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
    finally:
        db.close()

    # Get Binance symbols from Binance watchlist
    selected_symbols = get_binance_selected_symbols()
    if not selected_symbols:
        logger.warning("[Binance] No Binance watchlist configured, skipping Binance trading")
        return
    logger.info(f"[Binance] AI trading using symbols: {selected_symbols}")

    # Get market prices
    prices = {}
    for sym in selected_symbols:
        try:
            price = get_last_price(sym, market="binance")
            if price:
                prices[sym] = price
        except Exception as e:
            logger.warning(f"Failed to get price for {sym}: {e}")

    if not prices:
        logger.warning("Failed to fetch Binance market prices, skipping trading")
        return

    # Process each account
    for account in accounts:
        db = SessionLocal()
        try:
            # Get global trading mode (same as Hyperliquid)
            from services.hyperliquid_environment import get_global_trading_mode
            environment = get_global_trading_mode(db)
            if not environment:
                logger.info(f"AI Trader '{account.name}' skipped - No trading environment configured")
                continue

            # Check Binance wallet configuration for the current environment
            wallet = db.query(BinanceWallet).filter(
                BinanceWallet.account_id == account.id,
                BinanceWallet.environment == environment,
                BinanceWallet.is_active == "true"
            ).first()

            if not wallet or not wallet.api_key_encrypted or not wallet.secret_key_encrypted:
                logger.info(
                    f"AI Trader '{account.name}' (ID: {account.id}) skipped - "
                    f"Binance wallet not configured."
                )
                continue

            # Decrypt API credentials
            from utils.encryption import decrypt_private_key
            api_key = decrypt_private_key(wallet.api_key_encrypted)
            secret_key = decrypt_private_key(wallet.secret_key_encrypted)

            # Initialize Binance trading client
            client = BinanceTradingClient(
                api_key=api_key,
                secret_key=secret_key,
                environment=wallet.environment or "testnet"
            )

            # Build decision_kwargs for tracking (same as Hyperliquid)
            # Note: BinanceWallet has no wallet_address field (unlike HyperliquidWallet),
            # so we use wallet.id as identifier. The key must be "wallet_address" to match
            # save_ai_decision() function signature.
            decision_kwargs = {"wallet_address": str(wallet.id), "exchange": "binance"}

            # Get tracking fields for decision analysis
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

            # Get account state
            try:
                account_state = client.get_account_state(db)
                available_balance = account_state['available_balance']
                total_equity = account_state['total_equity']
                margin_usage = account_state['margin_usage_percent']

                logger.info(
                    f"Binance account state for {account.name}: "
                    f"equity=${total_equity:.2f}, available=${available_balance:.2f}, "
                    f"margin_usage={margin_usage:.1f}%"
                )
            except Exception as e:
                logger.error(f"Failed to get Binance account state for {account.name}: {e}")
                continue

            # Get positions
            try:
                positions = client.get_positions(include_timing=True)
                logger.info(f"Account {account.name} has {len(positions)} open positions")
            except Exception as e:
                logger.error(f"Failed to get Binance positions for {account.name}: {e}")
                positions = []

            # Check equity
            if total_equity <= 0 and len(positions) == 0:
                logger.warning(
                    f"Account {account.name} (ID: {account.id}) skipped - No balance to trade!"
                )
                continue

            # Build portfolio for AI
            portfolio = {
                'cash': available_balance,
                'frozen_cash': account_state.get('used_margin', 0),
                'positions': {},
                'total_assets': total_equity
            }

            for pos in positions:
                symbol = pos['coin']
                portfolio['positions'][symbol] = {
                    'quantity': pos['szi'],
                    'avg_cost': pos['entry_px'],
                    'current_value': pos['position_value'],
                    'unrealized_pnl': pos['unrealized_pnl'],
                    'leverage': pos['leverage']
                }

            # Build Binance state for prompt
            binance_state = {
                'total_equity': total_equity,
                'available_balance': available_balance,
                'used_margin': account_state.get('used_margin', 0),
                'margin_usage_percent': margin_usage,
                'positions': positions
            }

            # Forced decisions (from signal-driven daemons or manual triggers) bypass the
            # AI model so the same code path serves both AI-driven and rule-driven trading.
            if samples:
                decisions = samples
                logger.info(f"[BINANCE] Using {len(samples)} forced decision(s) for {account.name}")
            else:
                decisions = call_ai_for_decision(
                    db,
                    account,
                    portfolio,
                    prices,
                    symbols=selected_symbols,
                    hyperliquid_state=binance_state,
                    trigger_context=trigger_context,
                    exchange="binance",
                )

            if not decisions:
                logger.info(f"No AI decisions for Binance account {account.name}")
                continue

            # Execute decisions
            for decision in decisions:
                _execute_binance_decision(
                    db, account, client, decision, portfolio, positions, prices,
                    available_balance=available_balance,
                    max_leverage=wallet.max_leverage or 20,
                    default_leverage=wallet.default_leverage or 5,
                    decision_kwargs=decision_kwargs,
                    wallet=wallet
                )

        except Exception as e:
            logger.error(f"Error processing Binance account {account.name}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


def _execute_binance_decision(
    db: Session,
    account: Account,
    client,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    available_balance: float = 0.0,
    max_leverage: int = 20,
    default_leverage: int = 5,
    decision_kwargs: Optional[Dict[str, Any]] = None,
    wallet=None,
) -> None:
    """
    Execute a single AI decision on Binance.

    Uses the same logic as Hyperliquid:
    - Validates operation type
    - Calculates quantity from target_portion_of_balance
    - Validates leverage range
    - Places order with TP/SL via place_order_with_tpsl()
    - Records order IDs for attribution
    """
    # Default decision_kwargs if not provided
    if decision_kwargs is None:
        decision_kwargs = {}

    operation = decision.get("operation", "").lower()
    symbol = decision.get("symbol", "").upper() if decision.get("symbol") else ""
    target_portion = float(decision.get("target_portion_of_balance", 0))
    leverage = int(decision.get("leverage", default_leverage))
    reason = decision.get("reason", "No reason provided")

    # Extract TP/SL from AI decision
    take_profit_price = decision.get("take_profit_price")
    stop_loss_price = decision.get("stop_loss_price")

    logger.info(
        f"[BINANCE] AI decision for {account.name}: {operation} {symbol} "
        f"(portion: {target_portion:.2%}, leverage: {leverage}x) - {reason}"
    )

    # 1. Validate operation type
    if operation not in ["buy", "sell", "hold", "close"]:
        logger.warning(f"[BINANCE] Invalid operation '{operation}' from AI for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    # 2. Handle HOLD operation (no quota consumption, no execution needed)
    if operation == "hold":
        logger.info(f"[BINANCE] AI decided to HOLD for {account.name} - no action taken")
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
        return

    # 3. Check daily quota for mainnet non-rebate accounts (only for buy/sell/close)
    if wallet and wallet.environment == "mainnet" and wallet.rebate_working is False:
        quota_exceeded, quota_info = _check_binance_daily_quota(db, account.id)
        if quota_exceeded:
            logger.warning(
                f"[BINANCE] AI Trader '{account.name}' quota exceeded - "
                f"Decision recorded but NOT executed ({quota_info['used']}/{quota_info['limit']})"
            )
            # Save decision with executed=False and quota exceeded reason
            decision["_quota_exceeded"] = True
            decision["_quota_info"] = quota_info
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return

    # 4. Validate symbol
    if not symbol:
        logger.warning(f"[BINANCE] No symbol provided in decision for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    # 4. Validate leverage range
    if leverage < 1 or leverage > max_leverage:
        logger.warning(
            f"[BINANCE] Invalid leverage {leverage}x from AI (max: {max_leverage}x), "
            f"using default {default_leverage}x"
        )
        leverage = default_leverage

    # 5. Get price
    price = prices.get(symbol, 0)
    if not price or price <= 0:
        logger.warning(f"[BINANCE] Invalid price for {symbol} for {account.name}")
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return

    order_result = None

    try:
        if operation == "buy":
            # 6. Validate target_portion
            if target_portion <= 0 or target_portion > 1:
                logger.warning(f"[BINANCE] Invalid target_portion {target_portion} from AI for {account.name}")
                save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                return

            # 7. Calculate quantity: margin * leverage / price
            margin = available_balance * target_portion
            order_value = margin * leverage
            quantity = round(order_value / price, 6)

            logger.info(
                f"[BINANCE] Position sizing for {symbol}: "
                f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
            )

            # 8. Place order with TP/SL
            order_result = client.place_order_with_tpsl(
                db=db,
                symbol=symbol,
                is_buy=True,
                size=quantity,
                price=price,
                leverage=leverage,
                order_type="MARKET",
                reduce_only=False,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price
            )

        elif operation == "sell":
            # Validate target_portion
            if target_portion <= 0 or target_portion > 1:
                logger.warning(f"[BINANCE] Invalid target_portion {target_portion} from AI for {account.name}")
                save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
                return

            # Calculate quantity
            margin = available_balance * target_portion
            order_value = margin * leverage
            quantity = round(order_value / price, 6)

            logger.info(
                f"[BINANCE] Position sizing for {symbol}: "
                f"margin=${margin:.2f} ({target_portion:.1%} of ${available_balance:.2f}), "
                f"leverage={leverage}x, position_value=${order_value:.2f}, quantity={quantity}"
            )

            # Place order with TP/SL
            order_result = client.place_order_with_tpsl(
                db=db,
                symbol=symbol,
                is_buy=False,
                size=quantity,
                price=price,
                leverage=leverage,
                order_type="MARKET",
                reduce_only=False,
                take_profit_price=take_profit_price,
                stop_loss_price=stop_loss_price
            )

        elif operation == "close":
            # Close position
            result = client.close_position(symbol, cancel_tpsl=True)
            if result:
                logger.info(f"[BINANCE] Position closed: {symbol}")
                save_ai_decision(
                    db, account, decision, portfolio, executed=True,
                    hyperliquid_order_id=str(result.get("order_id")) if result.get("order_id") else None,
                    **decision_kwargs
                )
                # Save HyperliquidTrade record (consistent with Hyperliquid)
                try:
                    from database.snapshot_connection import SnapshotSessionLocal
                    from database.snapshot_models import HyperliquidTrade
                    from decimal import Decimal

                    snapshot_db = SnapshotSessionLocal()
                    try:
                        # Use Binance official fields, fallback to market price if 0
                        filled_qty = float(result.get('filled_qty', 0))
                        avg_price_val = float(result.get('avg_price', 0))
                        # For close, use filled_qty or position size from result
                        trade_qty = Decimal(str(filled_qty)) if filled_qty > 0 else Decimal('0')
                        trade_price = Decimal(str(avg_price_val)) if avg_price_val > 0 else Decimal(str(price))

                        trade_record = HyperliquidTrade(
                            account_id=account.id,
                            environment=wallet.environment if wallet else "mainnet",
                            wallet_address=f"binance_{account.id}",
                            symbol=symbol,
                            side="close",
                            quantity=trade_qty,
                            price=trade_price,
                            leverage=1,
                            order_id=str(result.get('order_id', '')),
                            order_status=result.get('status', 'filled'),
                            trade_value=trade_qty * trade_price,
                            fee=Decimal('0')
                        )
                        snapshot_db.add(trade_record)
                        snapshot_db.commit()
                        logger.info(f"[BINANCE] Close trade record saved for {account.name}")
                    finally:
                        snapshot_db.close()
                except Exception as trade_err:
                    logger.warning(f"Failed to save Binance close trade record: {trade_err}")
            else:
                logger.info(f"[BINANCE] No position to close for {symbol}")
                save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
            return

        # 9. Save decision with order IDs for attribution
        if order_result:
            status = order_result.get("status", "error")
            executed = status in ["filled", "resting"]

            save_ai_decision(
                db, account, decision, portfolio,
                executed=executed,
                hyperliquid_order_id=str(order_result.get("order_id")) if order_result.get("order_id") else None,
                tp_order_id=str(order_result.get("tp_order_id")) if order_result.get("tp_order_id") else None,
                sl_order_id=str(order_result.get("sl_order_id")) if order_result.get("sl_order_id") else None,
                **decision_kwargs
            )

            if executed:
                logger.info(
                    f"[BINANCE] {operation.upper()} order executed: {symbol} "
                    f"order_id={order_result.get('order_id')} "
                    f"tp_id={order_result.get('tp_order_id')} sl_id={order_result.get('sl_order_id')}"
                )
                # Save HyperliquidTrade record (consistent with Hyperliquid)
                try:
                    from database.snapshot_connection import SnapshotSessionLocal
                    from database.snapshot_models import HyperliquidTrade
                    from decimal import Decimal

                    snapshot_db = SnapshotSessionLocal()
                    try:
                        # Use Binance official fields, fallback to decision values if 0
                        filled_qty = float(order_result.get('filled_qty', 0))
                        avg_price = float(order_result.get('avg_price', 0))
                        # If Binance returns 0 (MARKET order not yet filled), use decision values
                        trade_qty = Decimal(str(filled_qty)) if filled_qty > 0 else Decimal(str(quantity))
                        trade_price = Decimal(str(avg_price)) if avg_price > 0 else Decimal(str(price))

                        trade_record = HyperliquidTrade(
                            account_id=account.id,
                            environment=wallet.environment if wallet else "mainnet",
                            wallet_address=f"binance_{account.id}",
                            symbol=symbol,
                            side=operation,
                            quantity=trade_qty,
                            price=trade_price,
                            leverage=leverage,
                            order_id=str(order_result.get('order_id', '')),
                            order_status=status,
                            trade_value=trade_qty * trade_price,
                            fee=Decimal('0')
                        )
                        snapshot_db.add(trade_record)
                        snapshot_db.commit()
                        logger.info(f"[BINANCE] Trade record saved for {account.name}")
                    finally:
                        snapshot_db.close()
                except Exception as trade_err:
                    logger.warning(f"Failed to save Binance trade record: {trade_err}")
            else:
                logger.warning(f"[BINANCE] {operation.upper()} order failed: {order_result}")

    except Exception as e:
        logger.error(f"[BINANCE] Error executing {operation} for {symbol}: {e}", exc_info=True)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)


BINANCE_TRADE_JOB_ID = "binance_ai_trade"
