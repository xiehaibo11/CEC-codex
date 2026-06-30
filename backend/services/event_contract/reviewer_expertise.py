"""Quant-team domain knowledge for the 30 event-contract reviewers.

Each reviewer is a specialist with a clear discipline. The data here is the
"team handbook": role, focus, decision triggers, primary features, and a base
weight (later adjusted by reviewer_learning from realized trade outcomes).

The schema is intentionally small so all 30 entries stay readable in one file.
LLM prompts and rule decisions both import from REVIEWER_EXPERTISE.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


# Each entry covers:
#   role:           one-line title (used in prompt injection)
#   focus:          what data this reviewer actually looks at
#   long_setup:     concrete conditions that justify a long vote
#   short_setup:    concrete conditions that justify a short vote
#   hold_setup:     conditions that should produce a hold vote (defaults imply hold)
#   risk_flags:     canonical flag strings this reviewer is expected to emit
#   primary_factors:feature-dict keys that drive this reviewer's call
#   weight_base:    starting vote weight before learning (1.0 = neutral)
REVIEWER_EXPERTISE: Dict[str, Dict[str, Any]] = {
    "Trend Micro AI": {
        "role": "Micro-trend specialist",
        "focus": "1-3 minute EMA structure and tick-level momentum",
        "long_setup": "Fast EMA above slow EMA with ret3 > +0.04% and rising volume",
        "short_setup": "Fast EMA below slow EMA with ret3 < -0.04% and rising volume",
        "hold_setup": "EMAs interleaved, |trend_score| < 0.02, or multi-timeframe conflict",
        "risk_flags": ["trend_weakness", "mtf_conflict"],
        "primary_factors": ["ema_diff_pct", "ret1", "ret3", "trend_score"],
        "weight_base": 1.0,
    },
    "Trend Structure AI": {
        "role": "Swing structure analyst",
        "focus": "Higher-highs/lower-lows, distance to support/resistance",
        "long_setup": "Higher-high confirmed, range_pos > 0.65, support_distance < 1.5x ATR",
        "short_setup": "Lower-low confirmed, range_pos < 0.35, resistance < 1.5x ATR",
        "hold_setup": "Mid-range with no breakout (range_pos 0.4-0.6)",
        "risk_flags": ["broken_structure", "range_middle"],
        "primary_factors": ["range_pos", "support", "resistance", "range_width_pct"],
        "weight_base": 1.0,
    },
    "Momentum AI": {
        "role": "Multi-window momentum reader",
        "focus": "ret3/ret5/ret15 alignment and acceleration",
        "long_setup": "ret3 > 0.05% AND ret5 > ret3 (accelerating up)",
        "short_setup": "ret3 < -0.05% AND ret5 < ret3 (accelerating down)",
        "hold_setup": "Cross-window disagreement or decelerating moves",
        "risk_flags": ["momentum_fade", "decel_warning"],
        "primary_factors": ["ret3", "ret5", "ret15", "trend_score"],
        "weight_base": 1.0,
    },
    "Volume AI": {
        "role": "Volume confirmation expert",
        "focus": "Volume spikes vs 30-bar baseline, sustainable thrust",
        "long_setup": "volume_ratio > 1.4 with positive trend (buying climax)",
        "short_setup": "volume_ratio > 1.4 with negative trend (selling climax)",
        "hold_setup": "volume_ratio < 1.1 (no commitment)",
        "risk_flags": ["weak_thrust", "exhaustion_volume"],
        "primary_factors": ["volume_ratio", "trend_score"],
        "weight_base": 1.0,
    },
    "Volatility AI": {
        "role": "Volatility regime classifier",
        "focus": "ATR%, range expansion vs contraction",
        "long_setup": "Range expansion up after compression (vol breakout long)",
        "short_setup": "Range expansion down after compression",
        "hold_setup": "ATR < median (compressed - wait for break)",
        "risk_flags": ["low_volatility", "spike_exhaustion"],
        "primary_factors": ["atr_pct", "range_width_pct"],
        "weight_base": 0.9,
    },
    "Kline Pattern AI": {
        "role": "Candlestick pattern reader",
        "focus": "Engulfing, pin bars, body/wick ratios on entry candle",
        "long_setup": "Bullish engulfing or hammer (lower_wick_ratio > 0.5, body > 0.3)",
        "short_setup": "Bearish engulfing or shooting star (upper_wick_ratio > 0.5)",
        "hold_setup": "Doji or indecision body (body_ratio < 0.25)",
        "risk_flags": ["indecision_candle", "rejection_pattern"],
        "primary_factors": ["body_ratio", "upper_wick_ratio", "lower_wick_ratio"],
        "weight_base": 0.9,
    },
    "Wick Rejection AI": {
        "role": "Liquidity wick interpreter",
        "focus": "Long wicks signaling absorbed orders at extremes",
        "long_setup": "lower_wick_ratio > 0.45 at range_pos < 0.3 (bid absorbed sells)",
        "short_setup": "upper_wick_ratio > 0.45 at range_pos > 0.7 (ask absorbed buys)",
        "hold_setup": "Neither wick > 0.3 (no clear absorption)",
        "risk_flags": ["wick_at_resistance", "wick_at_support"],
        "primary_factors": ["upper_wick_ratio", "lower_wick_ratio", "range_pos"],
        "weight_base": 0.9,
    },
    "Breakout AI": {
        "role": "Breakout confirmation analyst",
        "focus": "Clean breaks of recent support/resistance with volume",
        "long_setup": "close > resistance AND volume_ratio > 1.2 (real breakout up)",
        "short_setup": "close < support AND volume_ratio > 1.2 (real breakout down)",
        "hold_setup": "No fresh break or weak volume",
        "risk_flags": ["weak_volume_breakout", "false_breakout_zone"],
        "primary_factors": ["breakout_up", "breakout_down", "volume_ratio"],
        "weight_base": 1.0,
    },
    "Fake Breakout AI": {
        "role": "False breakout detector (CRITICAL gate)",
        "focus": "Wick-only breaks that quickly return inside the range",
        "long_setup": "RARELY long — only if fake_breakout_risk < 25 with momentum",
        "short_setup": "RARELY short — fade upside fakeouts with upper_wick rejection",
        "hold_setup": "fake_breakout_risk > 40 → must hold (gatekeeper duty)",
        "risk_flags": ["fakeout_upside", "fakeout_downside", "trapped_breakout"],
        "primary_factors": ["fake_breakout_risk", "upper_wick_ratio", "lower_wick_ratio"],
        "weight_base": 1.2,
    },
    "Pullback AI": {
        "role": "Pullback continuation trader",
        "focus": "Healthy retracements in trending markets",
        "long_setup": "Uptrend with 38-62% retrace, holding above VWAP",
        "short_setup": "Downtrend with 38-62% retrace, holding below VWAP",
        "hold_setup": "Retrace too deep (>62%) or against trend",
        "risk_flags": ["retrace_too_deep", "vwap_loss"],
        "primary_factors": ["vwap", "trend_score", "range_pos"],
        "weight_base": 0.95,
    },
    "Range AI": {
        "role": "Range-bound mean-reversion expert",
        "focus": "Sideways markets, fade extremes within a clean range",
        "long_setup": "In confirmed range, range_pos < 0.25, oversold bounce expected",
        "short_setup": "In confirmed range, range_pos > 0.75, overbought fade expected",
        "hold_setup": "range_pos 0.3-0.7 (no edge) or range broken",
        "risk_flags": ["range_break", "range_middle"],
        "primary_factors": ["range_pos", "range_risk", "range_width_pct"],
        "weight_base": 0.95,
    },
    "Trap Detection AI": {
        "role": "Trap pattern hunter (CRITICAL gate)",
        "focus": "Bull/bear traps where late entrants get reversed",
        "long_setup": "RARELY — only when bear trap setup confirms reversal up",
        "short_setup": "RARELY — only when bull trap setup confirms reversal down",
        "hold_setup": "trap_risk > 40 → block trade (gatekeeper duty)",
        "risk_flags": ["bull_trap_high", "bear_trap_high"],
        "primary_factors": ["trap_risk", "bull_trap_risk", "bear_trap_risk"],
        "weight_base": 1.2,
    },
    "Bull Trap AI": {
        "role": "Bull trap specialist",
        "focus": "Upper-wick rejection at range top with overbought RSI",
        "long_setup": "Almost never — only if bull_trap_risk < 20",
        "short_setup": "Upper-wick > 0.4 + RSI > 68 + range_pos > 0.82",
        "hold_setup": "Setup forming but not confirmed",
        "risk_flags": ["bull_trap_confirmed", "upper_wick_rejection"],
        "primary_factors": ["bull_trap_risk", "rsi", "upper_wick_ratio", "range_pos"],
        "weight_base": 1.0,
    },
    "Bear Trap AI": {
        "role": "Bear trap specialist",
        "focus": "Lower-wick absorption at range bottom with oversold RSI",
        "long_setup": "Lower-wick > 0.4 + RSI < 32 + range_pos < 0.18",
        "short_setup": "Almost never — only if bear_trap_risk < 20",
        "hold_setup": "Setup forming but not confirmed",
        "risk_flags": ["bear_trap_confirmed", "lower_wick_rejection"],
        "primary_factors": ["bear_trap_risk", "rsi", "lower_wick_ratio", "range_pos"],
        "weight_base": 1.0,
    },
    "Liquidity Sweep AI": {
        "role": "Stop-run / liquidity sweep reader",
        "focus": "Quick spikes that take prior swing highs/lows then revert",
        "long_setup": "Sweep below prior low + immediate reclaim (long after sweep)",
        "short_setup": "Sweep above prior high + immediate rejection",
        "hold_setup": "No sweep or sweep without reclaim",
        "risk_flags": ["sweep_no_reclaim", "stop_run_target"],
        "primary_factors": ["upper_wick_ratio", "lower_wick_ratio", "range_pos"],
        "weight_base": 0.95,
    },
    "Stop Hunt AI": {
        "role": "Stop-hunt zone identifier",
        "focus": "Common stop clusters (round numbers, recent swing tops/bottoms)",
        "long_setup": "Price below cluster of long stops that was just swept",
        "short_setup": "Price above cluster of short stops that was just swept",
        "hold_setup": "Approaching but not yet through stop cluster",
        "risk_flags": ["stops_below", "stops_above"],
        "primary_factors": ["range_pos", "support", "resistance"],
        "weight_base": 0.9,
    },
    "Orderbook AI": {
        "role": "Level-2 orderbook imbalance reader",
        "focus": "Bid/ask depth imbalance within top 10 levels",
        "long_setup": "orderbook_imbalance > +0.3 (bids dominate near-touch)",
        "short_setup": "orderbook_imbalance < -0.3 (asks dominate)",
        "hold_setup": "Imbalance ±0.15 (balanced book)",
        "risk_flags": ["thin_book", "imbalance_flip"],
        "primary_factors": ["orderbook_imbalance", "depth_ratio"],
        "weight_base": 0.9,
    },
    "Spread AI": {
        "role": "Spread / liquidity quality monitor",
        "focus": "Bid-ask spread in basis points vs venue norm",
        "long_setup": "Tight spread (< 2 bps for BTC) + directional bid pressure",
        "short_setup": "Tight spread + directional ask pressure",
        "hold_setup": "Spread > 5 bps (poor liquidity)",
        "risk_flags": ["wide_spread", "thin_liquidity"],
        "primary_factors": ["spread_bps", "depth_ratio"],
        "weight_base": 0.85,
    },
    "CVD AI": {
        "role": "Cumulative volume delta analyst",
        "focus": "Net buying vs selling pressure (signed volume)",
        "long_setup": "cvd_proxy > +0.15 with rising price (buyers in control)",
        "short_setup": "cvd_proxy < -0.15 with falling price",
        "hold_setup": "Divergence (price up + CVD down → fade) — emit hold or fade",
        "risk_flags": ["cvd_divergence", "cvd_neutral"],
        "primary_factors": ["cvd_proxy", "taker_delta", "trend_score"],
        "weight_base": 1.0,
    },
    "Taker Ratio AI": {
        "role": "Aggressive taker flow expert",
        "focus": "Taker buy vs sell volume ratio",
        "long_setup": "taker_buy_sell_ratio > 1.4 (aggressive buyers)",
        "short_setup": "taker_buy_sell_ratio < 0.7 (aggressive sellers)",
        "hold_setup": "Ratio between 0.85-1.15",
        "risk_flags": ["taker_extreme", "ratio_flip"],
        "primary_factors": ["taker_buy_sell_ratio", "taker_delta"],
        "weight_base": 0.95,
    },
    "Open Interest AI": {
        "role": "Open interest dynamics expert (perp futures)",
        "focus": "OI changes vs price direction",
        "long_setup": "OI rising + price rising (fresh longs adding)",
        "short_setup": "OI rising + price falling (fresh shorts adding)",
        "hold_setup": "OI falling (position unwinding, low conviction)",
        "risk_flags": ["oi_unwind", "oi_spike"],
        "primary_factors": ["oi_change_pct", "trend_score"],
        "weight_base": 0.95,
    },
    "Funding Rate AI": {
        "role": "Funding-rate sentiment reader",
        "focus": "Positive funding = long crowded; negative = short crowded",
        "long_setup": "funding < -0.0005 (shorts paying — fade shorts)",
        "short_setup": "funding > +0.0006 (longs paying heavily — fade longs)",
        "hold_setup": "Funding ±0.0002 (neutral)",
        "risk_flags": ["funding_crowded_long", "funding_crowded_short"],
        "primary_factors": ["funding_rate"],
        "weight_base": 0.9,
    },
    "Liquidation AI": {
        "role": "Liquidation cascade analyst",
        "focus": "One-sided liquidations as capitulation or squeeze fuel",
        "long_setup": "Long-side liquidation cascade below price (capitulation low)",
        "short_setup": "Short-side liquidation cascade above price (squeeze top)",
        "hold_setup": "Balanced liquidation (no clear cascade direction)",
        "risk_flags": ["long_liq_cascade", "short_squeeze"],
        "primary_factors": ["liquidation_imbalance"],
        "weight_base": 0.95,
    },
    "Support Resistance AI": {
        "role": "Key level technician",
        "focus": "Recent S/R within 1.5x ATR; reaction at touch",
        "long_setup": "Bounce off support with confirmation candle",
        "short_setup": "Rejection at resistance with confirmation candle",
        "hold_setup": "Mid-range, no key level near price",
        "risk_flags": ["s_breach", "r_breach"],
        "primary_factors": ["support", "resistance", "range_pos", "atr_pct"],
        "weight_base": 1.0,
    },
    "VWAP AI": {
        "role": "VWAP mean-reversion / trend expert",
        "focus": "Distance and direction from session VWAP",
        "long_setup": "Price reclaims VWAP from below + holding (trend resumption)",
        "short_setup": "Price loses VWAP from above + holding below",
        "hold_setup": "Hugging VWAP (no edge)",
        "risk_flags": ["vwap_lost", "vwap_extreme"],
        "primary_factors": ["vwap", "trend_score"],
        "weight_base": 0.95,
    },
    "Multi Timeframe AI": {
        "role": "Higher-timeframe context auditor",
        "focus": "Conflict check across 1m/3m/5m/15m direction",
        "long_setup": "All four timeframes long (no conflict)",
        "short_setup": "All four timeframes short",
        "hold_setup": "Any timeframe disagrees (mtf_conflict)",
        "risk_flags": ["mtf_conflict", "htf_against"],
        "primary_factors": ["mtf_dirs", "mtf_conflict"],
        "weight_base": 1.05,
    },
    "Market Regime AI": {
        "role": "Regime classifier (CRITICAL gate)",
        "focus": "Trend up / trend down / range / fake_breakout / trap",
        "long_setup": "Only in trend_up or confirmed range_bottom",
        "short_setup": "Only in trend_down or confirmed range_top",
        "hold_setup": "fake_breakout, bull_trap, bear_trap, or noisy regime",
        "risk_flags": ["regime_uncertain", "regime_flip"],
        "primary_factors": ["market_state", "trap_risk", "fake_breakout_risk"],
        "weight_base": 1.15,
    },
    "Noise Filter AI": {
        "role": "Signal-to-noise quality gate",
        "focus": "Filters low-strength signals (sig_strength < 85)",
        "long_setup": "signal_strength > 88 and confidence > 80 with long bias",
        "short_setup": "signal_strength > 88 and confidence > 80 with short bias",
        "hold_setup": "signal_strength < 85 → noise dominates",
        "risk_flags": ["low_signal_strength", "noisy_environment"],
        "primary_factors": ["signal_strength", "confidence"],
        "weight_base": 1.05,
    },
    "Entry Timing AI": {
        "role": "Execution-timing trader",
        "focus": "Avoiding entries at extreme range_pos or mid-candle",
        "long_setup": "range_pos < 0.6 with momentum (room to run)",
        "short_setup": "range_pos > 0.4 with negative momentum",
        "hold_setup": "Entry at range extreme (>0.85 or <0.15) without setup",
        "risk_flags": ["entry_at_extreme", "stale_setup"],
        "primary_factors": ["range_pos", "trend_score"],
        "weight_base": 0.95,
    },
    "Final Risk AI": {
        "role": "Last-line risk gate (CRITICAL)",
        "focus": "Cross-check all risk dimensions before allowing trade",
        "long_setup": "Allow long only when no risk threshold breached AND consensus aligned",
        "short_setup": "Allow short only when no risk threshold breached AND consensus aligned",
        "hold_setup": "ANY of: trap_risk>40, fake>40, range>50, low_sig, mtf_conflict → hold",
        "risk_flags": ["risk_veto", "consensus_weak"],
        "primary_factors": ["trap_risk", "fake_breakout_risk", "range_risk", "signal_strength"],
        "weight_base": 1.2,
    },
}


def list_reviewer_expertise() -> List[Dict[str, Any]]:
    """Stable ordered list of all 30 expertise records (for prompt injection)."""
    return [{"ai_name": name, **dict(payload)} for name, payload in REVIEWER_EXPERTISE.items()]


def expertise_summary_for_prompt() -> str:
    """A compact, LLM-friendly summary block.

    Kept short on purpose - the LLM needs only the discriminating bits to
    role-play each reviewer; the long-form rules live in REVIEWER_EXPERTISE
    for use by tests/learners.
    """
    lines: List[str] = ["Reviewer playbook (each reviewer must reason from its own discipline):"]
    for name, payload in REVIEWER_EXPERTISE.items():
        focus = payload.get("focus", "")
        long_setup = payload.get("long_setup", "")
        short_setup = payload.get("short_setup", "")
        hold_setup = payload.get("hold_setup", "")
        lines.append(
            f"- {name} [{payload.get('role','')}] focus={focus} | "
            f"long={long_setup} | short={short_setup} | hold={hold_setup}"
        )
    return "\n".join(lines)


def get_base_weight(name: str) -> float:
    """Return the pre-learning weight for a reviewer (defaults to 1.0)."""
    record = REVIEWER_EXPERTISE.get(name) or {}
    try:
        return float(record.get("weight_base", 1.0))
    except (TypeError, ValueError):
        return 1.0


def reviewer_record(name: str) -> Mapping[str, Any]:
    return REVIEWER_EXPERTISE.get(name) or {}
