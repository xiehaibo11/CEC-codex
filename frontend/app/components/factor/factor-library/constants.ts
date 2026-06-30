export const KLINE_PERIODS = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '8h', '12h', '1d', '3d', '1w', '1M']
export const FORWARD_PERIODS = ['1h', '4h', '12h', '24h']

export const KLINE_PERIOD_SECONDS: Record<string, number> = {
  '1m': 60,
  '3m': 3 * 60,
  '5m': 5 * 60,
  '15m': 15 * 60,
  '30m': 30 * 60,
  '1h': 60 * 60,
  '2h': 2 * 60 * 60,
  '4h': 4 * 60 * 60,
  '8h': 8 * 60 * 60,
  '12h': 12 * 60 * 60,
  '1d': 24 * 60 * 60,
  '3d': 3 * 24 * 60 * 60,
  '1w': 7 * 24 * 60 * 60,
  '1M': 30 * 24 * 60 * 60,
}

export const FORWARD_PERIOD_SECONDS: Record<string, number> = {
  '1h': 60 * 60,
  '4h': 4 * 60 * 60,
  '12h': 12 * 60 * 60,
  '24h': 24 * 60 * 60,
}

// Function categories for the picker in Custom Factor dialog
export const FUNC_CATEGORIES: { key: string; en: string; zh: string; fns: string[] }[] = [
  { key: 'ma', en: 'Moving Avg', zh: '均线', fns: ['SMA', 'EMA', 'WMA'] },
  { key: 'mom', en: 'Momentum', zh: '动量', fns: ['RSI', 'ROC', 'MOM', 'MACD', 'MACD_SIGNAL', 'MACD_HIST', 'STOCH_K', 'STOCH_D', 'CCI', 'WILLR'] },
  { key: 'vol', en: 'Volatility', zh: '波动率', fns: ['ATR', 'STDDEV', 'BBANDS_UPPER', 'BBANDS_MID', 'BBANDS_LOWER'] },
  { key: 'volume', en: 'Volume', zh: '成交量', fns: ['OBV', 'VWAP'] },
  { key: 'ts', en: 'Time Series', zh: '时间序列', fns: ['DELAY', 'DELTA', 'TS_MAX', 'TS_MIN', 'TS_RANK'] },
  { key: 'math', en: 'Math', zh: '数学', fns: ['ABS', 'LOG', 'SIGN', 'MAX', 'MIN', 'RANK', 'ZSCORE'] },
]

// Default expressions inserted when user clicks a function chip
export const FUNC_TEMPLATES: Record<string, string> = {
  SMA: 'SMA(close, 20)', EMA: 'EMA(close, 20)', WMA: 'WMA(close, 20)',
  RSI: 'RSI(close, 14)', ROC: 'ROC(close, 10)', MOM: 'MOM(close, 10)',
  MACD: 'MACD(close, 12, 26, 9)', MACD_SIGNAL: 'MACD_SIGNAL(close, 12, 26, 9)',
  MACD_HIST: 'MACD_HIST(close, 12, 26, 9)',
  STOCH_K: 'STOCH_K(high, low, close, 14)', STOCH_D: 'STOCH_D(high, low, close, 14)',
  CCI: 'CCI(high, low, close, 20)', WILLR: 'WILLR(high, low, close, 14)',
  ATR: 'ATR(high, low, close, 14)', STDDEV: 'STDDEV(close, 20)',
  BBANDS_UPPER: 'BBANDS_UPPER(close, 20)', BBANDS_MID: 'BBANDS_MID(close, 20)',
  BBANDS_LOWER: 'BBANDS_LOWER(close, 20)',
  OBV: 'OBV(close, volume)', VWAP: 'VWAP(high, low, close, volume)',
  DELAY: 'DELAY(close, 1)', DELTA: 'DELTA(close, 1)',
  TS_MAX: 'TS_MAX(close, 20)', TS_MIN: 'TS_MIN(close, 20)', TS_RANK: 'TS_RANK(close, 20)',
  ABS: 'ABS()', LOG: 'LOG()', SIGN: 'SIGN()',
  MAX: 'MAX(, )', MIN: 'MIN(, )', RANK: 'RANK(close)', ZSCORE: 'ZSCORE(close)',
}
