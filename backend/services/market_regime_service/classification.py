"""
Regime constants, config access, and regime-decision logic.

Contains the regime/direction constants, the default-config accessor, the
direction/confidence scoring helpers, the penalty multipliers, and the core
regime classifier.
"""

import math
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from database.models import MarketRegimeConfig

# Regime type constants
REGIME_STOP_HUNT = "stop_hunt"
REGIME_ABSORPTION = "absorption"
REGIME_BREAKOUT = "breakout"
REGIME_CONTINUATION = "continuation"
REGIME_EXHAUSTION = "exhaustion"
REGIME_TRAP = "trap"
REGIME_NOISE = "noise"

# Direction constants
DIRECTION_BULLISH = "bullish"
DIRECTION_BEARISH = "bearish"
DIRECTION_NEUTRAL = "neutral"


def get_default_config(db: Session) -> Optional[MarketRegimeConfig]:
    """Get default regime config from database"""
    return db.query(MarketRegimeConfig).filter(
        MarketRegimeConfig.is_default == True
    ).first()


def calculate_direction(cvd_ratio: float, taker_log_ratio: float, price_atr: float) -> str:
    """
    Calculate direction by voting: cvd + taker + price.
    Note: taker_log_ratio is already log-transformed, so >0 means bullish, <0 means bearish.
    """
    votes = 0
    if cvd_ratio > 0:
        votes += 1
    elif cvd_ratio < 0:
        votes -= 1
    if taker_log_ratio > 0:  # log(buy/sell) > 0 means buy > sell
        votes += 1
    elif taker_log_ratio < 0:
        votes -= 1
    if price_atr > 0:
        votes += 1
    elif price_atr < 0:
        votes -= 1

    if votes >= 2:
        return DIRECTION_BULLISH
    elif votes <= -2:
        return DIRECTION_BEARISH
    return DIRECTION_NEUTRAL


def calculate_confidence(
    cvd_ratio: float, taker_log_ratio: float, oi_delta: float, price_atr: float
) -> float:
    """Calculate base confidence score (0-1) based on signal strength"""
    # Normalize each indicator to 0-1 range
    # cvd_ratio: typical range -0.5 to 0.5, cap at 0.3
    # taker_log_ratio: typical range -1 to 1 (log scale)
    # oi_delta: typical range -5% to 5%
    # price_atr: typical range -2 to 2
    score = (
        0.3 * min(abs(cvd_ratio), 0.3) / 0.3 +
        0.2 * min(abs(taker_log_ratio), 1.0) / 1.0 +
        0.2 * min(abs(oi_delta), 5.0) / 5.0 +
        0.3 * min(abs(price_atr), 2.0) / 2.0
    )
    return max(0.0, min(1.0, score))


def calculate_pattern_penalty(
    regime: str,
    cvd_ratio: float,
    price_atr: float,
    oi_delta: float,
    rsi: float,
    price_range_atr: float
) -> float:
    """
    Calculate pattern penalty based on regime-specific feature matching.
    Returns multiplier 0.70-1.0 (1.0 = no penalty, <1.0 = penalty for mismatch).
    """
    score = 1.0

    cvd_weak = abs(cvd_ratio) < 0.03
    price_strong = abs(price_atr) > 0.5
    rsi_extreme = rsi > 70 or rsi < 30
    range_large = price_range_atr > 1.0
    body_ratio = abs(price_atr) / price_range_atr if price_range_atr > 0 else 1.0
    cvd_price_aligned = (cvd_ratio > 0 and price_atr > 0) or (cvd_ratio < 0 and price_atr < 0)

    if regime == REGIME_BREAKOUT:
        if not cvd_price_aligned:
            score -= 0.12  # CVD and price should be aligned for breakout
        if cvd_weak:
            score -= 0.08  # CVD should be strong for breakout

    elif regime == REGIME_ABSORPTION:
        if price_strong:
            score -= 0.10  # Price should be weak for absorption
        if cvd_weak:
            score -= 0.08  # CVD should be strong for absorption

    elif regime == REGIME_CONTINUATION:
        if not cvd_price_aligned:
            score -= 0.15  # CVD and price must be aligned for continuation

    elif regime == REGIME_EXHAUSTION:
        if not rsi_extreme:
            score -= 0.10  # RSI should be extreme for exhaustion

    elif regime == REGIME_TRAP:
        if cvd_price_aligned:
            score -= 0.12  # Trap should have CVD/price divergence

    elif regime == REGIME_STOP_HUNT:
        if not range_large:
            score -= 0.10  # Stop hunt needs large range
        if body_ratio > 0.5:
            score -= 0.08  # Stop hunt should have small body (reversal)

    elif regime == REGIME_NOISE:
        score -= 0.15  # Noise regime gets penalty

    return max(0.70, score)


def calculate_direction_penalty(
    regime: str,
    cvd_ratio: float,
    price_atr: float,
    taker_log_ratio: float
) -> float:
    """
    Calculate direction penalty based on CVD/Price/Taker alignment.
    Returns multiplier 0.85-1.0 (1.0 = no penalty, <1.0 = penalty for mismatch).
    """
    cvd_dir = 1 if cvd_ratio > 0.02 else (-1 if cvd_ratio < -0.02 else 0)
    price_dir = 1 if price_atr > 0.1 else (-1 if price_atr < -0.1 else 0)
    taker_dir = 1 if taker_log_ratio > 0.15 else (-1 if taker_log_ratio < -0.15 else 0)

    dirs = [d for d in [cvd_dir, price_dir, taker_dir] if d != 0]
    if len(dirs) < 2:
        return 1.0  # Insufficient data, no penalty

    all_aligned = all(d == dirs[0] for d in dirs)
    has_contradiction = (1 in dirs and -1 in dirs)

    # Breakout/Continuation: should have aligned directions
    if regime in [REGIME_BREAKOUT, REGIME_CONTINUATION]:
        if has_contradiction:
            return 0.85  # -15% penalty for direction contradiction

    # Absorption/Trap: expect divergence, penalize if all aligned
    elif regime in [REGIME_ABSORPTION, REGIME_TRAP]:
        if all_aligned:
            return 0.88  # -12% penalty for unexpected alignment

    elif regime == REGIME_NOISE:
        return 0.90  # -10% penalty for noise

    return 1.0


def classify_regime(
    cvd_ratio: float,
    taker_log_ratio: float,
    oi_delta: float,
    price_atr: float,
    rsi: float,
    price_range_atr: float,
    config: MarketRegimeConfig
) -> Tuple[str, str]:
    """
    Classify market regime based on indicators.
    Returns (regime_type, reason)

    Priority order:
    1. Stop Hunt - spike and reversal
    2. Breakout - strong CVD + price move + (Taker extreme OR OI increase)
    3. Exhaustion - strong CVD + OI decrease + RSI extreme
    4. Trap - strong CVD + OI decrease significantly
    5. Absorption - strong CVD but price doesn't move
    6. Continuation - CVD aligned with price movement
    7. Noise - no clear pattern

    Note: Taker thresholds should be set to capture ~25% as extreme.
    Default: taker_high=33, taker_low=0.03 (log threshold ±3.5)
    """
    # Thresholds from config
    cvd_strong = config.breakout_cvd_z * 0.1  # ~0.15 for strong flow
    cvd_divisor = config.continuation_cvd_divisor or 3.0
    cvd_weak = cvd_strong / cvd_divisor  # ~0.05 for weak flow
    price_breakout = config.breakout_price_atr + 0.2  # ~0.5 for breakout
    price_move = config.absorption_price_atr  # ~0.3 for movement
    oi_increase = config.breakout_oi_z  # OI increase threshold
    oi_decrease = config.trap_oi_z  # OI decrease threshold

    # Taker extreme check (using log thresholds)
    taker_high_log = math.log(config.breakout_taker_high) if config.breakout_taker_high > 0 else 3.5
    taker_low_log = math.log(config.breakout_taker_low) if config.breakout_taker_low > 0 else -3.5
    is_taker_extreme = taker_log_ratio > taker_high_log or taker_log_ratio < taker_low_log

    # Direction alignment check
    cvd_price_aligned = (cvd_ratio > 0 and price_atr > 0) or (cvd_ratio < 0 and price_atr < 0)

    # 1. Stop Hunt: large range but close near open (spike and reversal)
    if (price_range_atr > config.stop_hunt_range_atr and
        abs(price_atr) < config.stop_hunt_close_atr):
        return REGIME_STOP_HUNT, "Price spiked but closed near open"

    # 2. Breakout: strong CVD + price move + (Taker extreme OR OI increase)
    # Additional check: body must be significant portion of range (not spike-and-reverse)
    is_cvd_strong = abs(cvd_ratio) > cvd_strong
    is_price_breakout = abs(price_atr) > price_breakout
    is_oi_increase = oi_delta > oi_increase
    # Body ratio: if price spiked but reversed (long shadow), it's not a true breakout
    body_ratio = abs(price_atr) / price_range_atr if price_range_atr > 0 else 1.0
    body_ratio_threshold = config.breakout_body_ratio or 0.4
    is_solid_move = body_ratio > body_ratio_threshold  # Body must be > threshold of range

    if is_cvd_strong and is_price_breakout and cvd_price_aligned and is_solid_move and (is_taker_extreme or is_oi_increase):
        direction = "Bullish" if cvd_ratio > 0 else "Bearish"
        return REGIME_BREAKOUT, f"{direction} breakout with aligned signals"

    # 3. Exhaustion: strong CVD + OI decrease + RSI extreme
    is_oi_decrease = oi_delta < oi_decrease
    rsi_extreme = rsi > config.exhaustion_rsi_high or rsi < config.exhaustion_rsi_low

    if is_cvd_strong and is_oi_decrease and rsi_extreme:
        return REGIME_EXHAUSTION, "Trend exhaustion at RSI extreme"

    # 4. Trap: strong CVD + OI decrease + price reversal (close near open)
    if is_cvd_strong and is_oi_decrease and abs(price_atr) < config.stop_hunt_close_atr:
        return REGIME_TRAP, "Strong flow but positions closing with reversal (trap)"

    # 5. Absorption: strong CVD but price doesn't move
    is_price_move = abs(price_atr) > price_move
    if is_cvd_strong and not is_price_move:
        return REGIME_ABSORPTION, "Strong flow absorbed without price movement"

    # 6. Continuation: CVD aligned with price movement
    is_cvd_weak = abs(cvd_ratio) > cvd_weak
    if is_cvd_weak and is_price_move and cvd_price_aligned:
        direction = "Bullish" if cvd_ratio > 0 else "Bearish"
        return REGIME_CONTINUATION, f"{direction} trend continuation"

    # 7. Noise: no clear pattern
    return REGIME_NOISE, "No clear market regime detected"
