export function formatMetricName(metric: string): string {
  const names: Record<string, string> = {
    cvd_change: 'CVD Change',
    oi_delta: 'OI Delta',
    oi_delta_percent: 'OI Delta %',
    buy_sell_imbalance: 'Buy/Sell Imbalance',
    depth_ratio: 'Depth Ratio',
    taker_buy_ratio: 'Taker Buy Ratio',
    taker_direction: 'Taker Direction',
  }
  return names[metric] || metric
}

export function formatValue(metric: string, value: number): string {
  if (metric.includes('ratio') || metric.includes('imbalance')) {
    return value.toFixed(3)
  }
  if (metric.includes('percent') || metric === 'cvd_change' || metric === 'oi_delta') {
    return `${value.toFixed(2)}%`
  }
  return value.toFixed(4)
}

export function getRegimeColor(regime: string): string {
  const colors: Record<string, string> = {
    stop_hunt: 'text-red-500',
    absorption: 'text-purple-500',
    breakout: 'text-green-500',
    continuation: 'text-blue-500',
    exhaustion: 'text-orange-500',
    trap: 'text-yellow-500',
    noise: 'text-gray-500',
  }
  return colors[regime] || 'text-gray-500'
}

export function formatRegimeName(regime: string): string {
  const names: Record<string, string> = {
    stop_hunt: 'Stop Hunt',
    absorption: 'Absorption',
    breakout: 'Breakout',
    continuation: 'Continuation',
    exhaustion: 'Exhaustion',
    trap: 'Trap',
    noise: 'Noise',
  }
  return names[regime] || regime
}

export function getDirectionColor(direction: string): string {
  return direction === 'buy' ? 'text-green-400' : 'text-red-400'
}

export function getDirectionLabel(direction: string): string {
  return direction === 'buy' ? 'BUY' : 'SELL'
}

export function getDominantLabel(direction: string): string {
  return direction === 'buy' ? 'Buyers' : 'Sellers'
}

export function formatDominantMultiplier(direction: string | undefined, ratio: number | undefined): string | undefined {
  if (direction === 'sell' && ratio && ratio > 0) {
    return (1 / ratio).toFixed(2)
  }
  return ratio?.toFixed(2)
}

export function formatMillions(volume: number | undefined): string {
  return ((volume || 0) / 1e6).toFixed(1)
}

export function formatThousands(volume: number | undefined): string {
  return ((volume || 0) / 1000).toFixed(0)
}

export function formatMacdEventLabel(event: string): string {
  const eventLabels: Record<string, string> = {
    golden_cross: '🟢 Golden Cross',
    death_cross: '🔴 Death Cross',
    histogram_positive: '🟢 Histogram +',
    histogram_negative: '🔴 Histogram -',
    macd_above_zero: '🟢 MACD > 0',
    macd_below_zero: '🔴 MACD < 0',
  }
  return eventLabels[event] || event
}

export function getMacdEventColor(event: string): string {
  return event.includes('golden') || event.includes('positive') || event.includes('above')
    ? 'text-green-400'
    : 'text-red-400'
}

export function formatRegimeDirection(direction: string): string {
  if (direction === 'long') return '↑'
  if (direction === 'short') return '↓'
  return '−'
}
