"""Factor expression function metadata."""

from typing import Dict


# Single Source of Truth: Function Registry
# Every supported function is defined here with full metadata.
# registry.build_functions() registers the actual implementations keyed by name.
# GET /api/factors/expression-functions serves this to frontend + AI.

FUNCTION_REGISTRY: Dict[str, dict] = {}


def _reg(name, cat, sig, desc, desc_zh, example, params=None):
    FUNCTION_REGISTRY[name] = {
        "category": cat,
        "signature": sig,
        "description": desc,
        "description_zh": desc_zh,
        "example": example,
        "params": params or [],
    }


# fmt: off
# Moving Average
_reg("SMA", "moving_average", "SMA(series, period)", "Simple Moving Average", "简单移动平均", "SMA(close, 20)")
_reg("EMA", "moving_average", "EMA(series, period)", "Exponential Moving Average", "指数移动平均", "EMA(close, 12)")
_reg("WMA", "moving_average", "WMA(series, period)", "Weighted Moving Average", "加权移动平均", "WMA(close, 20)")
_reg("DEMA", "moving_average", "DEMA(series, period)", "Double Exponential Moving Average", "双重指数移动平均", "DEMA(close, 20)")
_reg("TEMA", "moving_average", "TEMA(series, period)", "Triple Exponential Moving Average", "三重指数移动平均", "TEMA(close, 20)")
_reg("HMA", "moving_average", "HMA(series, period)", "Hull Moving Average (less lag)", "Hull移动平均(低延迟)", "HMA(close, 20)")
_reg("KAMA", "moving_average", "KAMA(series, period)", "Kaufman Adaptive Moving Average", "考夫曼自适应移动平均", "KAMA(close, 20)")

# Momentum
_reg("RSI", "momentum", "RSI(series, period)", "Relative Strength Index (0-100)", "相对强弱指数", "RSI(close, 14)")
_reg("ROC", "momentum", "ROC(series, period)", "Rate of Change (%)", "变化率", "ROC(close, 10)")
_reg("MOM", "momentum", "MOM(series, period)", "Momentum (price difference)", "动量(价差)", "MOM(close, 10)")
_reg("MACD", "momentum", "MACD(series, fast, slow, signal)", "MACD line", "MACD线", "MACD(close, 12, 26, 9)")
_reg("MACD_SIGNAL", "momentum", "MACD_SIGNAL(series, fast, slow, signal)", "MACD signal line", "MACD信号线", "MACD_SIGNAL(close, 12, 26, 9)")
_reg("MACD_HIST", "momentum", "MACD_HIST(series, fast, slow, signal)", "MACD histogram", "MACD柱状图", "MACD_HIST(close, 12, 26, 9)")
_reg("STOCH_K", "momentum", "STOCH_K(high, low, close, period)", "Stochastic %K", "随机指标%K", "STOCH_K(high, low, close, 14)")
_reg("STOCH_D", "momentum", "STOCH_D(high, low, close, period)", "Stochastic %D", "随机指标%D", "STOCH_D(high, low, close, 14)")
_reg("CCI", "momentum", "CCI(high, low, close, period)", "Commodity Channel Index", "顺势指标", "CCI(high, low, close, 20)")
_reg("WILLR", "momentum", "WILLR(high, low, close, period)", "Williams %R (-100~0)", "威廉指标", "WILLR(high, low, close, 14)")
_reg("PPO", "momentum", "PPO(series, fast, slow)", "Percentage Price Oscillator", "百分比价格振荡器", "PPO(close, 12, 26)")
_reg("TRIX", "momentum", "TRIX(series, period)", "Triple EMA Rate of Change", "三重EMA变化率", "TRIX(close, 15)")

# Trend
_reg("ADX", "trend", "ADX(high, low, close, period)", "Average Directional Index (trend strength)", "平均趋向指数(趋势强度)", "ADX(high, low, close, 14)")
_reg("PLUS_DI", "trend", "PLUS_DI(high, low, close, period)", "Plus Directional Indicator", "正方向指标", "PLUS_DI(high, low, close, 14)")
_reg("MINUS_DI", "trend", "MINUS_DI(high, low, close, period)", "Minus Directional Indicator", "负方向指标", "MINUS_DI(high, low, close, 14)")
_reg("AROON_UP", "trend", "AROON_UP(high, low, period)", "Aroon Up (0-100)", "阿隆上升线", "AROON_UP(high, low, 25)")
_reg("AROON_DOWN", "trend", "AROON_DOWN(high, low, period)", "Aroon Down (0-100)", "阿隆下降线", "AROON_DOWN(high, low, 25)")

# Volatility
_reg("ATR", "volatility", "ATR(high, low, close, period)", "Average True Range", "平均真实波幅", "ATR(high, low, close, 14)")
_reg("NATR", "volatility", "NATR(high, low, close, period)", "Normalized ATR (% of close)", "标准化ATR(收盘价百分比)", "NATR(high, low, close, 14)")
_reg("TRUE_RANGE", "volatility", "TRUE_RANGE(high, low, close)", "True Range (single bar)", "真实波幅(单根)", "TRUE_RANGE(high, low, close)")
_reg("STDDEV", "volatility", "STDDEV(series, period)", "Rolling Standard Deviation", "滚动标准差", "STDDEV(close, 20)")
_reg("BBANDS_UPPER", "volatility", "BBANDS_UPPER(series, period)", "Bollinger upper band", "布林带上轨", "BBANDS_UPPER(close, 20)")
_reg("BBANDS_MID", "volatility", "BBANDS_MID(series, period)", "Bollinger middle band", "布林带中轨", "BBANDS_MID(close, 20)")
_reg("BBANDS_LOWER", "volatility", "BBANDS_LOWER(series, period)", "Bollinger lower band", "布林带下轨", "BBANDS_LOWER(close, 20)")

# Volume
_reg("OBV", "volume", "OBV(close, volume)", "On-Balance Volume", "能量潮", "OBV(close, volume)")
_reg("VWAP", "volume", "VWAP(high, low, close, volume)", "Volume Weighted Average Price", "成交量加权均价", "VWAP(high, low, close, volume)")
_reg("AD", "volume", "AD(high, low, close, volume)", "Accumulation/Distribution Line", "累积/派发线", "AD(high, low, close, volume)")
_reg("CMF", "volume", "CMF(high, low, close, volume, period)", "Chaikin Money Flow", "蔡金资金流", "CMF(high, low, close, volume, 20)")
_reg("MFI", "volume", "MFI(high, low, close, volume, period)", "Money Flow Index (0-100)", "资金流量指数", "MFI(high, low, close, volume, 14)")

# Time Series Operators
_reg("DELAY", "time_series", "DELAY(series, period)", "Value N bars ago", "N根K线前的值", "DELAY(close, 5)")
_reg("DELTA", "time_series", "DELTA(series, period)", "Difference from N bars ago: x - x[N]", "与N根前的差值", "DELTA(close, 5)")
_reg("TS_SUM", "time_series", "TS_SUM(series, period)", "Rolling sum over N bars", "N根滚动求和", "TS_SUM(volume, 20)")
_reg("TS_MEAN", "time_series", "TS_MEAN(series, period)", "Rolling mean over N bars", "N根滚动均值", "TS_MEAN(close, 20)")
_reg("TS_STD", "time_series", "TS_STD(series, period)", "Rolling standard deviation", "滚动标准差", "TS_STD(close, 20)")
_reg("TS_MAX", "time_series", "TS_MAX(series, period)", "Rolling maximum", "滚动最大值", "TS_MAX(high, 20)")
_reg("TS_MIN", "time_series", "TS_MIN(series, period)", "Rolling minimum", "滚动最小值", "TS_MIN(low, 20)")
_reg("TS_RANK", "time_series", "TS_RANK(series, period)", "Rolling percentile rank (0-1)", "滚动百分位排名", "TS_RANK(close, 20)")
_reg("TS_ARGMAX", "time_series", "TS_ARGMAX(series, period)", "Bars since rolling max (0=today)", "距最高点的K线数", "TS_ARGMAX(high, 20)")
_reg("TS_ARGMIN", "time_series", "TS_ARGMIN(series, period)", "Bars since rolling min (0=today)", "距最低点的K线数", "TS_ARGMIN(low, 20)")
_reg("TS_CORR", "time_series", "TS_CORR(a, b, period)", "Rolling Pearson correlation", "滚动相关系数", "TS_CORR(close, volume, 20)")
_reg("TS_COV", "time_series", "TS_COV(a, b, period)", "Rolling covariance", "滚动协方差", "TS_COV(close, volume, 20)")
_reg("TS_SKEW", "time_series", "TS_SKEW(series, period)", "Rolling skewness", "滚动偏度", "TS_SKEW(close, 20)")
_reg("TS_KURT", "time_series", "TS_KURT(series, period)", "Rolling kurtosis", "滚动峰度", "TS_KURT(close, 20)")
_reg("DECAYLINEAR", "time_series", "DECAYLINEAR(series, period)", "Linearly decaying weighted average", "线性衰减加权平均", "DECAYLINEAR(close, 10)")
_reg("LOG_RETURN", "time_series", "LOG_RETURN(series, period)", "Log return: ln(x / x[N])", "对数收益率", "LOG_RETURN(close, 1)")
_reg("TS_PCT_CHANGE", "time_series", "TS_PCT_CHANGE(series, period)", "Percentage change: (x - x[N]) / x[N]", "百分比变化", "TS_PCT_CHANGE(close, 1)")

# Cross-section
_reg("RANK", "cross_section", "RANK(series)", "Percentile rank across all bars (0-1)", "全序列百分位排名", "RANK(close)")
_reg("ZSCORE", "cross_section", "ZSCORE(series)", "Z-score: (x - mean) / std", "Z分数标准化", "ZSCORE(RSI(close, 14))")
_reg("NORMALIZE", "cross_section", "NORMALIZE(series, period)", "Rolling Z-score: (x - rolling_mean) / rolling_std", "滚动Z分数标准化", "NORMALIZE(close, 20)")

# Math
_reg("ABS", "math", "ABS(x)", "Absolute value", "绝对值", "ABS(DELTA(close, 5))")
_reg("LOG", "math", "LOG(x)", "Natural logarithm (ln)", "自然对数", "LOG(volume)")
_reg("SIGN", "math", "SIGN(x)", "Sign: -1, 0, or 1", "符号函数", "SIGN(ROC(close, 5))")
_reg("SQRT", "math", "SQRT(x)", "Square root", "平方根", "SQRT(ATR(high,low,close,14))")
_reg("EXP", "math", "EXP(x)", "Exponential (e^x)", "指数函数", "EXP(-RSI(close,14)/100)")
_reg("POW", "math", "POW(x, n)", "Power: x^n", "幂运算", "POW(ROC(close,10), 2)")
_reg("MAX", "math", "MAX(a, b)", "Element-wise maximum", "逐元素取最大", "MAX(SMA(close,10), SMA(close,20))")
_reg("MIN", "math", "MIN(a, b)", "Element-wise minimum", "逐元素取最小", "MIN(low, DELAY(low,1))")
_reg("CLAMP", "math", "CLAMP(x, lo, hi)", "Clip values to [lo, hi] range", "截断到范围", "CLAMP(RSI(close,14), 30, 70)")

# Conditional
_reg("IF", "conditional", "IF(cond, then_val, else_val)", "Conditional: if cond then A else B", "条件选择", "IF(ROC(close,5) > 0, 1, -1)")
_reg("AND", "conditional", "AND(a, b)", "Logical AND (element-wise)", "逻辑与", "AND(RSI(close,14) > 30, RSI(close,14) < 70)")
_reg("OR", "conditional", "OR(a, b)", "Logical OR (element-wise)", "逻辑或", "OR(RSI(close,14) < 30, RSI(close,14) > 70)")
_reg("NOT", "conditional", "NOT(x)", "Logical NOT (element-wise)", "逻辑非", "NOT(ROC(close,5) > 0)")
# fmt: on

# Category labels for frontend display
CATEGORY_LABELS = {
    "moving_average": {"en": "Moving Average", "zh": "移动平均"},
    "momentum": {"en": "Momentum", "zh": "动量"},
    "trend": {"en": "Trend", "zh": "趋势"},
    "volatility": {"en": "Volatility", "zh": "波动率"},
    "volume": {"en": "Volume", "zh": "成交量"},
    "time_series": {"en": "Time Series Operators", "zh": "时间序列算子"},
    "cross_section": {"en": "Cross-Section", "zh": "截面"},
    "math": {"en": "Math", "zh": "数学"},
    "conditional": {"en": "Conditional / Logic", "zh": "条件/逻辑"},
}

FACTOR_DEFINITIONS = FUNCTION_REGISTRY

__all__ = ["CATEGORY_LABELS", "FACTOR_DEFINITIONS", "FUNCTION_REGISTRY"]

del _reg
