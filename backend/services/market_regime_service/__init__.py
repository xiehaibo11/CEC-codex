"""
Market Regime Classification Service

Classifies market conditions into 7 regime types:
1. Stop Hunt - Price spike through key level then reversal
2. Absorption - Strong flow but price doesn't move
3. Breakout - Trend initiation with aligned signals
4. Continuation - Trend continuation
5. Exhaustion - Trend exhaustion at extremes
6. Trap - Bull/bear trap (strong flow but OI decreasing)
7. Noise - No clear signal

Indicator definitions (per planning document):
- cvd_ratio: CVD / Total Notional (not z-score)
- taker_ratio: ln(buy_notional / sell_notional) - log transformation for symmetry
- oi_delta: OI change percentage
- price_atr: Price Change / ATR
- rsi: RSI14
"""

from services.market_regime_service.data import (
    fetch_ohlc_from_flow,
    _fetch_kline_with_realtime,
    fetch_kline_data,
    calculate_price_metrics,
)
from services.market_regime_service.classification import (
    REGIME_STOP_HUNT,
    REGIME_ABSORPTION,
    REGIME_BREAKOUT,
    REGIME_CONTINUATION,
    REGIME_EXHAUSTION,
    REGIME_TRAP,
    REGIME_NOISE,
    DIRECTION_BULLISH,
    DIRECTION_BEARISH,
    DIRECTION_NEUTRAL,
    get_default_config,
    calculate_direction,
    calculate_confidence,
    calculate_pattern_penalty,
    calculate_direction_penalty,
    classify_regime,
)
from services.market_regime_service.service import get_market_regime

__all__ = [
    "fetch_ohlc_from_flow",
    "_fetch_kline_with_realtime",
    "fetch_kline_data",
    "calculate_price_metrics",
    "REGIME_STOP_HUNT",
    "REGIME_ABSORPTION",
    "REGIME_BREAKOUT",
    "REGIME_CONTINUATION",
    "REGIME_EXHAUSTION",
    "REGIME_TRAP",
    "REGIME_NOISE",
    "DIRECTION_BULLISH",
    "DIRECTION_BEARISH",
    "DIRECTION_NEUTRAL",
    "get_default_config",
    "calculate_direction",
    "calculate_confidence",
    "calculate_pattern_penalty",
    "calculate_direction_penalty",
    "classify_regime",
    "get_market_regime",
]
