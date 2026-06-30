import { formatDateTime } from '@/lib/dateTime'

export function formatTimestamp(value?: string | null): string {
  if (!value) return 'No executions yet'
  return formatDateTime(value, { style: 'short' })
}
