export function formatFlow(v: number) {
  const abs = Math.abs(v)
  if (abs >= 1e6) return `${v > 0 ? '+' : ''}${(v / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${v > 0 ? '+' : ''}${(v / 1e3).toFixed(0)}K`
  return `${v > 0 ? '+' : ''}${v.toFixed(0)}`
}

export function toLocalTime(val?: string | number | null): string {
  if (!val) return ''
  const d = typeof val === 'number' ? new Date(val) : new Date(val)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
}
