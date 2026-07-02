"""Venue presets for event-contract economics.

Sources (2026-07): HIBT support docs (payout 0.80, no fee, min 3 USDT,
per-minute open cap, settles on venue index mark price); Binance Event
Contracts FAQ (fixed payout ~0.80, draw refunds premium, min 5 USDT,
10k USDT daily loss cap, no extra fee).
"""
from __future__ import annotations

from typing import Any, Dict

PLATFORM_PRESETS: Dict[str, Dict[str, Any]] = {
    "hibt": {
        "win_payout_ratio": 0.8,
        "fee_rate": 0.0,
        "draw_result": "loss",
        "min_stake": 3.0,
        "min_seconds_between_trades": 60,
        "daily_loss_cap": None,
    },
    "binance_event": {
        "win_payout_ratio": 0.8,
        "fee_rate": 0.0,
        "draw_result": "refund",
        "min_stake": 5.0,
        "min_seconds_between_trades": 0,
        "daily_loss_cap": 10000.0,
    },
    "custom": {
        "min_stake": 1.0,
        "min_seconds_between_trades": 0,
        "daily_loss_cap": None,
    },
}

# Keys a preset may fill only when the user did not set them explicitly.
_SOFT_KEYS = ("win_payout_ratio", "fee_rate", "draw_result")
# Keys the platform always dictates.
_HARD_KEYS = ("min_stake", "min_seconds_between_trades", "daily_loss_cap")


def apply_platform_preset(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge platform rules into a raw request config (pre-normalization)."""
    platform = str(config.get("platform") or "custom").lower()
    preset = PLATFORM_PRESETS.get(platform)
    if preset is None:
        raise ValueError(f"Unsupported platform: {platform}")
    merged = dict(config)
    merged["platform"] = platform
    for key in _SOFT_KEYS:
        if key in preset and merged.get(key) is None:
            merged[key] = preset[key]
    for key in _HARD_KEYS:
        merged[key] = preset.get(key, PLATFORM_PRESETS["custom"][key])
    return merged
