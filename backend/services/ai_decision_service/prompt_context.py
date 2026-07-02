"""Prompt context assembly for AI trading decisions.

_build_prompt_context is the single source of truth for prompt template
variables (kept intentionally cohesive); _get_portfolio_data loads portfolio
state from the main DB.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import Account, Position
from services.asset_calculator import calc_positions_value

from services.ai_decision_service.constants import (
    DECISION_TASK_TEXT,
    MAX_LEVERAGE_PLACEHOLDER,
    OUTPUT_FORMAT_COMPLETE,
    OUTPUT_FORMAT_JSON,
    SUPPORTED_SYMBOLS,
    SYMBOL_PLACEHOLDER,
)
from services.ai_decision_service.prompt_formatting import (
    _build_account_state,
    _build_holdings_detail,
    _build_market_prices,
    _build_market_snapshot,
    _build_sampling_data,
    _build_session_context,
    _calculate_runtime_minutes,
    _calculate_total_return_percent,
    _format_currency,
    _get_realtime_ticker_snapshot,
    _normalize_symbol_metadata,
)
from services.ai_decision_service.prompt_template_variables import build_template_variable_contexts
from services.ai_decision_service.prompt_runtime_sections import (
    build_market_regime_context,
    build_recent_trades_summary,
    build_trigger_context_text,
)

logger = logging.getLogger(__name__)


def _build_prompt_context(
    account: Account,
    portfolio: Dict[str, Any],
    prices: Dict[str, float],
    news_section: str,
    samples: Optional[List] = None,
    target_symbol: Optional[str] = None,
    hyperliquid_state: Optional[Dict[str, Any]] = None,
    *,
    db: Optional[Session] = None,
    symbol_metadata: Optional[Dict[str, Any]] = None,
    symbol_order: Optional[List[str]] = None,
    sampling_interval: Optional[int] = None,
    environment: str = "mainnet",
    template_text: Optional[str] = None,
    trigger_context: Optional[Dict[str, Any]] = None,
    exchange: str = "hyperliquid",
) -> Dict[str, Any]:
    """
    Build complete prompt context for AI decision-making.

    ⚠️ CRITICAL: This is the SINGLE and ONLY function responsible for building
    prompt context variables. ALL prompt template variable generation MUST happen
    here to ensure consistency between preview and actual AI decision execution.

    DO NOT create separate context-building logic elsewhere. If you need to add
    new template variables, add them here.

    Args:
        account: Trading account
        portfolio: Portfolio data with positions
        prices: Current market prices
        news_section: Latest news summary
        samples: Legacy price samples (deprecated)
        target_symbol: Legacy single symbol (deprecated)
        hyperliquid_state: Real-time Hyperliquid account state
        db: Database session (required for leverage settings lookup)
        symbol_metadata: Symbol display names and metadata
        symbol_order: Ordered list of symbols
        sampling_interval: Sampling interval in seconds
        environment: Trading environment (mainnet/testnet)
        template_text: Prompt template text for parsing K-line variables
        trigger_context: Context about what triggered this decision (signal or scheduled)
        exchange: Exchange to use for market data ("hyperliquid" or "binance")

    Returns:
        Complete context dictionary ready for template.format_map()
    """
    base_portfolio = portfolio or {}
    base_positions = base_portfolio.get("positions") or {}
    positions: Dict[str, Dict[str, Any]] = {symbol: dict(data) for symbol, data in base_positions.items()}

    symbol_source = symbol_metadata or SUPPORTED_SYMBOLS
    base_order = symbol_order or list(symbol_source.keys())
    ordered_symbols: List[str] = []
    seen_symbols = set()
    for sym in base_order:
        symbol_upper = str(sym).upper()
        if not symbol_upper or symbol_upper in seen_symbols:
            continue
        seen_symbols.add(symbol_upper)
        ordered_symbols.append(symbol_upper)
    if not ordered_symbols:
        ordered_symbols = list(SUPPORTED_SYMBOLS.keys())

    normalized_symbol_metadata = _normalize_symbol_metadata(symbol_metadata, ordered_symbols)
    symbol_display_map = {
        symbol: normalized_symbol_metadata.get(symbol, {}).get("name") or SUPPORTED_SYMBOLS.get(symbol, symbol)
        for symbol in ordered_symbols
    }
    selected_symbols_detail_lines = []
    for symbol in ordered_symbols:
        info = normalized_symbol_metadata.get(symbol, {})
        display_name = info.get("name") or symbol
        symbol_type = info.get("type")
        if symbol_type:
            selected_symbols_detail_lines.append(f"- {symbol}: {display_name} ({symbol_type})")
        else:
            selected_symbols_detail_lines.append(f"- {symbol}: {display_name}")
    selected_symbols_detail = "\n".join(selected_symbols_detail_lines) if selected_symbols_detail_lines else "None configured"
    selected_symbols_csv = ", ".join(ordered_symbols) if ordered_symbols else "N/A"
    output_symbol_choices = "|".join(ordered_symbols) if ordered_symbols else "SYMBOL"

    # NOTE: environment parameter is now passed from caller (call_ai_for_decision)

    # Use Hyperliquid state if provided (indicates Hyperliquid trading mode)
    if hyperliquid_state and environment in ("testnet", "mainnet"):
        hl_positions = hyperliquid_state.get("positions", []) or []
        positions = {}
        for pos in hl_positions:
            symbol = (pos.get("coin") or "").upper()
            if not symbol:
                continue

            quantity = float(pos.get("szi", 0) or 0)
            entry_px = float(pos.get("entry_px", 0) or 0)
            current_value = float(pos.get("position_value", 0) or 0)

            positions[symbol] = {
                "quantity": quantity,
                "avg_cost": entry_px,
                "current_value": current_value,
                "unrealized_pnl": float(pos.get("unrealized_pnl", 0) or 0),
                "leverage": pos.get("leverage"),
                "liquidation_price": pos.get("liquidation_px"),
            }

        portfolio = {
            "cash": float(hyperliquid_state.get("available_balance", 0) or 0),
            "frozen_cash": float(hyperliquid_state.get("used_margin", 0) or 0),
            "total_assets": float(hyperliquid_state.get("total_equity", 0) or 0),
            "positions": positions,
        }
    else:
        portfolio = {
            "cash": base_portfolio.get("cash"),
            "frozen_cash": base_portfolio.get("frozen_cash"),
            "total_assets": base_portfolio.get("total_assets"),
            "positions": positions,
        }

    now = datetime.utcnow()

    realtime_tickers = _get_realtime_ticker_snapshot(ordered_symbols, environment=environment, exchange=exchange)
    effective_prices: Dict[str, float] = dict(prices or {})
    for symbol, ticker in realtime_tickers.items():
        try:
            ticker_price = float((ticker or {}).get("price", 0) or 0)
        except (TypeError, ValueError):
            ticker_price = 0.0
        if ticker_price > 0:
            effective_prices[symbol.upper()] = ticker_price

    # Legacy format variables (for backward compatibility with existing templates)
    account_state = _build_account_state(portfolio)
    market_snapshot = _build_market_snapshot(effective_prices, positions, ordered_symbols)
    session_context = _build_session_context(account)
    sampling_data = _build_sampling_data(samples, target_symbol, sampling_interval)

    # New Alpha Arena style variables
    runtime_minutes = _calculate_runtime_minutes(account)
    current_time_utc = now.isoformat() + "Z"
    total_return_percent = _calculate_total_return_percent(account)
    available_cash = _format_currency(portfolio.get('cash'))
    total_account_value = _format_currency(portfolio.get('total_assets'))
    holdings_detail = _build_holdings_detail(positions)
    market_prices = _build_market_prices(effective_prices, ordered_symbols, symbol_display_map)
    # Legacy format (kept for backward compatibility with old templates)
    output_format_legacy = OUTPUT_FORMAT_JSON.replace(SYMBOL_PLACEHOLDER, output_symbol_choices or "SYMBOL")

    # Get leverage settings from the wallet source that matches the target exchange.
    if db:
        try:
            if exchange == "binance":
                from database.models import BinanceWallet

                wallet = db.query(BinanceWallet).filter(
                    BinanceWallet.account_id == account.id,
                    BinanceWallet.environment == environment,
                    BinanceWallet.is_active == "true"
                ).first()

                if wallet:
                    max_leverage = wallet.max_leverage
                    default_leverage = wallet.default_leverage
                else:
                    logger.warning(
                        f"No Binance wallet found for account {account.id} in {environment}, using defaults"
                    )
                    max_leverage = 20
                    default_leverage = 1
            else:
                from services.hyperliquid_environment import get_leverage_settings

                leverage_settings = get_leverage_settings(db, account.id, environment)
                max_leverage = leverage_settings["max_leverage"]
                default_leverage = leverage_settings["default_leverage"]
        except Exception as e:
            logger.warning(f"Failed to get leverage settings for account {account.id}: {e}, using fallback")
            if exchange == "binance":
                max_leverage = 20
                default_leverage = 1
            else:
                max_leverage = getattr(account, "max_leverage", 3)
                default_leverage = getattr(account, "default_leverage", 1)
    else:
        # Fallback if db not provided (should not happen in normal operation)
        logger.warning(f"No db session provided to _build_prompt_context, using Account table fallback for leverage")
        max_leverage = getattr(account, "max_leverage", 3)
        default_leverage = getattr(account, "default_leverage", 1)

    # Build complete output format with placeholders replaced
    output_format = OUTPUT_FORMAT_COMPLETE.replace(SYMBOL_PLACEHOLDER, output_symbol_choices or "SYMBOL").replace(MAX_LEVERAGE_PLACEHOLDER, str(max_leverage))

    # Use hyperliquid_state to determine if this is Hyperliquid trading mode
    if hyperliquid_state and environment in ("testnet", "mainnet"):
        trading_environment = f"Platform: Hyperliquid Perpetual Contracts | Environment: {environment.upper()}"

        if environment == "mainnet":
            real_trading_warning = "⚠️ REAL MONEY TRADING - All decisions execute on live markets"
            operational_constraints = f"""- Perpetual contract trading with cross margin
- Maximum position size: ≤ 25% of available balance per trade
- Leverage range: 1x to {max_leverage}x (default: {default_leverage}x)
- Margin call threshold: 80% margin usage (CRITICAL - will auto-liquidate)
- Default stop loss: -10% from entry (adjust based on leverage and volatility)
- Default take profit: +20% from entry (adjust based on risk/reward)
- Liquidation protection: NEVER exceed 70% margin usage
- Risk management: Monitor unrealized PnL and margin usage before each trade"""
        else:  # testnet
            real_trading_warning = "Testnet simulation environment (using test funds)"
            operational_constraints = f"""- Perpetual contract trading with cross margin (testnet mode)
- Default position size: ≤ 30% of available balance per trade
- Leverage range: 1x to {max_leverage}x (default: {default_leverage}x)
- Margin call threshold: 80% margin usage
- Default stop loss: -8% from entry (adjust based on leverage)
- Default take profit: +15% from entry
- Liquidation protection: avoid exceeding 70% margin usage"""

        leverage_constraints = f"- Leverage range: 1x to {max_leverage}x (default: {default_leverage}x)"
        margin_info = "\nMargin Mode: Cross margin (shared across all positions)"
    else:
        trading_environment = "Platform: Paper Trading Simulation"
        real_trading_warning = "Sandbox environment (no real funds at risk)"
        operational_constraints = """- No pyramiding or position size increases without explicit exit plan
- Default risk per trade: ≤ 20% of available cash
- Default stop loss: -5% from entry (adjust based on volatility)
- Default take profit: +10% from entry (adjust based on signals)"""
        leverage_constraints = ""
        margin_info = ""

    # Process Hyperliquid account state if provided
    if hyperliquid_state:
        total_equity = _format_currency(hyperliquid_state.get('total_equity'))
        available_balance = _format_currency(hyperliquid_state.get('available_balance'))
        used_margin = _format_currency(hyperliquid_state.get('used_margin', 0))
        margin_usage_percent = f"{hyperliquid_state.get('margin_usage_percent', 0):.1f}"
        maintenance_margin = _format_currency(hyperliquid_state.get('maintenance_margin', 0))

        # Build positions detail from Hyperliquid positions
        hl_positions = hyperliquid_state.get('positions', [])
        if hl_positions:
            pos_lines = []
            for pos in hl_positions:
                symbol = pos.get('coin', 'UNKNOWN')
                size = float(pos.get('szi', 0))
                direction = "Long" if size > 0 else "Short"
                abs_size = abs(size)
                entry_px = float(pos.get('entry_px', 0))
                unrealized_pnl = float(pos.get('unrealized_pnl', 0))
                leverage = float(pos.get('leverage', 1))
                position_max_leverage = float(pos.get('max_leverage', 10))  # Renamed to avoid conflict with account max_leverage
                margin_used = float(pos.get('margin_used', 0))
                position_value = float(pos.get('position_value', 0))
                roe = float(pos.get('return_on_equity', 0))
                funding_since_open = float(pos.get('cum_funding_since_open', 0) or 0)
                net_pnl = unrealized_pnl + funding_since_open
                liquidation_px = float(pos.get('liquidation_px', 0))
                leverage_type = pos.get('leverage_type', 'cross') or 'cross'

                # Position timing information (NEW)
                opened_at_str = pos.get('opened_at_str')
                holding_duration_str = pos.get('holding_duration_str')

                # Get current market price for this symbol
                current_price = effective_prices.get(symbol, entry_px)

                # Format values
                pnl_str = f"+${unrealized_pnl:,.2f}" if unrealized_pnl >= 0 else f"-${abs(unrealized_pnl):,.2f}"
                roe_str = f"+{roe:.2f}%" if roe >= 0 else f"{roe:.2f}%"
                funding_str = f"+${funding_since_open:.4f}" if funding_since_open >= 0 else f"-${abs(funding_since_open):.4f}"
                net_pnl_str = f"+${net_pnl:,.2f}" if net_pnl >= 0 else f"-${abs(net_pnl):,.2f}"
                leverage_type_str = leverage_type.capitalize()

                # Calculate distance to liquidation
                if liquidation_px > 0 and current_price > 0:
                    liq_distance_pct = abs(current_price - liquidation_px) / current_price * 100
                    liq_warning = " ⚠️" if liq_distance_pct < 10 else ""
                else:
                    liq_distance_pct = 0
                    liq_warning = ""

                # Build position timing line
                timing_line = ""
                if opened_at_str and holding_duration_str:
                    timing_line = f"  Opened: {opened_at_str} | Holding: {holding_duration_str}\n"

                pos_lines.append(
                    f"- {symbol}: {direction} {abs_size:.4f} units @ ${entry_px:,.2f} avg\n"
                    f"{timing_line}"
                    f"  Mark price: ${current_price:,.2f} | Position value: ${position_value:,.2f}\n"
                    f"  Unrealized P&L (exchange): {pnl_str} ({roe_str} ROE)\n"
                    f"  Funding Since Open: {funding_str} | Net P&L: {net_pnl_str}\n"
                    f"  Leverage: {leverage:.0f}x {leverage_type_str} (max {position_max_leverage:.0f}x) | Margin: ${margin_used:,.2f}\n"
                    f"  Liquidation: ${liquidation_px:,.2f} ({liq_distance_pct:.1f}% away){liq_warning}"
                )
            positions_detail = "\n".join(pos_lines)
        else:
            positions_detail = "No open positions"
    else:
        total_equity = "N/A"
        available_balance = "N/A"
        used_margin = "N/A"
        margin_usage_percent = "0"
        maintenance_margin = "N/A"
        positions_detail = "No open positions"

    recent_trades_summary = build_recent_trades_summary(
        account,
        hyperliquid_state,
        environment,
        exchange,
    )

    kline_context, factor_context, news_context = build_template_variable_contexts(
        template_text,
        realtime_tickers,
        environment,
        exchange,
    )

    trigger_context_text = build_trigger_context_text(trigger_context)

    market_regime_context = build_market_regime_context(db, ordered_symbols, trigger_context, exchange)

    return {
        # Legacy variables (for Default prompt and backward compatibility)
        "account_state": account_state,
        "market_snapshot": market_snapshot,
        "session_context": session_context,
        "sampling_data": sampling_data,
        "decision_task": DECISION_TASK_TEXT,
        "output_format": output_format,
        "prices_json": json.dumps(effective_prices, indent=2, sort_keys=True),
        "portfolio_json": json.dumps(portfolio, indent=2, sort_keys=True),
        "portfolio_positions_json": json.dumps(positions, indent=2, sort_keys=True),
        "news_section": news_section,
        "account_name": account.name,
        "model_name": account.model or "",
        # New Alpha Arena style variables (for Pro prompt)
        "runtime_minutes": runtime_minutes,
        "current_time_utc": current_time_utc,
        "total_return_percent": total_return_percent,
        "available_cash": available_cash,
        "total_account_value": total_account_value,
        "holdings_detail": positions_detail if hyperliquid_state else holdings_detail,
        "market_prices": market_prices,
        "selected_symbols_csv": selected_symbols_csv,
        "selected_symbols_detail": selected_symbols_detail,
        "selected_symbols_count": len(ordered_symbols),
        # Hyperliquid-specific variables
        "trading_environment": trading_environment,
        "real_trading_warning": real_trading_warning,
        "operational_constraints": operational_constraints,
        "leverage_constraints": leverage_constraints,
        "margin_info": margin_info,
        "environment": environment,
        "max_leverage": max_leverage,
        "default_leverage": default_leverage,
        # Hyperliquid account state (dynamic from API)
        "total_equity": total_equity,
        "available_balance": available_balance,
        "used_margin": used_margin,
        "margin_usage_percent": margin_usage_percent,
        "maintenance_margin": maintenance_margin,
        "positions_detail": positions_detail,
        # Recent trades history (NEW - helps AI understand trading patterns)
        "recent_trades_summary": recent_trades_summary,
        # Trigger context (signal or scheduled trigger information)
        "trigger_context": trigger_context_text,
        # K-line and technical indicator variables (dynamically generated)
        **kline_context,  # Merge K-line/indicator variables like {BTC_klines_15m}, {BTC_MACD_15m}, etc.
        # Market Regime classification variables (multi-timeframe)
        **market_regime_context,  # Merge {market_regime}, {BTC_market_regime_5m}, etc.
        # Factor variables like {BTC_factor_1h_RSI21}
        **factor_context,
        # News intelligence variables like {BTC_news_sentiment}, {macro_news}, etc.
        **news_context,
    }
def _get_portfolio_data(db: Session, account: Account) -> Dict:
    """Get current portfolio positions and values"""
    positions = db.query(Position).filter(
        Position.account_id == account.id,
        Position.market == "CRYPTO"
    ).all()
    
    portfolio = {}
    for pos in positions:
        if float(pos.quantity) > 0:
            portfolio[pos.symbol] = {
                "quantity": float(pos.quantity),
                "avg_cost": float(pos.avg_cost),
                "current_value": float(pos.quantity) * float(pos.avg_cost)
            }
    
    return {
        "cash": float(account.current_cash),
        "frozen_cash": float(account.frozen_cash),
        "positions": portfolio,
        "total_assets": float(account.current_cash) + calc_positions_value(db, account.id)
    }
