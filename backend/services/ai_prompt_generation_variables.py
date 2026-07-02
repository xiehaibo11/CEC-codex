"""
Variable validation helpers for AI prompt generation.
"""
import re
from typing import List

# Base variable patterns that are always valid
VALID_VARIABLE_PATTERNS = [
    # Account/Position variables
    r"total_equity",
    r"available_balance",
    r"margin_usage_percent",
    r"maintenance_margin",
    r"positions_detail",
    r"recent_trades_summary",
    r"open_orders_detail",
    # Context variables
    r"runtime_minutes",
    r"current_time_utc",
    r"trading_environment",
    r"selected_symbols_detail",
    r"trigger_context",
    r"news_section",
    r"output_format",
    # Market regime
    r"market_regime_description",
    r"trigger_market_regime",
    r"market_regime(?:_(?:1m|5m|15m|1h|4h|1d))?",
    # Symbol-specific patterns (BTC, ETH, SOL, etc.)
    r"[A-Z]+_market_data",
    r"[A-Z]+_klines_(?:1m|3m|5m|15m|30m|1h|2h|4h|8h|12h|1d|3d|1w|1M)",
    r"[A-Z]+_market_regime(?:_(?:1m|5m|15m|1h|4h|1d))?",
    # Technical indicators
    r"[A-Z]+_(?:MA|EMA|RSI14|RSI7|MACD|BOLL|ATR14|VWAP|OBV|STOCH)_(?:1m|3m|5m|15m|30m|1h|2h|4h|8h|12h|1d)",
    # Flow indicators
    r"[A-Z]+_(?:CVD|OI|OI_DELTA|TAKER|FUNDING|DEPTH|IMBALANCE|PRICE_CHANGE|VOLATILITY)_(?:1m|3m|5m|15m|30m|1h|2h|4h|8h|12h|1d)",
    # Factor variables: preferred {SYMBOL_factor_PERIOD_NAME}, legacy {SYMBOL_factor_NAME}
    r"[A-Z][A-Z0-9]*_factor_(?:1m|5m|15m|1h|4h|1d)_[A-Za-z][A-Za-z0-9_]*",
    r"[A-Z][A-Z0-9]*_factor_[A-Za-z][A-Za-z0-9_]*",
]


def _validate_variable(var_name: str) -> bool:
    """Check if a variable name matches any valid pattern."""
    for pattern in VALID_VARIABLE_PATTERNS:
        if re.fullmatch(pattern, var_name):
            return True
    return False


def _extract_variables_from_text(text: str) -> List[str]:
    """Extract all {variable} placeholders from text."""
    # Match {variable_name} but not {{escaped}}
    pattern = r"\{([^{}]+)\}"
    matches = re.findall(pattern, text)
    # Filter out things that look like JSON or format strings
    variables = []
    for m in matches:
        # Skip if it looks like JSON key or has special chars
        if ":" in m or '"' in m or "'" in m:
            continue
        # Skip if it's a number (like array index)
        if m.isdigit():
            continue
        # Handle klines with count: {BTC_klines_1h}(100) -> BTC_klines_1h
        clean_var = m.split("}")[0].split("(")[0].strip()
        if clean_var:
            variables.append(clean_var)
    return list(set(variables))


# Account-related variables that need AI Trader binding (will show placeholders)
ACCOUNT_VARIABLES = {
    "total_equity",
    "available_balance",
    "margin_usage_percent",
    "maintenance_margin",
    "positions_detail",
    "recent_trades_summary",
    "open_orders_detail",
    "runtime_minutes",
    "trading_environment",
    "trigger_context",
    "trigger_market_regime",
}
