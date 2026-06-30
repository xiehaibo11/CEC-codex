import { MACD_EVENT_TYPES, METRICS, OPERATORS } from './constants'
import type { TriggerCondition } from './types'

export function formatCondition(cond: TriggerCondition): string {
  const metric = cond.metric?.startsWith('factor:')
    ? `⚗ ${cond.metric.split(':')[1]}`
    : METRICS.find(m => m.value === cond.metric)?.label || cond.metric

  if (cond.metric === 'taker_volume') {
    const dir = (cond as any).direction || 'any'
    const ratio = (cond as any).ratio_threshold || 1.5
    const vol = ((cond as any).volume_threshold || 0).toLocaleString()
    return `${metric} | ${dir.toUpperCase()} ≥${ratio} Vol≥$${vol} (${cond.time_window})`
  }

  if (cond.metric === 'macd') {
    const events = (cond as any).event_types || []
    const eventLabels = events.map((event: string) => {
      const found = MACD_EVENT_TYPES.find(item => item.value === event)
      return found ? found.label : event
    }).join(', ')
    return `${metric} | ${eventLabels || 'No events'} (${cond.time_window})`
  }

  const op = OPERATORS.find(operator => operator.value === cond.operator)?.label || cond.operator
  return `${metric} ${op} ${cond.threshold} (${cond.time_window})`
}
