import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

// Format time to local
export function formatTime(time: string | null): string {
  if (!time) return '-'
  return dayjs.utc(time).local().format('MM-DD HH:mm')
}

// Get operation badge color
export function getOperationColor(op: string | null): 'default' | 'secondary' | 'destructive' {
  if (!op) return 'secondary'
  const opLower = op.toLowerCase()
  if (opLower === 'buy') return 'default'
  if (opLower === 'sell') return 'destructive'
  return 'secondary'
}
