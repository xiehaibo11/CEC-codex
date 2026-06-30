"""Runtime helper registration for factor expressions."""

from typing import Any, Callable, Dict

import numpy as np
import pandas as pd


def build_functions(ta: Any, to_series: Callable, safe_float: Callable) -> Dict:
    """Build function dict from pandas-ta plus local time-series helpers."""
    s = to_series
    sf = safe_float

    funcs = {}

    # Moving Average
    funcs["SMA"] = lambda series, period=20: ta.sma(s(series), length=int(period))
    funcs["EMA"] = lambda series, period=20: ta.ema(s(series), length=int(period))
    funcs["WMA"] = lambda series, period=20: ta.wma(s(series), length=int(period))
    funcs["DEMA"] = lambda series, period=20: ta.dema(s(series), length=int(period))
    funcs["TEMA"] = lambda series, period=20: ta.tema(s(series), length=int(period))
    funcs["HMA"] = lambda series, period=20: ta.hma(s(series), length=int(period))
    funcs["KAMA"] = lambda series, period=20: ta.kama(s(series), length=int(period))

    # Momentum
    funcs["RSI"] = lambda series, period=14: ta.rsi(s(series), length=int(period))
    funcs["ROC"] = lambda series, period=10: ta.roc(s(series), length=int(period))
    funcs["MOM"] = lambda series, period=10: ta.mom(s(series), length=int(period))

    def _macd_col(series, fast=12, slow=26, signal=9, col=0):
        r = ta.macd(s(series), fast=int(fast), slow=int(slow), signal=int(signal))
        if r is not None and r.shape[1] > col:
            return r.iloc[:, col]
        return s(series) * 0

    funcs["MACD"] = lambda series, fast=12, slow=26, signal=9: _macd_col(
        series, fast, slow, signal, 0
    )
    funcs["MACD_SIGNAL"] = lambda series, fast=12, slow=26, signal=9: _macd_col(
        series, fast, slow, signal, 1
    )
    funcs["MACD_HIST"] = lambda series, fast=12, slow=26, signal=9: _macd_col(
        series, fast, slow, signal, 2
    )

    def _stoch_col(high, low, close, period=14, col=0):
        r = ta.stoch(s(high), s(low), s(close), k=int(period))
        if r is not None and r.shape[1] > col:
            return r.iloc[:, col]
        return s(close) * 0

    funcs["STOCH_K"] = lambda h, l, c, period=14: _stoch_col(h, l, c, period, 0)
    funcs["STOCH_D"] = lambda h, l, c, period=14: _stoch_col(h, l, c, period, 1)
    funcs["CCI"] = lambda h, l, c, period=20: ta.cci(
        s(h), s(l), s(c), length=int(period)
    )
    funcs["WILLR"] = lambda h, l, c, period=14: ta.willr(
        s(h), s(l), s(c), length=int(period)
    )
    funcs["PPO"] = lambda series, fast=12, slow=26: ta.ppo(
        s(series), fast=int(fast), slow=int(slow)
    ).iloc[:, 0]
    funcs["TRIX"] = lambda series, period=15: ta.trix(
        s(series), length=int(period)
    ).iloc[:, 0]

    # Trend
    def _adx_col(high, low, close, period=14, col=0):
        r = ta.adx(s(high), s(low), s(close), length=int(period))
        if r is not None and r.shape[1] > col:
            return r.iloc[:, col]
        return s(close) * 0

    funcs["ADX"] = lambda h, l, c, period=14: _adx_col(h, l, c, period, 0)
    funcs["PLUS_DI"] = lambda h, l, c, period=14: _adx_col(h, l, c, period, 1)
    funcs["MINUS_DI"] = lambda h, l, c, period=14: _adx_col(h, l, c, period, 2)

    def _aroon_col(high, low, period=25, col=0):
        r = ta.aroon(s(high), s(low), length=int(period))
        if r is not None and r.shape[1] > col:
            return r.iloc[:, col]
        return s(high) * 0

    funcs["AROON_UP"] = lambda h, l, period=25: _aroon_col(h, l, period, 1)
    funcs["AROON_DOWN"] = lambda h, l, period=25: _aroon_col(h, l, period, 0)

    # Volatility
    funcs["ATR"] = lambda h, l, c, period=14: ta.atr(
        s(h), s(l), s(c), length=int(period)
    )
    funcs["NATR"] = lambda h, l, c, period=14: ta.natr(
        s(h), s(l), s(c), length=int(period)
    )
    funcs["TRUE_RANGE"] = lambda h, l, c: ta.true_range(s(h), s(l), s(c))
    funcs["STDDEV"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).std()
    )

    def _bb(series, period=20, col_idx=0):
        r = ta.bbands(s(series), length=int(period))
        if r is not None and r.shape[1] > col_idx:
            return r.iloc[:, col_idx]
        return s(series) * 0

    funcs["BBANDS_LOWER"] = lambda series, period=20: _bb(series, period, 0)
    funcs["BBANDS_MID"] = lambda series, period=20: _bb(series, period, 1)
    funcs["BBANDS_UPPER"] = lambda series, period=20: _bb(series, period, 2)

    # Volume
    funcs["OBV"] = lambda close, volume: ta.obv(s(close), s(volume))
    funcs["VWAP"] = lambda h, l, c, v: ta.vwap(s(h), s(l), s(c), s(v))
    funcs["AD"] = lambda h, l, c, v: ta.ad(s(h), s(l), s(c), s(v))
    funcs["CMF"] = lambda h, l, c, v, period=20: ta.cmf(
        s(h), s(l), s(c), s(v), length=int(period)
    )
    funcs["MFI"] = lambda h, l, c, v, period=14: ta.mfi(
        s(h), s(l), s(c), s(v), length=int(period)
    )

    # Time Series Operators
    funcs["DELAY"] = lambda series, period=1: s(series).shift(int(period))
    funcs["DELTA"] = lambda series, period=1: s(series).diff(int(period))
    funcs["TS_SUM"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).sum()
    )
    funcs["TS_MEAN"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).mean()
    )
    funcs["TS_STD"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).std()
    )
    funcs["TS_MAX"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).max()
    )
    funcs["TS_MIN"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).min()
    )

    def _ts_rank(series, period=20):
        sr = s(series)
        return sr.rolling(window=int(period)).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )

    funcs["TS_RANK"] = _ts_rank

    def _ts_argmax(series, period=20):
        sr = s(series)
        return sr.rolling(window=int(period)).apply(
            lambda x: int(period) - 1 - np.argmax(x), raw=True
        )

    funcs["TS_ARGMAX"] = _ts_argmax

    def _ts_argmin(series, period=20):
        sr = s(series)
        return sr.rolling(window=int(period)).apply(
            lambda x: int(period) - 1 - np.argmin(x), raw=True
        )

    funcs["TS_ARGMIN"] = _ts_argmin

    funcs["TS_CORR"] = (
        lambda a, b, period=20: s(a).rolling(window=int(period)).corr(s(b))
    )
    funcs["TS_COV"] = lambda a, b, period=20: s(a).rolling(window=int(period)).cov(s(b))
    funcs["TS_SKEW"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).skew()
    )
    funcs["TS_KURT"] = (
        lambda series, period=20: s(series).rolling(window=int(period)).kurt()
    )

    def _decaylinear(series, period=10):
        sr = s(series)
        w = np.arange(1, int(period) + 1, dtype=float)
        w = w / w.sum()
        return sr.rolling(window=int(period)).apply(lambda x: np.dot(x, w), raw=True)

    funcs["DECAYLINEAR"] = _decaylinear

    funcs["LOG_RETURN"] = lambda series, period=1: np.log(
        s(series) / s(series).shift(int(period))
    )
    funcs["TS_PCT_CHANGE"] = lambda series, period=1: s(series).pct_change(
        periods=int(period)
    )

    # Cross-section
    funcs["RANK"] = lambda series: s(series).rank(pct=True)
    funcs["ZSCORE"] = lambda series: (s(series) - s(series).mean()) / (
        s(series).std() + 1e-10
    )

    def _normalize(series, period=20):
        sr = s(series)
        rm = sr.rolling(window=int(period)).mean()
        rs = sr.rolling(window=int(period)).std()
        return (sr - rm) / (rs + 1e-10)

    funcs["NORMALIZE"] = _normalize

    # Math
    funcs["ABS"] = lambda x: np.abs(sf(x))
    funcs["LOG"] = lambda x: np.log(sf(x).clip(lower=1e-10))
    funcs["SIGN"] = lambda x: np.sign(sf(x))
    funcs["SQRT"] = lambda x: np.sqrt(sf(x).clip(lower=0))
    funcs["EXP"] = lambda x: np.exp(sf(x).clip(upper=500))
    funcs["POW"] = lambda x, n: np.power(sf(x), float(n))
    funcs["MAX"] = lambda a, b: np.maximum(sf(a), sf(b))
    funcs["MIN"] = lambda a, b: np.minimum(sf(a), sf(b))
    funcs["CLAMP"] = lambda x, lo, hi: sf(x).clip(lower=float(lo), upper=float(hi))

    # Conditional
    def _if(cond, then_val, else_val):
        c = sf(cond)
        t = sf(then_val) if hasattr(then_val, "__len__") else float(then_val)
        e = sf(else_val) if hasattr(else_val, "__len__") else float(else_val)
        return pd.Series(np.where(c != 0, t, e), index=c.index)

    funcs["IF"] = _if
    funcs["WHERE"] = _if

    funcs["AND"] = lambda a, b: (sf(a) != 0) & (sf(b) != 0)
    funcs["OR"] = lambda a, b: (sf(a) != 0) | (sf(b) != 0)
    funcs["NOT"] = lambda x: ~(sf(x) != 0)

    return funcs


__all__ = ["build_functions"]
