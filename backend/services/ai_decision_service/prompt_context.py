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
    _format_market_data_block,
    _get_metric_unit,
    _get_realtime_ticker_snapshot,
    _normalize_symbol_metadata,
)
from services.ai_decision_service.kline_context import (
    _build_factor_context,
    _build_klines_and_indicators_context,
    _parse_factor_variables,
    _parse_kline_indicator_variables,
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

    # ============================================================================
    # RECENT TRADES HISTORY SUMMARY
    # ============================================================================
    # Build recent closed trades summary to help AI understand trading patterns
    # and avoid flip-flop behavior (rapid position reversals)
    recent_trades_summary = "No recent trade history available"

    # Support both Hyperliquid and Binance exchanges
    if (hyperliquid_state or exchange == "binance") and environment in ("testnet", "mainnet"):
        try:
            from database.connection import SessionLocal

            with SessionLocal() as db_session:
                recent_trades = []
                open_orders = []

                if exchange == "binance":
                    # Get Binance trading client
                    from services.binance_trading_client import BinanceTradingClient
                    from database.models import BinanceWallet
                    from utils.encryption import decrypt_private_key

                    binance_wallet = db_session.query(BinanceWallet).filter(
                        BinanceWallet.account_id == account.id,
                        BinanceWallet.environment == environment,
                        BinanceWallet.is_active == "true"
                    ).first()

                    if binance_wallet and binance_wallet.api_key_encrypted:
                        api_key = decrypt_private_key(binance_wallet.api_key_encrypted)
                        secret_key = decrypt_private_key(binance_wallet.secret_key_encrypted)
                        client = BinanceTradingClient(
                            api_key=api_key,
                            secret_key=secret_key,
                            environment=binance_wallet.environment or "testnet"
                        )
                        recent_trades = client.get_recent_closed_trades(db_session, limit=5)
                        open_orders = client.get_open_orders_formatted(db_session)
                    else:
                        recent_trades_summary = "Binance wallet not configured"
                else:
                    # Get Hyperliquid trading client (uses get_hyperliquid_client to support API Wallet)
                    from services.hyperliquid_environment import get_hyperliquid_client

                    try:
                        client = get_hyperliquid_client(db_session, account.id, override_environment=environment)
                        recent_trades = client.get_recent_closed_trades(db_session, limit=5)
                        open_orders = client.get_open_orders(db_session)
                    except ValueError:
                        recent_trades_summary = "Wallet not configured for this environment"

                # Build recent trades section (common format for both exchanges)
                if recent_trades or open_orders:
                    trades_section = ""
                    if recent_trades:
                        trade_lines = ["Recent closed trades (last 5 positions):"]
                        for trade in recent_trades:
                            symbol = trade.get('symbol', 'UNKNOWN')
                            side = trade.get('side', 'Unknown')
                            close_time = trade.get('close_time', 'N/A')
                            close_price = trade.get('close_price', 0)
                            realized_pnl = trade.get('realized_pnl', 0)
                            direction = trade.get('direction', '')

                            pnl_str = f"+${realized_pnl:,.2f}" if realized_pnl >= 0 else f"-${abs(realized_pnl):,.2f}"
                            trade_lines.append(
                                f"- {symbol} {side}: Closed at {close_time} @ ${close_price:,.2f} | P&L: {pnl_str} | {direction}"
                            )
                        trades_section = "\n".join(trade_lines)
                    else:
                        trades_section = "Recent closed trades: No recent closed trades found"

                    # Build open orders section
                    orders_section = ""
                    if open_orders:
                        display_orders = open_orders[:10]
                        order_lines = [f"\nOpen orders ({len(open_orders)} pending):"]
                        for order in display_orders:
                            symbol = order.get('symbol', 'UNKNOWN')
                            direction = order.get('direction', 'Unknown')
                            order_type = order.get('order_type', 'Limit')
                            order_id = order.get('order_id', 'N/A')
                            price = order.get('price', 0)
                            size = order.get('size', 0)
                            order_value = order.get('order_value', 0)
                            reduce_only = "Yes" if order.get('reduce_only', False) else "No"
                            trigger_condition = order.get('trigger_condition')
                            order_time = order.get('order_time', 'N/A')

                            trigger_info = f"Trigger: {trigger_condition}" if trigger_condition else "Trigger: None"
                            order_lines.append(
                                f"- {symbol} {direction}: {order_type} Order #{order_id} @ ${price:,.2f} | "
                                f"Size: {size:.5f} | Value: ${order_value:,.2f} | Reduce Only: {reduce_only} | "
                                f"{trigger_info} | Placed: {order_time}"
                            )
                        orders_section = "\n".join(order_lines)
                    else:
                        orders_section = "\nOpen orders: No open orders"

                    recent_trades_summary = orders_section + "\n\n" + trades_section

        except Exception as e:
            logger.warning(f"Failed to get recent trades summary: {e}", exc_info=True)
            recent_trades_summary = f"Error fetching trade history: {str(e)[:100]}"

    # ============================================================================
    # K-LINE AND TECHNICAL INDICATORS PROCESSING
    # ============================================================================
    # Process K-line and technical indicator variables if template_text is provided.
    # This ensures that variables like {BTC_klines_15m}, {BTC_MACD_15m}, etc.
    # are properly populated with real data instead of showing "N/A".
    #
    # IMPORTANT: This processing MUST stay inside _build_prompt_context to ensure
    # preview and AI decision execution use the same logic.
    kline_context = {}
    if template_text:
        try:
            from database.connection import SessionLocal
            variable_groups = _parse_kline_indicator_variables(template_text)
            if variable_groups:
                # Reuse the same realtime ticker snapshot for {SYMBOL_market_data}
                # so market_prices, positions_detail, and market_data stay aligned.
                market_data_groups = {}
                non_market_groups = {}
                for key, requirements in variable_groups.items():
                    symbol, period = key
                    if period is None and requirements.get("market_data"):
                        market_data_groups[key] = requirements
                    else:
                        non_market_groups[key] = requirements

                for (symbol, _period), _requirements in market_data_groups.items():
                    ticker = realtime_tickers.get(symbol)
                    if ticker:
                        kline_context[f"{symbol}_market_data"] = _format_market_data_block(symbol, ticker)

                if non_market_groups:
                    with SessionLocal() as db:
                        kline_context.update(
                            _build_klines_and_indicators_context(
                                non_market_groups,
                                db,
                                environment,
                                exchange,
                            )
                        )
                logger.debug(f"Built K-line context with {len(kline_context)} variables")
        except Exception as e:
            logger.warning(f"Failed to build K-line context: {e}", exc_info=True)

    # ============================================================================
    # FACTOR VARIABLES PROCESSING
    # ============================================================================
    # Process factor variables like {BTC_factor_1h_RSI21} from prompt template.
    # Legacy {BTC_factor_RSI21} syntax still works and defaults to 5m.
    factor_context = {}
    if template_text:
        try:
            factor_vars = _parse_factor_variables(template_text)
            if factor_vars:
                factor_context = _build_factor_context(factor_vars, environment, exchange)
                logger.debug(f"Built factor context with {len(factor_context)} variables")
        except Exception as e:
            logger.warning(f"Failed to build factor context: {e}", exc_info=True)

    # ============================================================================
    # NEWS INTELLIGENCE VARIABLES
    # ============================================================================
    # Process news variables like {BTC_news_sentiment}, {BTC_news_headlines_4h},
    # {macro_news}, {general_news} from prompt template.
    news_context = {}
    if template_text:
        try:
            from services.news_prompt_variables import build_news_context
            from database.connection import SessionLocal
            with SessionLocal() as news_db:
                news_context = build_news_context(template_text, news_db)
            if news_context:
                logger.debug(f"Built news context with {len(news_context)} variables")
        except Exception as e:
            logger.warning(f"Failed to build news context: {e}", exc_info=True)

    # ============================================================================
    # TRIGGER CONTEXT FORMATTING
    # ============================================================================
    # Format trigger context into structured text for AI prompt.
    # This tells the AI what triggered this decision (signal or scheduled).
    trigger_context_text = ""
    if trigger_context:
        trigger_type = trigger_context.get("trigger_type", "unknown")
        lines = [f"=== TRIGGER CONTEXT ===", f"trigger_type: {trigger_type}"]

        if trigger_type == "signal":
            pool_name = trigger_context.get("signal_pool_name", "Unknown")
            pool_logic = trigger_context.get("pool_logic", "OR")
            trigger_symbol = trigger_context.get("trigger_symbol", "N/A")
            lines.append(f"signal_pool_name: {pool_name}")
            lines.append(f"pool_logic: {pool_logic}")
            lines.append(f"trigger_symbol: {trigger_symbol}")

            triggered_signals = trigger_context.get("triggered_signals", [])
            if triggered_signals:
                lines.append("triggered_signals:")
                for sig in triggered_signals:
                    # Support both "signal_name" (from signal_detection_service) and "name" (fallback)
                    sig_name = sig.get("signal_name") or sig.get("name", "Unknown Signal")
                    description = sig.get("description")
                    metric = sig.get("metric", "N/A")
                    time_window = sig.get("time_window", "N/A")

                    lines.append(f"  - name: {sig_name}")
                    if description:
                        lines.append(f"    description: {description}")

                    # Special handling for taker_volume composite signal
                    if metric == "taker_volume":
                        direction = sig.get("actual_direction") or sig.get("direction", "N/A")
                        buy = sig.get("buy", 0)
                        sell = sig.get("sell", 0)
                        ratio = sig.get("ratio", 0)
                        ratio_threshold = sig.get("ratio_threshold", 1.5)
                        volume_threshold = sig.get("volume_threshold", 0)
                        # Calculate dominant side multiplier for clarity
                        if direction == "buy" and ratio > 0:
                            multiplier = ratio
                            dominant = "buyers"
                        elif direction == "sell" and ratio > 0:
                            multiplier = 1 / ratio if ratio > 0 else 0
                            dominant = "sellers"
                        else:
                            multiplier = ratio
                            dominant = "N/A"
                        lines.append(f"    metric: taker_volume")
                        lines.append(f"    direction: {direction}")
                        lines.append(f"    taker_buy: ${buy/1e6:.2f}M")
                        lines.append(f"    taker_sell: ${sell/1e6:.2f}M")
                        lines.append(f"    dominant: {dominant} {multiplier:.2f}x (threshold: {ratio_threshold}x)")
                    else:
                        # Standard single-value signal
                        operator = sig.get("operator", "N/A")
                        threshold = sig.get("threshold", "N/A")
                        actual_value = sig.get("current_value") or sig.get("actual_value", "N/A")

                        unit = _get_metric_unit(metric)
                        metric_display = f"{metric} ({unit})" if unit else metric
                        threshold_display = f"{threshold}{unit}" if unit else str(threshold)
                        value_display = f"{actual_value:.4f}{unit}" if isinstance(actual_value, (int, float)) and unit else str(actual_value)

                        lines.append(f"    metric: {metric_display}")
                        lines.append(f"    time_window: {time_window}")
                        lines.append(f"    condition: {operator} {threshold_display}")
                        lines.append(f"    current_value: {value_display}")

                        # Factor effectiveness context
                        fe = sig.get("factor_effectiveness")
                        if fe:
                            parts = []
                            if fe.get("ic") is not None:
                                parts.append(f"IC={fe['ic']}")
                            if fe.get("icir") is not None:
                                parts.append(f"ICIR={fe['icir']}")
                            if fe.get("win_rate") is not None:
                                parts.append(f"WinRate={fe['win_rate']}%")
                            dh = fe.get("decay_half_life_hours")
                            if dh is not None:
                                parts.append("Persistent" if dh == -1 else f"Decay={dh}h")
                            if parts:
                                lines.append(f"    factor_effectiveness: {' '.join(parts)}")
        elif trigger_type == "wallet_signal":
            pool_name = trigger_context.get("signal_pool_name", "Unknown")
            trigger_symbol = trigger_context.get("trigger_symbol", "N/A")
            wallet_event = trigger_context.get("wallet_event") or {}
            detail = wallet_event.get("detail") or {}

            lines.append(f"signal_pool_name: {pool_name}")
            lines.append(f"trigger_symbol: {trigger_symbol}")
            lines.append(f"address: {wallet_event.get('address', 'N/A')}")
            lines.append(f"event_type: {wallet_event.get('event_type', 'N/A')}")
            lines.append(f"event_level: {wallet_event.get('event_level', 'N/A')}")
            lines.append(f"summary: {wallet_event.get('summary', 'N/A')}")
            if detail:
                if detail.get("action") is not None:
                    lines.append(f"action: {detail.get('action')}")
                if detail.get("direction") is not None:
                    lines.append(f"direction: {detail.get('direction')}")
                if detail.get("notional_value") is not None:
                    lines.append(f"notional_value: {detail.get('notional_value')}")
                if detail.get("entry_price") is not None:
                    lines.append(f"entry_price: {detail.get('entry_price')}")
                if detail.get("leverage") is not None:
                    lines.append(f"leverage: {detail.get('leverage')}")
                if detail.get("unrealized_pnl") is not None:
                    lines.append(f"unrealized_pnl: {detail.get('unrealized_pnl')}")
                if detail.get("liquidation_price") is not None:
                    lines.append(f"liquidation_price: {detail.get('liquidation_price')}")
                if detail.get("old_value") is not None:
                    lines.append(f"old_value: {detail.get('old_value')}")
                if detail.get("new_value") is not None:
                    lines.append(f"new_value: {detail.get('new_value')}")
                if detail.get("closed_pnl") is not None:
                    lines.append(f"closed_pnl: {detail.get('closed_pnl')}")
                if detail.get("average_price") is not None:
                    lines.append(f"average_price: {detail.get('average_price')}")
                if detail.get("start_position") is not None:
                    lines.append(f"start_position: {detail.get('start_position')}")
                if detail.get("end_position") is not None:
                    lines.append(f"end_position: {detail.get('end_position')}")
                if detail.get("fills_count") is not None:
                    lines.append(f"fills_count: {detail.get('fills_count')}")
        elif trigger_type == "scheduled":
            interval = trigger_context.get("trigger_interval", "N/A")
            lines.append(f"trigger_interval: {interval} seconds")

        trigger_context_text = "\n".join(lines)

    # ============================================================================
    # Market Regime Classification Variables
    # ============================================================================
    # Variables provided:
    # - {market_regime} - summary of all symbols (default 5m timeframe)
    # - {market_regime_description} - indicator calculation methodology
    # - {BTC_market_regime}, {ETH_market_regime} - per-symbol (default 5m)
    # - {BTC_market_regime_1m}, {BTC_market_regime_5m}, {BTC_market_regime_15m}, {BTC_market_regime_1h}
    # - {market_regime_1m}, {market_regime_5m}, {market_regime_15m}, {market_regime_1h}
    market_regime_context = {}

    # Indicator calculation description for AI understanding
    market_regime_context["market_regime_description"] = """Market Regime Indicator Definitions:
- cvd_ratio: CVD / (Taker Buy + Taker Sell). Positive = net buying pressure, negative = net selling
- oi_delta: Open Interest change percentage over the period
- taker: Taker Buy/Sell ratio. >1 = aggressive buying, <1 = aggressive selling
- rsi: RSI(14) momentum indicator. >70 overbought, <30 oversold
- price_atr: (Close - Open) / ATR. Measures price movement relative to volatility

Regime Types:
- breakout: Strong directional move with volume confirmation
- absorption: Large orders absorbed without price impact (potential reversal)
- stop_hunt: Wick beyond range then reversal (liquidity grab)
- exhaustion: Extreme RSI with diverging CVD (trend weakening)
- trap: Price breaks level but CVD/OI diverge (false breakout)
- continuation: Trend continuation with aligned indicators
- noise: No clear pattern, low conviction"""

    if db:
        try:
            from services.market_regime_service import get_market_regime
            supported_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

            def format_regime_text(symbol, tf, result):
                """Format regime result with symbol and timeframe context"""
                regime = result['regime']
                direction = result['direction']
                conf = result['confidence']
                ind = result.get('indicators', {})
                if not ind:
                    return f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | insufficient data"
                return (
                    f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | "
                    f"cvd_ratio={ind.get('cvd_ratio', 0):.3f}, oi_delta={ind.get('oi_delta', 0):.3f}%, "
                    f"taker={ind.get('taker_ratio', 1):.2f}, rsi={ind.get('rsi', 50):.1f}"
                )

            for tf in supported_timeframes:
                tf_regime_lines = []
                for symbol in ordered_symbols:
                    regime_result = get_market_regime(db, symbol, tf, use_realtime=True, exchange=exchange)
                    regime_text = format_regime_text(symbol, tf, regime_result)
                    market_regime_context[f"{symbol}_market_regime_{tf}"] = regime_text
                    tf_regime_lines.append(f"- {regime_text}")
                market_regime_context[f"market_regime_{tf}"] = "\n".join(tf_regime_lines) if tf_regime_lines else "N/A"

            # Default variables (5m) for backward compatibility
            for symbol in ordered_symbols:
                market_regime_context[f"{symbol}_market_regime"] = market_regime_context.get(f"{symbol}_market_regime_5m", "N/A")
            market_regime_context["market_regime"] = market_regime_context.get("market_regime_5m", "N/A")

            # ============================================================================
            # Trigger Market Regime Variable
            # ============================================================================
            # {trigger_market_regime} - The market regime captured at signal trigger time.
            # This is the regime that was calculated when the signal pool triggered,
            # NOT the current real-time regime. Use this to ensure AI sees the same
            # regime that caused the trigger.
            #
            # Only available for signal triggers (trigger_type = "signal").
            # For scheduled triggers, this will be "N/A".
            market_regime_context["trigger_market_regime"] = "N/A"

            if trigger_context and trigger_context.get("trigger_type") == "signal":
                signal_trigger_id = trigger_context.get("signal_trigger_id")
                if signal_trigger_id:
                    # Real trigger - fetch from database
                    try:
                        from sqlalchemy import text
                        result = db.execute(
                            text("SELECT market_regime FROM signal_trigger_logs WHERE id = :id"),
                            {"id": signal_trigger_id}
                        )
                        row = result.fetchone()
                        if row and row[0]:
                            regime_json = row[0]
                            # Parse JSON if it's a string
                            if isinstance(regime_json, str):
                                regime_data = json.loads(regime_json)
                            else:
                                regime_data = regime_json

                            # Format to match other regime variables
                            symbol = regime_data.get("symbol", "N/A")
                            tf = regime_data.get("timeframe", "5m")
                            regime = regime_data.get("regime", "unknown")
                            direction = regime_data.get("direction", "neutral")
                            conf = regime_data.get("confidence", 0)
                            # Get indicators (backward compatible - old data may not have this)
                            ind = regime_data.get("indicators", {})

                            if ind:
                                market_regime_context["trigger_market_regime"] = (
                                    f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | "
                                    f"cvd_ratio={ind.get('cvd_ratio', 0):.3f}, oi_delta={ind.get('oi_delta', 0):.3f}%, "
                                    f"taker={ind.get('taker_ratio', 1):.2f}, rsi={ind.get('rsi', 50):.1f} | (trigger snapshot)"
                                )
                            else:
                                # Old data without indicators
                                market_regime_context["trigger_market_regime"] = (
                                    f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | (trigger snapshot)"
                                )
                    except Exception as e:
                        logger.warning(f"Failed to get trigger market regime: {e}")
                else:
                    # Preview mode - no signal_trigger_id, provide sample value
                    # Use trigger_symbol from context if available
                    trigger_symbol = trigger_context.get("trigger_symbol", "BTC")
                    # Get time_window from first triggered signal if available
                    triggered_signals = trigger_context.get("triggered_signals", [])
                    if triggered_signals:
                        sample_tf = triggered_signals[0].get("time_window", "5m")
                    else:
                        sample_tf = "5m"
                    market_regime_context["trigger_market_regime"] = (
                        f"[{trigger_symbol}/{sample_tf}] breakout (bullish) conf=0.65 | "
                        f"cvd_ratio=0.286, oi_delta=0.857%, taker=1.80, rsi=50.7 | (trigger snapshot - preview)"
                    )

        except Exception as e:
            logger.warning(f"Failed to get market regime data: {e}")
            market_regime_context["market_regime"] = "N/A"
            market_regime_context["trigger_market_regime"] = "N/A"
    else:
        market_regime_context["market_regime"] = "N/A"
        market_regime_context["trigger_market_regime"] = "N/A"

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
