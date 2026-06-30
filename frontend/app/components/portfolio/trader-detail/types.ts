import type { TFunction } from 'i18next'

export interface RateLimitData {
  cumVlm: number
  nRequestsUsed: number
  nRequestsCap: number
  remaining: number
  usagePercent: number
  isOverLimit: boolean
}

export type AccountDetailTranslator = TFunction
export type UsageColorResolver = (percent: number) => string
