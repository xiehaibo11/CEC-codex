import { AlertTriangle, TrendingUp } from 'lucide-react'
import type { SummaryTranslator } from './types'

export const getMarginStatus = (percent: number, t: SummaryTranslator) => {
  if (percent < 50) {
    return {
      color: 'bg-green-500',
      text: t('account.marginHealthy', 'Healthy'),
      icon: TrendingUp,
      textColor: 'text-green-600',
      dotColor: 'bg-green-500',
    } as const
  }
  if (percent < 75) {
    return {
      color: 'bg-yellow-500',
      text: t('account.marginModerate', 'Moderate'),
      icon: AlertTriangle,
      textColor: 'text-yellow-600',
      dotColor: 'bg-yellow-500',
    } as const
  }
  return {
    color: 'bg-red-500',
    text: t('account.marginHighRisk', 'High Risk'),
    icon: AlertTriangle,
    textColor: 'text-red-600',
    dotColor: 'bg-red-500',
  } as const
}

export const getApiUsageColor = (usagePercent: number) => {
  if (usagePercent >= 90) return 'text-red-600'
  if (usagePercent >= 70) return 'text-yellow-600'
  return 'text-green-600'
}
