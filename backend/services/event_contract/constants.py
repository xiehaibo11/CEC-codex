"""Constants for the 5-minute event-contract engine."""

from __future__ import annotations

DEFAULT_API_KEYS = {
    "",
    "default",
    "default-key-please-update-in-settings",
    None,
}

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

ENGINE_VERSION = "event-contract-v2"
