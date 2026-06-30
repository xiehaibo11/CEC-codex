"""
Paper Trading Service - Simulated execution that persists to the database.

Routes AI Trader decisions through the local order matching engine
(``order_matching.py``) so they are written to ``orders`` / ``positions`` /
``trades`` and logged to ``ai_decision_logs`` WITHOUT calling any real exchange.

Account routing (decided by callers):
    - hyperliquid_environment in {"testnet", "mainnet"} -> LIVE Hyperliquid path
      (``place_ai_driven_hyperliquid_order``); intentionally NOT handled here so
      real trading stays fully available.
    - hyperliquid_environment is NULL                   -> PAPER path (this file).

This module is deliberately self-contained to keep ``trading_commands.py`` from
growing past the file-size guideline and to avoid import cycles.
"""
import logging
from typing import Any, Dict, Iterable, List, Optional

from database.connection import SessionLocal
from database.models import Account, Position
from services.market_data import get_last_price
from services.order_matching import create_order, check_and_execute_order
from services.ai_decision_service import (
    call_ai_for_decision,
    save_ai_decision,
    _get_portfolio_data,
)
from services.hyperliquid_symbol_service import (
    get_selected_symbols as get_paper_selected_symbols,
    get_available_symbol_map as get_paper_symbol_map,
)

logger = logging.getLogger(__name__)

# Operation execution order: close/sell free up cash before buys are sized.
_DECISION_PRIORITY = {"close": 0, "sell": 1, "buy": 2, "hold": 3}
# Leave headroom for commission so a target_portion of 1.0 does not fail funding.
_BUY_CASH_BUFFER = 0.995


def _is_paper_account(account: Account) -> bool:
    """A paper account has no live Hyperliquid environment configured."""
    return getattr(account, "hyperliquid_environment", None) not in ("testnet", "mainnet")


def _fetch_prices(symbols: List[str]) -> Dict[str, float]:
    """Best-effort spot prices for the configured symbols."""
    prices: Dict[str, float] = {}
    for sym in symbols:
        try:
            price = get_last_price(sym)
            if price and float(price) > 0:
                prices[sym] = float(price)
        except Exception as err:
            logger.debug("Paper trading: no price for %s (%s)", sym, err)
    return prices


def _resolve_prompt_template_id(db, account: Account) -> Optional[int]:
    """Look up the bound prompt template for decision attribution (best-effort)."""
    try:
        from database.models import AccountPromptBinding

        binding = (
            db.query(AccountPromptBinding)
            .filter(
                AccountPromptBinding.account_id == account.id,
                AccountPromptBinding.is_deleted != True,  # noqa: E712
            )
            .first()
        )
        return binding.prompt_template_id if binding else None
    except Exception as err:
        logger.debug("Paper trading: prompt_template_id lookup failed: %s", err)
        return None


def _execute_paper_decision(
    db,
    account: Account,
    decision: Dict[str, Any],
    portfolio: Dict[str, Any],
    prices: Dict[str, float],
    symbol_whitelist: set,
    symbol_names: Dict[str, str],
    decision_kwargs: Dict[str, Any],
) -> bool:
    """Map one AI decision to a simulated order and persist it. Returns executed."""
    if not isinstance(decision, dict):
        logger.warning("Paper trading: skipping malformed decision for %s: %s", account.name, decision)
        return False

    operation = str(decision.get("operation", "")).lower()
    symbol = str(decision.get("symbol", "")).upper()
    target_portion = float(decision.get("target_portion_of_balance", 0) or 0)
    reason = decision.get("reason", "No reason provided")

    logger.info(
        "Paper decision for %s: %s %s (portion: %.2f%%) - %s",
        account.name, operation, symbol, target_portion * 100, reason,
    )

    if operation not in ("buy", "sell", "hold", "close"):
        logger.warning("Paper trading: invalid operation '%s' for %s", operation, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return False

    if operation == "hold":
        logger.info("Paper trading: HOLD for %s - no action", account.name)
        save_ai_decision(db, account, decision, portfolio, executed=True, **decision_kwargs)
        return False

    if symbol not in symbol_whitelist:
        logger.warning("Paper trading: symbol '%s' not in watchlist for %s", symbol, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return False

    price = prices.get(symbol)
    if not price or price <= 0:
        logger.warning("Paper trading: invalid price for %s (%s)", symbol, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return False

    if target_portion <= 0 or target_portion > 1:
        logger.warning("Paper trading: invalid target_portion %.4f for %s", target_portion, account.name)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return False

    name = symbol_names.get(symbol, symbol)

    # Determine side and quantity using the local (spot-style) virtual balance.
    if operation == "buy":
        side = "BUY"
        budget = float(account.current_cash) * target_portion * _BUY_CASH_BUFFER
        quantity = round(budget / price, 6)
        if quantity <= 0:
            logger.info("Paper trading: BUY budget too small for %s (%s)", symbol, account.name)
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return False
    else:  # "sell" or "close"
        side = "SELL"
        position = (
            db.query(Position)
            .filter(
                Position.account_id == account.id,
                Position.symbol == symbol,
                Position.market == "CRYPTO",
            )
            .first()
        )
        available = float(position.available_quantity) if position else 0.0
        if available <= 0:
            logger.info("Paper trading: no position to %s for %s (%s)", operation, symbol, account.name)
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return False
        # "close" always exits the full position; "sell" trims by target_portion.
        portion = 1.0 if operation == "close" else target_portion
        quantity = round(available * portion, 6)
        if quantity <= 0:
            save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
            return False

    try:
        order = create_order(
            db=db,
            account=account,
            symbol=symbol,
            name=name,
            side=side,
            order_type="MARKET",
            price=None,
            quantity=quantity,
        )
        db.commit()
        db.refresh(order)
    except ValueError as order_err:
        logger.info("Paper trading: order rejected for %s %s (%s): %s", side, symbol, account.name, order_err)
        save_ai_decision(db, account, decision, portfolio, executed=False, **decision_kwargs)
        return False

    executed = check_and_execute_order(db, order)
    if executed:
        db.refresh(order)
        logger.info(
            "Paper trading: EXECUTED %s %s %s qty=%s @ market (order %s)",
            account.name, side, symbol, quantity, order.order_no,
        )
    else:
        logger.info("Paper trading: order %s created but not filled (%s)", order.order_no, account.name)

    save_ai_decision(
        db, account, decision, portfolio,
        executed=executed, order_id=order.id, **decision_kwargs,
    )
    return executed


def place_ai_driven_paper_order(
    account_ids: Optional[Iterable[int]] = None,
    account_id: Optional[int] = None,
    symbol: Optional[str] = None,
    samples: Optional[List[Dict[str, Any]]] = None,
    bypass_auto_trading: bool = False,
    trigger_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Run AI Trader decisions for PAPER accounts through the local matcher.

    Args:
        account_ids: Optional iterable of account IDs to process.
        account_id: Optional single account ID (used by manual/Dashboard trigger).
        symbol: Optional symbol hint (currently informational).
        samples: Optional pre-built decisions (forced operation from the UI). When
            provided the AI model is not called and these decisions are executed.
        bypass_auto_trading: When True, run even if auto_trading_enabled is "false"
            (manual Dashboard trigger). Scheduler calls leave this False.
        trigger_context: Optional context (e.g. signal_trigger_id) for attribution.
    """
    # Resolve the target paper accounts.
    db = SessionLocal()
    try:
        if account_id is not None:
            account = (
                db.query(Account)
                .filter(Account.id == account_id, Account.is_deleted != True)  # noqa: E712
                .first()
            )
            if not account or account.is_active != "true":
                logger.debug("Paper trading: account %s missing/inactive", account_id)
                return
            if not bypass_auto_trading and getattr(account, "auto_trading_enabled", "false") != "true":
                logger.debug("Paper trading: account %s auto trading disabled", account_id)
                return
            if not _is_paper_account(account):
                logger.debug("Paper trading: account %s is live, not paper - skipping", account_id)
                return
            accounts = [account]
        else:
            query = db.query(Account).filter(
                Account.is_active == "true",
                Account.auto_trading_enabled == "true",
                Account.is_deleted != True,  # noqa: E712
            )
            accounts = [acc for acc in query.all() if _is_paper_account(acc)]
            if account_ids is not None:
                id_set = {int(a) for a in account_ids}
                accounts = [acc for acc in accounts if acc.id in id_set]
        if not accounts:
            logger.debug("Paper trading: no eligible paper accounts")
            return
        account_ids_resolved = [acc.id for acc in accounts]
    finally:
        db.close()

    selected_symbols = get_paper_selected_symbols()
    if not selected_symbols:
        logger.info("Paper trading: no watchlist configured, skipping")
        return
    symbol_whitelist = set(selected_symbols)
    symbol_map = get_paper_symbol_map()
    symbol_names = {s: dict(symbol_map.get(s, {})).get("name", s) for s in selected_symbols}

    prices = _fetch_prices(selected_symbols)
    if not prices:
        logger.info("Paper trading: failed to fetch market prices, skipping")
        return

    signal_trigger_id = trigger_context.get("signal_trigger_id") if trigger_context else None

    for acc_id in account_ids_resolved:
        db = SessionLocal()
        try:
            account = db.query(Account).filter(Account.id == acc_id).first()
            if not account:
                continue

            decision_kwargs = {
                "wallet_address": None,
                "exchange": "paper",
                "prompt_template_id": _resolve_prompt_template_id(db, account),
                "signal_trigger_id": signal_trigger_id,
            }

            portfolio = _get_portfolio_data(db, account)

            # Forced decisions from the UI bypass the model; otherwise ask the AI.
            decisions = samples
            if not decisions:
                if not account.api_key or not account.model:
                    logger.info(
                        "Paper trading: account '%s' skipped - AI model/API key not configured",
                        account.name,
                    )
                    continue
                decisions = call_ai_for_decision(
                    db, account, portfolio, prices,
                    symbols=selected_symbols,
                    hyperliquid_state=None,
                    trigger_context=trigger_context,
                )
            if not decisions:
                logger.warning("Paper trading: no decision for %s, skipping", account.name)
                continue

            ordered = sorted(
                (d for d in decisions if isinstance(d, dict)),
                key=lambda d: _DECISION_PRIORITY.get(str(d.get("operation", "")).lower(), 4),
            )
            for decision in ordered:
                try:
                    _execute_paper_decision(
                        db, account, decision, portfolio, prices,
                        symbol_whitelist, symbol_names, decision_kwargs,
                    )
                except Exception as decision_err:
                    db.rollback()
                    logger.error(
                        "Paper trading: failed to execute decision for %s: %s",
                        account.name, decision_err, exc_info=True,
                    )
        except Exception as account_err:
            logger.error("Paper trading: account %s failed: %s", acc_id, account_err, exc_info=True)
            db.rollback()
        finally:
            db.close()
