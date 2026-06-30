import { ArenaAccountMeta, ArenaAnalyticsAccount } from '@/lib/api'
import { formatDateTime } from '@/lib/dateTime'

export function formatCurrency(value?: number | null, minimumFractionDigits = 2) {
  if (value === undefined || value === null) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits,
    maximumFractionDigits: Math.max(minimumFractionDigits, 2),
  })
}

export function formatSignedCurrency(value?: number | null) {
  if (value === undefined || value === null) return '—'
  const absolute = formatCurrency(Math.abs(value))
  const prefix = value >= 0 ? '+' : '-'
  return `${prefix}$${absolute}`
}

export function formatPercent(value?: number | null, fractionDigits = 2) {
  if (value === undefined || value === null) return '—'
  return `${(value * 100).toFixed(fractionDigits)}%`
}

export function formatDecimal(value?: number | null, fractionDigits = 2) {
  if (value === undefined || value === null) return '—'
  return value.toFixed(fractionDigits)
}

// Use formatDateTime from @/lib/dateTime with 'short' style for compact display
export const formatDate = (value?: string | null) => formatDateTime(value, { style: 'short' })

export function getTrendColor(value?: number | null) {
  if (value === undefined || value === null) return 'text-foreground'
  if (value > 0) return 'text-emerald-500'
  if (value < 0) return 'text-red-500'
  return 'text-foreground'
}

export function formatMinutes(value?: number | null) {
  if (value === undefined || value === null) return '—'
  if (value < 1) return '<1m'
  const rounded = Math.round(value)
  if (rounded < 60) return `${rounded}m`
  const hours = Math.floor(rounded / 60)
  const minutes = rounded % 60
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

export function buildAccountsMeta(accounts: ArenaAnalyticsAccount[]): ArenaAccountMeta[] {
  return accounts.map((account) => ({
    account_id: account.account_id,
    name: account.account_name,
    model: account.model ?? null,
  }))
}
