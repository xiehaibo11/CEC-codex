/** Formatting helpers for the live event-contract paper trader dashboard card.
 * Backend timestamps are naive-UTC ISO strings (no offset) - appending `Z`
 * mirrors the convention already used in TradesTable.tsx. */

export function parseUtcMs(iso: string | null | undefined): number | null {
  if (!iso) return null
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`
  const ms = new Date(normalized).getTime()
  return Number.isNaN(ms) ? null : ms
}

export function formatCountdown(remainingMs: number): string {
  if (remainingMs <= 0) return '00:00'
  const totalSeconds = Math.floor(remainingMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function formatPnl(value: number | null | undefined): string {
  const v = value ?? 0
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}`
}
