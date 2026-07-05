"""Constants for the 5-minute event-contract engine."""

from __future__ import annotations

DEFAULT_API_KEYS = {
    "",
    "default",
    "default-key-please-update-in-settings",
    None,
}

MAIN_LOGIC_REVIEWER_NAME = "Main Logic"
DEFAULT_REVIEWER_PANEL_SIZE = 25
DEFAULT_CONSENSUS_THRESHOLD = 5
MAX_REVIEWER_PANEL_SIZE = 1 + 30

EVENT_AI_NAMES = [
    "Trend Micro AI",
    "Trend Structure AI",
    "Momentum AI",
    "Volume AI",
    "Volatility AI",
    "Kline Pattern AI",
    "Wick Rejection AI",
    "Breakout AI",
    "Fake Breakout AI",
    "Pullback AI",
    "Range AI",
    "Trap Detection AI",
    "Bull Trap AI",
    "Bear Trap AI",
    "Liquidity Sweep AI",
    "Stop Hunt AI",
    "Orderbook AI",
    "Spread AI",
    "CVD AI",
    "Taker Ratio AI",
    "Open Interest AI",
    "Funding Rate AI",
    "Liquidation AI",
    "Support Resistance AI",
    "VWAP AI",
    "Multi Timeframe AI",
    "Market Regime AI",
    "Noise Filter AI",
    "Entry Timing AI",
    "Final Risk AI",
]

EVENT_RULE_AGENT_NAMES = [name.replace(" AI", " Rule Agent") for name in EVENT_AI_NAMES]

CRITICAL_REVIEWER_PREFIXES = {
    "Fake Breakout",
    "Trap Detection",
    "Market Regime",
    "Final Risk",
}

CONSENSUS_MODES = {"rule_only", "ai_confirmed"}

PERIOD_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
}

# v3: records unclamped edge_score_raw alongside the gated edge_score;
# validation monotonicity ranks by the raw score. Gating behavior unchanged.
# v4: execution-cost floors enforced (fee/slippage/impact/delay); local
# market-flow features (real taker CVD replaces the OHLCV proxy, OI/funding
# feed the reversal-evidence score); exhaustion_reversal + evidence score
# recorded per trade for attribution.
# v5: MA-cross triple confirmation (sharp angle / persistence / slope
# acceleration) feeds edge scoring, whipsaw crosses add risk; kline sanitize
# drops null-field bars and flags (never drops) extreme single-bar moves.
# v6: indicator suite from real OHLCV+volume - MACD(12,26,9) cross, Bollinger
# %B + band walk, RSI divergence, OBV/MA cross, W/M double pattern with
# neckline confirmation; divergence/OBV/pattern combine into
# indicator_reversal_score which widens the exhaustion gate additively
# (same corroborate-never-cancel rule as CoinGlass evidence).
ENGINE_VERSION = "event-contract-v6"


def is_critical_reviewer_name(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in CRITICAL_REVIEWER_PREFIXES)


def event_ai_names_for_panel(panel_size: int) -> list[str]:
    ai_slots = max(0, min(int(panel_size) - 1, len(EVENT_AI_NAMES)))
    if ai_slots >= len(EVENT_AI_NAMES):
        return list(EVENT_AI_NAMES)

    selected = list(EVENT_AI_NAMES[:ai_slots])
    for name in EVENT_AI_NAMES:
        if not is_critical_reviewer_name(name) or name in selected:
            continue
        for idx in range(len(selected) - 1, -1, -1):
            if not is_critical_reviewer_name(selected[idx]):
                selected[idx] = name
                break

    selected_names = set(selected)
    return [name for name in EVENT_AI_NAMES if name in selected_names][:ai_slots]


def reviewer_names_for_panel(panel_size: int) -> list[str]:
    return [MAIN_LOGIC_REVIEWER_NAME, *event_ai_names_for_panel(panel_size)]
