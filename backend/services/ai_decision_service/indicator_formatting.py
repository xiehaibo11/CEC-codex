"""Technical-indicator and market-flow value formatting for prompt injection."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _format_single_indicator(indicator_name: str, indicator_data: Any) -> str:
    """
    Format a single technical indicator for prompt injection.

    Args:
        indicator_name: Name of the indicator (e.g., 'RSI14', 'MACD')
        indicator_data: Calculated indicator data

    Returns:
        Formatted string for prompt
    """
    if not indicator_data:
        return "N/A (Insufficient data for calculation)"

    try:
        if indicator_name.startswith('RSI'):
            # RSI format: value + interpretation + last 5 values
            values = indicator_data if isinstance(indicator_data, list) else []
            if not values:
                return "N/A"

            current = values[-1]
            last_5 = values[-5:] if len(values) >= 5 else values

            # Interpret RSI value
            if current > 70:
                interpretation = "Overbought"
            elif current < 30:
                interpretation = "Oversold"
            else:
                interpretation = "Neutral"

            result = [
                f"{indicator_name}: {current:.2f} ({interpretation})",
                f"{indicator_name} last 5: {', '.join(f'{v:.2f}' for v in last_5)}"
            ]
            return "\n".join(result)

        elif indicator_name == 'MACD':
            # MACD format: MACD line, Signal line, Histogram + interpretation
            macd_line = indicator_data.get('macd', [])
            signal_line = indicator_data.get('signal', [])
            histogram = indicator_data.get('histogram', [])

            if not macd_line or not signal_line or not histogram:
                return "N/A"

            current_macd = macd_line[-1]
            current_signal = signal_line[-1]
            current_hist = histogram[-1]
            last_5_hist = histogram[-5:] if len(histogram) >= 5 else histogram

            # Interpret MACD
            momentum = "Bullish momentum" if current_hist > 0 else "Bearish momentum"

            result = [
                f"MACD Line: {current_macd:.4f}",
                f"Signal Line: {current_signal:.4f}",
                f"Histogram: {current_hist:.4f} ({momentum})",
                f"Histogram last 5: {', '.join(f'{v:.4f}' for v in last_5_hist)}"
            ]
            return "\n".join(result)

        elif indicator_name.startswith('MA') or indicator_name.startswith('EMA'):
            # Moving average format: current value + last 5 values
            values = indicator_data if isinstance(indicator_data, list) else []
            if not values:
                return "N/A"

            current = values[-1]
            last_5 = values[-5:] if len(values) >= 5 else values

            result = [
                f"{indicator_name}: {current:.2f}",
                f"{indicator_name} last 5: {', '.join(f'{v:.2f}' for v in last_5)}"
            ]
            return "\n".join(result)

        elif indicator_name == 'BOLL':
            # Bollinger Bands format: Upper, Middle, Lower bands
            upper = indicator_data.get('upper', [])
            middle = indicator_data.get('middle', [])
            lower = indicator_data.get('lower', [])

            if not upper or not middle or not lower:
                return "N/A"

            result = [
                f"Upper Band: {upper[-1]:.2f}",
                f"Middle Band: {middle[-1]:.2f}",
                f"Lower Band: {lower[-1]:.2f}",
                f"Band Width: {(upper[-1] - lower[-1]):.2f}"
            ]
            return "\n".join(result)

        elif indicator_name.startswith('ATR'):
            # ATR format: current value + interpretation
            values = indicator_data if isinstance(indicator_data, list) else []
            if not values:
                return "N/A"

            current = values[-1]
            avg_atr = sum(values[-20:]) / min(len(values), 20) if values else 0

            volatility = "High volatility" if current > avg_atr * 1.2 else "Normal volatility"

            result = [
                f"{indicator_name}: {current:.2f} ({volatility})",
                f"20-period average: {avg_atr:.2f}"
            ]
            return "\n".join(result)

        elif indicator_name == 'STOCH':
            # Stochastic Oscillator format: %K and %D lines + interpretation
            k_line = indicator_data.get('k', [])
            d_line = indicator_data.get('d', [])

            if not k_line or not d_line:
                return "N/A"

            current_k = k_line[-1]
            current_d = d_line[-1]
            last_5_k = k_line[-5:] if len(k_line) >= 5 else k_line

            # Interpret Stochastic
            if current_k > 80:
                interpretation = "Overbought"
            elif current_k < 20:
                interpretation = "Oversold"
            else:
                interpretation = "Neutral"

            result = [
                f"%K Line: {current_k:.2f} ({interpretation})",
                f"%D Line: {current_d:.2f}",
                f"%K last 5: {', '.join(f'{v:.2f}' for v in last_5_k)}"
            ]
            return "\n".join(result)

        elif indicator_name == 'VWAP':
            # VWAP format: current value + comparison with price
            values = indicator_data if isinstance(indicator_data, list) else []
            if not values:
                return "N/A"

            current = values[-1]
            last_5 = values[-5:] if len(values) >= 5 else values

            result = [
                f"VWAP: {current:.2f}",
                f"VWAP last 5: {', '.join(f'{v:.2f}' for v in last_5)}",
                f"Note: Price above VWAP suggests bullish sentiment, below suggests bearish"
            ]
            return "\n".join(result)

        elif indicator_name == 'OBV':
            # OBV format: current value + trend
            values = indicator_data if isinstance(indicator_data, list) else []
            if not values:
                return "N/A"

            current = values[-1]
            last_5 = values[-5:] if len(values) >= 5 else values

            # Determine trend
            if len(values) >= 2:
                trend = "Rising" if current > values[-2] else "Falling"
            else:
                trend = "N/A"

            result = [
                f"OBV: {current:.0f} ({trend})",
                f"OBV last 5: {', '.join(f'{v:.0f}' for v in last_5)}"
            ]
            return "\n".join(result)

        else:
            return "N/A"

    except Exception as e:
        logger.error(f"Error formatting indicator {indicator_name}: {e}")
        return "N/A"


def _format_flow_indicator(indicator_name: str, indicator_data: Any, symbol: str = "", period: str = "", exchange: str = "") -> str:
    """
    Format a market flow indicator for prompt injection.

    Args:
        indicator_name: Name of the flow indicator (e.g., 'CVD', 'TAKER', 'OI')
        indicator_data: Calculated flow indicator data dict

    Returns:
        Formatted string for prompt (objective data only, no interpretations)
    """
    if not indicator_data:
        if symbol and period and exchange:
            return f"N/A ({symbol} {indicator_name} on {exchange}: insufficient data for {period} calculation. Symbol may need more time after being added to watchlist.)"
        return "N/A (Insufficient data for calculation)"

    try:
        period = indicator_data.get("period", "")

        if indicator_name == "CVD":
            current = indicator_data.get("current", 0)
            last_5 = indicator_data.get("last_5", [])
            cumulative = indicator_data.get("cumulative", 0)

            result = [
                f"CVD ({period}): {_format_usd(current)}",
                f"CVD last 5: {', '.join(_format_usd(v) for v in last_5)}",
                f"Cumulative: {_format_usd(cumulative)}"
            ]
            return "\n".join(result)

        elif indicator_name == "TAKER":
            import math
            buy = indicator_data.get("buy", 0)
            sell = indicator_data.get("sell", 0)
            ratio = indicator_data.get("ratio", 1.0)
            ratio_last_5 = indicator_data.get("ratio_last_5", [])
            volume_last_5 = indicator_data.get("volume_last_5", [])

            # Calculate log ratio: positive = buyers dominate, negative = sellers dominate
            log_ratio = math.log(ratio) if ratio > 0 else 0

            result = [
                f"Taker Buy: {_format_usd(buy)} | Taker Sell: {_format_usd(sell)}",
                f"Buy/Sell Ratio: {ratio:.2f}x (log: {log_ratio:+.2f})",
                f"Ratio last 5: {', '.join(f'{r:.2f}x' for r in ratio_last_5)}",
                f"Volume last 5: {', '.join(_format_usd(v) for v in volume_last_5)}"
            ]
            return "\n".join(result)

        elif indicator_name == "OI":
            current = indicator_data.get("current", 0)
            last_5 = indicator_data.get("last_5", [])
            is_stale = indicator_data.get("stale", False)
            age_minutes = indicator_data.get("age_minutes", 0)

            result = [f"Open Interest: {_format_usd(current)}"]
            if is_stale and age_minutes > 0:
                result[0] += f" (data from {age_minutes}min ago)"
            result.append(f"OI last 5: {', '.join(_format_usd(v) for v in last_5)}")
            return "\n".join(result)

        elif indicator_name == "OI_DELTA":
            current = indicator_data.get("current", 0)
            last_5 = indicator_data.get("last_5", [])
            is_stale = indicator_data.get("stale", False)
            expanded_window = indicator_data.get("expanded_window", 0)

            result = [f"OI Delta ({period}): {current:+.2f}%"]
            if is_stale and expanded_window > 0:
                result[0] += f" (expanded {expanded_window}x window)"
            result.append(f"OI Delta last 5: {', '.join(f'{c:+.2f}%' for c in last_5)}")
            return "\n".join(result)

        elif indicator_name == "FUNDING":
            # Values are in K-line display unit (raw × 1000000)
            # current_pct is the actual percentage
            current = indicator_data.get("current", 0)
            current_pct = indicator_data.get("current_pct", current / 10000)
            change = indicator_data.get("change", 0)
            change_pct = indicator_data.get("change_pct", change / 10000)
            last_5 = indicator_data.get("last_5", [])
            annualized = indicator_data.get("annualized", 0)

            # Format change with sign
            change_sign = "+" if change >= 0 else ""

            result = [
                f"Funding Rate: {current:.1f} ({current_pct:.4f}%)",
                f"Funding Change: {change_sign}{change:.1f} ({change_sign}{change_pct:.4f}%)",
                f"Annualized: {annualized:.2f}%",
                f"Funding last 5: {', '.join(f'{f:.1f}' for f in last_5)}"
            ]
            return "\n".join(result)

        elif indicator_name == "DEPTH":
            bid = indicator_data.get("bid", 0)
            ask = indicator_data.get("ask", 0)
            ratio = indicator_data.get("ratio", 1.0)
            ratio_last_5 = indicator_data.get("ratio_last_5", [])
            spread = indicator_data.get("spread")

            result = [
                f"Bid Depth: {_format_usd(bid)} | Ask Depth: {_format_usd(ask)}",
                f"Depth Ratio (Bid/Ask): {ratio:.2f}",
                f"Ratio last 5: {', '.join(f'{r:.2f}' for r in ratio_last_5)}"
            ]
            if spread is not None:
                result.append(f"Spread: {spread:.4f}")
            return "\n".join(result)

        elif indicator_name == "IMBALANCE":
            current = indicator_data.get("current", 0)
            last_5 = indicator_data.get("last_5", [])

            result = [
                f"Order Imbalance: {current:+.3f}",
                f"Imbalance last 5: {', '.join(f'{v:+.3f}' for v in last_5)}"
            ]
            return "\n".join(result)

        elif indicator_name == "PRICE_CHANGE":
            current = indicator_data.get("current", 0)
            start_price = indicator_data.get("start_price")
            end_price = indicator_data.get("end_price")
            last_5 = indicator_data.get("last_5", [])

            # Calculate USD change value
            if start_price and end_price:
                change_usd = end_price - start_price
                usd_str = _format_price_value(change_usd, reference_price=end_price, with_sign=True)
                result = [f"Price Change: {current:+.3f}% ({usd_str})"]
                result.append(f"Price: {_format_price_value(start_price)} -> {_format_price_value(end_price)}")
            else:
                result = [f"Price Change: {current:+.3f}%"]
            if last_5:
                result.append(f"Change last 5: {', '.join(f'{v:+.3f}%' for v in last_5)}")
            return "\n".join(result)

        elif indicator_name == "VOLATILITY":
            current = indicator_data.get("current", 0)
            high = indicator_data.get("high")
            low = indicator_data.get("low")
            last_5 = indicator_data.get("last_5", [])

            # Calculate USD range value
            if high and low:
                range_usd = high - low
                usd_str = _format_price_value(range_usd, reference_price=high, with_sign=False)
                result = [f"Volatility: {current:.3f}% ({usd_str})"]
                result.append(f"Range: {_format_price_value(low)} - {_format_price_value(high)}")
            else:
                result = [f"Volatility: {current:.3f}%"]
            if last_5:
                result.append(f"Volatility last 5: {', '.join(f'{v:.3f}%' for v in last_5)}")
            return "\n".join(result)

        else:
            return "N/A"

    except Exception as e:
        logger.error(f"Error formatting flow indicator {indicator_name}: {e}")
        return "N/A"


def _format_usd(value: float) -> str:
    """Format USD value with appropriate unit (K, M, B)"""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    sign = "+" if value >= 0 else "-"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val/1_000_000_000:.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.2f}M"
    elif abs_val >= 1_000:
        return f"{sign}${abs_val/1_000:.2f}K"
    else:
        return f"{sign}${abs_val:.2f}"


def _format_price_value(value: float, reference_price: float = None, with_sign: bool = False) -> str:
    """
    Format price value with adaptive decimal places based on price magnitude.

    Args:
        value: The price value to format
        reference_price: Reference price to determine decimal places (uses value if None)
        with_sign: Whether to include +/- sign prefix

    Returns:
        Formatted price string like "$94,521.00" or "$+2,156.00"
    """
    if value is None:
        return "N/A"

    ref = reference_price if reference_price is not None else abs(value)
    abs_val = abs(value)

    # Determine decimal places based on reference price magnitude
    if ref >= 1000:
        decimals = 2
    elif ref >= 1:
        decimals = 4
    elif ref >= 0.01:
        decimals = 6
    else:
        decimals = 8

    # Format with thousand separators
    formatted = f"{abs_val:,.{decimals}f}"

    if with_sign:
        sign = "+" if value >= 0 else "-"
        return f"${sign}{formatted}"
    else:
        return f"${formatted}"
