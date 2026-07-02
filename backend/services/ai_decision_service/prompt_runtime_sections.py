"""Runtime prompt sections for AI trading context."""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import Account
from services.ai_decision_service.prompt_formatting import _get_metric_unit

logger = logging.getLogger(__name__)


def build_recent_trades_summary(
    account: Account,
    hyperliquid_state: Optional[Dict[str, Any]],
    environment: str,
    exchange: str,
) -> str:
    """Build recent closed trades and open orders summary for prompt context."""
    recent_trades_summary = "No recent trade history available"

    if not (hyperliquid_state or exchange == "binance") or environment not in ("testnet", "mainnet"):
        return recent_trades_summary

    try:
        from database.connection import SessionLocal

        with SessionLocal() as db_session:
            recent_trades = []
            open_orders = []

            if exchange == "binance":
                recent_trades_summary = _load_binance_trades(
                    db_session,
                    account,
                    environment,
                    recent_trades,
                    open_orders,
                )
            else:
                recent_trades_summary = _load_hyperliquid_trades(
                    db_session,
                    account,
                    environment,
                    recent_trades,
                    open_orders,
                )

            if recent_trades or open_orders:
                recent_trades_summary = _format_trade_and_order_sections(recent_trades, open_orders)
    except Exception as err:
        logger.warning("Failed to get recent trades summary: %s", err, exc_info=True)
        recent_trades_summary = f"Error fetching trade history: {str(err)[:100]}"

    return recent_trades_summary


def _load_binance_trades(
    db_session: Session,
    account: Account,
    environment: str,
    recent_trades: List[Dict[str, Any]],
    open_orders: List[Dict[str, Any]],
) -> str:
    from database.models import BinanceWallet
    from services.binance_trading_client import BinanceTradingClient
    from utils.encryption import decrypt_private_key

    binance_wallet = db_session.query(BinanceWallet).filter(
        BinanceWallet.account_id == account.id,
        BinanceWallet.environment == environment,
        BinanceWallet.is_active == "true",
    ).first()

    if not binance_wallet or not binance_wallet.api_key_encrypted:
        return "Binance wallet not configured"

    api_key = decrypt_private_key(binance_wallet.api_key_encrypted)
    secret_key = decrypt_private_key(binance_wallet.secret_key_encrypted)
    client = BinanceTradingClient(
        api_key=api_key,
        secret_key=secret_key,
        environment=binance_wallet.environment or "testnet",
    )
    recent_trades.extend(client.get_recent_closed_trades(db_session, limit=5))
    open_orders.extend(client.get_open_orders_formatted(db_session))
    return "No recent trade history available"


def _load_hyperliquid_trades(
    db_session: Session,
    account: Account,
    environment: str,
    recent_trades: List[Dict[str, Any]],
    open_orders: List[Dict[str, Any]],
) -> str:
    from services.hyperliquid_environment import get_hyperliquid_client

    try:
        client = get_hyperliquid_client(db_session, account.id, override_environment=environment)
        recent_trades.extend(client.get_recent_closed_trades(db_session, limit=5))
        open_orders.extend(client.get_open_orders(db_session))
    except ValueError:
        return "Wallet not configured for this environment"

    return "No recent trade history available"


def _format_trade_and_order_sections(
    recent_trades: List[Dict[str, Any]],
    open_orders: List[Dict[str, Any]],
) -> str:
    if recent_trades:
        trade_lines = ["Recent closed trades (last 5 positions):"]
        for trade in recent_trades:
            symbol = trade.get("symbol", "UNKNOWN")
            side = trade.get("side", "Unknown")
            close_time = trade.get("close_time", "N/A")
            close_price = trade.get("close_price", 0)
            realized_pnl = trade.get("realized_pnl", 0)
            direction = trade.get("direction", "")

            pnl_str = f"+${realized_pnl:,.2f}" if realized_pnl >= 0 else f"-${abs(realized_pnl):,.2f}"
            trade_lines.append(
                f"- {symbol} {side}: Closed at {close_time} @ ${close_price:,.2f} | "
                f"P&L: {pnl_str} | {direction}"
            )
        trades_section = "\n".join(trade_lines)
    else:
        trades_section = "Recent closed trades: No recent closed trades found"

    if open_orders:
        display_orders = open_orders[:10]
        order_lines = [f"\nOpen orders ({len(open_orders)} pending):"]
        for order in display_orders:
            symbol = order.get("symbol", "UNKNOWN")
            direction = order.get("direction", "Unknown")
            order_type = order.get("order_type", "Limit")
            order_id = order.get("order_id", "N/A")
            price = order.get("price", 0)
            size = order.get("size", 0)
            order_value = order.get("order_value", 0)
            reduce_only = "Yes" if order.get("reduce_only", False) else "No"
            trigger_condition = order.get("trigger_condition")
            order_time = order.get("order_time", "N/A")

            trigger_info = f"Trigger: {trigger_condition}" if trigger_condition else "Trigger: None"
            order_lines.append(
                f"- {symbol} {direction}: {order_type} Order #{order_id} @ ${price:,.2f} | "
                f"Size: {size:.5f} | Value: ${order_value:,.2f} | Reduce Only: {reduce_only} | "
                f"{trigger_info} | Placed: {order_time}"
            )
        orders_section = "\n".join(order_lines)
    else:
        orders_section = "\nOpen orders: No open orders"

    return orders_section + "\n\n" + trades_section


def build_trigger_context_text(trigger_context: Optional[Dict[str, Any]]) -> str:
    """Format signal, wallet-signal, or scheduled trigger context for prompts."""
    if not trigger_context:
        return ""

    trigger_type = trigger_context.get("trigger_type", "unknown")
    lines = [f"=== TRIGGER CONTEXT ===", f"trigger_type: {trigger_type}"]

    if trigger_type == "signal":
        _append_signal_trigger_context(lines, trigger_context)
    elif trigger_type == "wallet_signal":
        _append_wallet_trigger_context(lines, trigger_context)
    elif trigger_type == "scheduled":
        interval = trigger_context.get("trigger_interval", "N/A")
        lines.append(f"trigger_interval: {interval} seconds")

    return "\n".join(lines)


def _append_signal_trigger_context(lines: List[str], trigger_context: Dict[str, Any]) -> None:
    pool_name = trigger_context.get("signal_pool_name", "Unknown")
    pool_logic = trigger_context.get("pool_logic", "OR")
    trigger_symbol = trigger_context.get("trigger_symbol", "N/A")
    lines.append(f"signal_pool_name: {pool_name}")
    lines.append(f"pool_logic: {pool_logic}")
    lines.append(f"trigger_symbol: {trigger_symbol}")

    triggered_signals = trigger_context.get("triggered_signals", [])
    if not triggered_signals:
        return

    lines.append("triggered_signals:")
    for sig in triggered_signals:
        sig_name = sig.get("signal_name") or sig.get("name", "Unknown Signal")
        description = sig.get("description")
        metric = sig.get("metric", "N/A")
        time_window = sig.get("time_window", "N/A")

        lines.append(f"  - name: {sig_name}")
        if description:
            lines.append(f"    description: {description}")

        if metric == "taker_volume":
            _append_taker_volume_signal(lines, sig)
        else:
            _append_standard_signal(lines, sig, metric, time_window)


def _append_taker_volume_signal(lines: List[str], sig: Dict[str, Any]) -> None:
    direction = sig.get("actual_direction") or sig.get("direction", "N/A")
    buy = sig.get("buy", 0)
    sell = sig.get("sell", 0)
    ratio = sig.get("ratio", 0)
    ratio_threshold = sig.get("ratio_threshold", 1.5)

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


def _append_standard_signal(
    lines: List[str],
    sig: Dict[str, Any],
    metric: str,
    time_window: str,
) -> None:
    operator = sig.get("operator", "N/A")
    threshold = sig.get("threshold", "N/A")
    actual_value = sig.get("current_value") or sig.get("actual_value", "N/A")

    unit = _get_metric_unit(metric)
    metric_display = f"{metric} ({unit})" if unit else metric
    threshold_display = f"{threshold}{unit}" if unit else str(threshold)
    value_display = (
        f"{actual_value:.4f}{unit}"
        if isinstance(actual_value, (int, float)) and unit
        else str(actual_value)
    )

    lines.append(f"    metric: {metric_display}")
    lines.append(f"    time_window: {time_window}")
    lines.append(f"    condition: {operator} {threshold_display}")
    lines.append(f"    current_value: {value_display}")

    fe = sig.get("factor_effectiveness")
    if not fe:
        return

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


def _append_wallet_trigger_context(lines: List[str], trigger_context: Dict[str, Any]) -> None:
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

    for key in (
        "action",
        "direction",
        "notional_value",
        "entry_price",
        "leverage",
        "unrealized_pnl",
        "liquidation_price",
        "old_value",
        "new_value",
        "closed_pnl",
        "average_price",
        "start_position",
        "end_position",
        "fills_count",
    ):
        if detail.get(key) is not None:
            lines.append(f"{key}: {detail.get(key)}")


def build_market_regime_context(
    db: Optional[Session],
    ordered_symbols: List[str],
    trigger_context: Optional[Dict[str, Any]],
    exchange: str,
) -> Dict[str, str]:
    """Build market-regime prompt variables across symbols and timeframes."""
    market_regime_context = {
        "market_regime_description": """Market Regime Indicator Definitions:
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
    }

    if not db:
        market_regime_context["market_regime"] = "N/A"
        market_regime_context["trigger_market_regime"] = "N/A"
        return market_regime_context

    try:
        from services.market_regime_service import get_market_regime

        supported_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        for tf in supported_timeframes:
            tf_regime_lines = []
            for symbol in ordered_symbols:
                regime_result = get_market_regime(db, symbol, tf, use_realtime=True, exchange=exchange)
                regime_text = _format_regime_text(symbol, tf, regime_result)
                market_regime_context[f"{symbol}_market_regime_{tf}"] = regime_text
                tf_regime_lines.append(f"- {regime_text}")
            market_regime_context[f"market_regime_{tf}"] = (
                "\n".join(tf_regime_lines) if tf_regime_lines else "N/A"
            )

        for symbol in ordered_symbols:
            market_regime_context[f"{symbol}_market_regime"] = market_regime_context.get(
                f"{symbol}_market_regime_5m",
                "N/A",
            )
        market_regime_context["market_regime"] = market_regime_context.get("market_regime_5m", "N/A")
        market_regime_context["trigger_market_regime"] = _build_trigger_market_regime(db, trigger_context)
    except Exception as err:
        logger.warning("Failed to get market regime data: %s", err)
        market_regime_context["market_regime"] = "N/A"
        market_regime_context["trigger_market_regime"] = "N/A"

    return market_regime_context


def _format_regime_text(symbol: str, tf: str, result: Dict[str, Any]) -> str:
    regime = result["regime"]
    direction = result["direction"]
    conf = result["confidence"]
    indicators = result.get("indicators", {})
    if not indicators:
        return f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | insufficient data"

    return (
        f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | "
        f"cvd_ratio={indicators.get('cvd_ratio', 0):.3f}, "
        f"oi_delta={indicators.get('oi_delta', 0):.3f}%, "
        f"taker={indicators.get('taker_ratio', 1):.2f}, "
        f"rsi={indicators.get('rsi', 50):.1f}"
    )


def _build_trigger_market_regime(
    db: Session,
    trigger_context: Optional[Dict[str, Any]],
) -> str:
    if not trigger_context or trigger_context.get("trigger_type") != "signal":
        return "N/A"

    signal_trigger_id = trigger_context.get("signal_trigger_id")
    if signal_trigger_id:
        return _load_trigger_market_regime(db, signal_trigger_id)

    trigger_symbol = trigger_context.get("trigger_symbol", "BTC")
    triggered_signals = trigger_context.get("triggered_signals", [])
    sample_tf = triggered_signals[0].get("time_window", "5m") if triggered_signals else "5m"
    return (
        f"[{trigger_symbol}/{sample_tf}] breakout (bullish) conf=0.65 | "
        f"cvd_ratio=0.286, oi_delta=0.857%, taker=1.80, rsi=50.7 | "
        f"(trigger snapshot - preview)"
    )


def _load_trigger_market_regime(db: Session, signal_trigger_id: Any) -> str:
    try:
        from sqlalchemy import text

        result = db.execute(
            text("SELECT market_regime FROM signal_trigger_logs WHERE id = :id"),
            {"id": signal_trigger_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return "N/A"

        regime_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        symbol = regime_data.get("symbol", "N/A")
        tf = regime_data.get("timeframe", "5m")
        regime = regime_data.get("regime", "unknown")
        direction = regime_data.get("direction", "neutral")
        conf = regime_data.get("confidence", 0)
        indicators = regime_data.get("indicators", {})

        if not indicators:
            return f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | (trigger snapshot)"

        return (
            f"[{symbol}/{tf}] {regime} ({direction}) conf={conf:.2f} | "
            f"cvd_ratio={indicators.get('cvd_ratio', 0):.3f}, "
            f"oi_delta={indicators.get('oi_delta', 0):.3f}%, "
            f"taker={indicators.get('taker_ratio', 1):.2f}, "
            f"rsi={indicators.get('rsi', 50):.1f} | (trigger snapshot)"
        )
    except Exception as err:
        logger.warning("Failed to get trigger market regime: %s", err)
        return "N/A"
