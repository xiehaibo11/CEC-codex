import { minutesByInterval } from './constants'
import { formatTime, planRank } from './formatters'
import type { CoinGlassEndpoint } from './types'

export function toNumber(value: unknown) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function rowFromUnknown(item: unknown): Record<string, unknown> {
  if (Array.isArray(item)) {
    return item.reduce<Record<string, unknown>>((acc, value, index) => {
      acc[index === 0 ? 'time' : `value_${index}`] = value
      return acc
    }, {})
  }
  if (item && typeof item === 'object') return item as Record<string, unknown>
  return { value: item }
}

export function extractRows(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data.map(rowFromUnknown)
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    const arrayKey = Object.keys(record).find((key) => Array.isArray(record[key]))
    if (arrayKey) return (record[arrayKey] as unknown[]).map(rowFromUnknown)
    return [record]
  }
  return []
}

export function timeKeyFor(rows: Record<string, unknown>[]) {
  const keys = Object.keys(rows[0] || {})
  return keys.find((key) => ['time', 'timestamp', 'open_time', 'created_at', 'date'].includes(key)) || null
}

export function numericKeysFor(rows: Record<string, unknown>[]) {
  const sample = rows.slice(0, 40)
  const keys = new Set<string>()
  sample.forEach((row) => {
    Object.entries(row).forEach(([key, value]) => {
      if (key === 'time' || key.endsWith('_time') || key === 'timestamp') return
      if (toNumber(value) !== null) keys.add(key)
    })
  })
  return Array.from(keys)
}

export function preferredKeys(keys: string[], focus?: string) {
  const priority = [
    'close',
    'current_price',
    'volume_usd',
    'open_interest_usd',
    'open_interest',
    'long_volume_usd',
    'short_volume_usd',
    'agg_taker_buy_vol',
    'agg_taker_sell_vol',
    'cum_vol_delta',
    'long_liquidation_usd',
    'short_liquidation_usd',
    'aggregated_long_liquidation_usd',
    'aggregated_short_liquidation_usd',
    'long_short_ratio',
    'funding_rate',
    'value',
  ]
  const focusBoost = focus === 'ratio' ? ['long_short_ratio', 'long_account', 'short_account'] : []
  const ordered = [...focusBoost, ...priority]
    .map((key) => keys.find((candidate) => candidate === key || candidate.includes(key)))
    .filter(Boolean) as string[]
  const remaining = keys.filter((key) => !ordered.includes(key))
  return [...ordered, ...remaining].slice(0, 5)
}

export function chartRowsFor(rows: Record<string, unknown>[], rowTimeKey: string | null, chartKeys: string[]) {
  return rows.slice(-120).map((row, index) => {
    const next: Record<string, unknown> = {
      label: rowTimeKey ? formatTime(row[rowTimeKey]) : String(index + 1),
    }
    chartKeys.forEach((key) => {
      next[key] = toNumber(row[key])
    })
    return next
  })
}

export function columnsFor(rows: Record<string, unknown>[], chartKeys: string[]) {
  const keys = Object.keys(rows[0] || {})
  const priority = ['time', 'timestamp', 'exchange_name', 'symbol', 'instrument_id', ...chartKeys]
  return Array.from(new Set([...priority.filter((key) => keys.includes(key)), ...keys])).slice(0, 12)
}

export function endpointNeedsPlan(endpoint?: CoinGlassEndpoint, currentPlan?: string | null) {
  if (!endpoint?.min_plan || !currentPlan) return false
  const current = planRank(currentPlan)
  const required = planRank(endpoint.min_plan)
  return current >= 0 && required >= 0 && current < required
}

export function startupIntervalBlocked(
  endpoint: CoinGlassEndpoint | undefined,
  currentPlan: string | null | undefined,
  interval: string,
) {
  if (!endpoint || currentPlan?.toLowerCase() !== 'startup') return false
  const limit = endpoint.interval_limit?.Startup
  if (!limit || limit.includes('No Limit')) return false
  const required = limit.includes('>=30m') ? 30 : limit.includes('>=4h') ? 240 : 0
  return required > 0 && (minutesByInterval[interval] || required) < required
}
