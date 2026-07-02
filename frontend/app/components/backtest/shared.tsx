import type { ReactNode } from 'react'

import { Switch } from '@/components/ui/switch'

export function toLocalInputValue(date: Date) {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

export function fromLocalInputValue(value: string) {
  return new Date(value).toISOString()
}

export function formatTime(value?: string | number | null) {
  if (!value) return '-'
  const date = typeof value === 'number' ? new Date(value) : new Date(value)
  return date.toLocaleString(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatPrice(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '-'
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export function formatPct(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '-'
  return `${value.toFixed(2)}%`
}

export function formatMoney(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '-'
  return `${value >= 0 ? '+' : '-'}$${Math.abs(value).toFixed(2)}`
}

export function directionClass(direction?: string) {
  if (direction === 'long') return 'text-green-600 border-green-500 bg-green-500/10'
  if (direction === 'short') return 'text-red-600 border-red-500 bg-red-500/10'
  return 'text-muted-foreground border-border bg-muted/40'
}

export function resultClass(result?: string) {
  if (result === 'win') return 'text-green-600'
  if (result === 'loss') return 'text-red-600'
  return 'text-muted-foreground'
}

export function missingKlineCount(
  dataQuality?: { missing_bar_count?: number; sample_gaps?: Array<{ missing_bars?: number }> } | null,
) {
  if (!dataQuality) return 0
  if (typeof dataQuality.missing_bar_count === 'number') return dataQuality.missing_bar_count
  return (dataQuality.sample_gaps || []).reduce((total, gap) => total + (gap.missing_bars || 0), 0)
}

export function MetricCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string
  value: string
  icon?: ReactNode
  tone?: 'green' | 'red' | 'amber'
}) {
  const toneClass =
    tone === 'green' ? 'text-green-600' :
    tone === 'red' ? 'text-red-600' :
    tone === 'amber' ? 'text-amber-600' :
    'text-foreground'

  return (
    <div className="rounded-md border bg-card px-3 py-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <div className={`mt-1 truncate text-lg font-semibold ${toneClass}`}>{value}</div>
    </div>
  )
}

export function ToggleRow({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <label className={`flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-xs ${disabled ? 'opacity-60' : ''}`}>
      <span className="min-w-0 truncate">{label}</span>
      <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
    </label>
  )
}
