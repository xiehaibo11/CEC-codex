"""Hard production-policy defaults for the customer event-contract trader."""

from __future__ import annotations

from typing import Any, Dict

ALLOWED_PRODUCTION_EXPIRIES = frozenset({5, 10})
ALLOWED_EXECUTION_MODES = frozenset({"paper", "live"})
PRODUCTION_SIGNAL_MODE = "trend_follow"
PRODUCTION_BASE_PERIOD = "1m"

DEFAULT_PRODUCTION_CONFIG: Dict[str, Any] = {
    "expiry_minutes": 5,
    "period": PRODUCTION_BASE_PERIOD,
    "signal_mode": PRODUCTION_SIGNAL_MODE,
    "execution_mode": "paper",
    "leverage": 10,
    "trade_margin": 100.0,
    "max_daily_trades": 10,
    "profit_target_multiplier": 2.0,
    "non_overlapping_only": True,
    "professional_ai_enabled": True,
    "professional_ai_min_confidence": 75.0,
}


def normalize_production_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    """Apply immutable customer-production defaults and reject unsafe variants.

    Historical backtest configs are intentionally not passed through this
    helper: their stored summaries remain reproducible. This policy is for new
    production Paper/Live trader requests and their runtime cycle.
    """
    normalized = dict(DEFAULT_PRODUCTION_CONFIG)
    normalized.update(dict(config or {}))

    try:
        expiry_minutes = int(normalized["expiry_minutes"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Production event-contract expiry must be 5 or 10 minutes") from exc
    if expiry_minutes not in ALLOWED_PRODUCTION_EXPIRIES:
        raise ValueError("Production event-contract expiry must be 5 or 10 minutes")
    normalized["expiry_minutes"] = expiry_minutes

    signal_mode = str(normalized.get("signal_mode") or PRODUCTION_SIGNAL_MODE).strip().lower()
    if signal_mode != PRODUCTION_SIGNAL_MODE:
        raise ValueError("Production event-contract strategy only supports trend_follow")
    normalized["signal_mode"] = PRODUCTION_SIGNAL_MODE

    period = str(normalized.get("period") or PRODUCTION_BASE_PERIOD).strip().lower()
    if period != PRODUCTION_BASE_PERIOD:
        raise ValueError("Production event-contract analysis requires a 1m base K-line period")
    normalized["period"] = PRODUCTION_BASE_PERIOD

    execution_mode = str(normalized.get("execution_mode") or "paper").strip().lower()
    if execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError(
            "Live event-contract adapter selection requires execution_mode=paper or execution_mode=live"
        )
    normalized["execution_mode"] = execution_mode

    # These are policy fields, not model suggestions. Any AI-provided override
    # is discarded before the config reaches execution.
    normalized["non_overlapping_only"] = True
    normalized["leverage"] = 10
    normalized["max_daily_trades"] = 10
    normalized["profit_target_multiplier"] = 2.0
    normalized["professional_ai_enabled"] = True
    normalized["professional_ai_min_confidence"] = min(
        max(float(normalized.get("professional_ai_min_confidence") or 75.0), 0.0), 100.0
    )
    normalized["trade_margin"] = float(normalized.get("trade_margin") or 100.0)
    if normalized["trade_margin"] <= 0:
        raise ValueError("Production event-contract trade_margin must be positive")

    return normalized
