import type { SignalTranslate } from './types'

export function parseUtcNaiveString(value?: string | null): Date | null {
  if (!value) return null
  const normalized = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatWalletRuntimeTime(value?: string | null): string {
  const parsed = parseUtcNaiveString(value)
  return parsed ? parsed.toLocaleString() : '-'
}

export function formatWalletTier(t: SignalTranslate, tier?: string | null): string {
  return tier || t('signals.walletTracking.planUnknown', 'Unknown')
}

export function formatWalletEventType(t: SignalTranslate, eventType: string): string {
  switch (eventType) {
    case 'position_change':
      return t('signals.walletTracking.eventTypePositionChange', 'Position Change')
    case 'equity_change':
      return t('signals.walletTracking.eventTypeEquityChange', 'Equity Change')
    case 'fill':
      return t('signals.walletTracking.eventTypeFill', 'Trade Fill')
    case 'funding':
      return t('signals.walletTracking.eventTypeFunding', 'Funding')
    case 'transfer':
      return t('signals.walletTracking.eventTypeTransfer', 'Transfer')
    case 'liquidation':
      return t('signals.walletTracking.eventTypeLiquidation', 'Liquidation')
    default:
      return eventType
  }
}

export function formatWalletActionLabel(t: SignalTranslate, action?: string | null): string {
  switch (action) {
    case 'open':
      return t('signals.walletTracking.actionOpen', 'Opened')
    case 'add':
      return t('signals.walletTracking.actionAdd', 'Increased')
    case 'reduce':
      return t('signals.walletTracking.actionReduce', 'Reduced')
    case 'close':
      return t('signals.walletTracking.actionClose', 'Closed')
    case 'flip':
      return t('signals.walletTracking.actionFlip', 'Flipped')
    case 'update':
      return t('signals.walletTracking.actionUpdate', 'Updated')
    default:
      return action || '-'
  }
}

export function formatWalletDirectionLabel(t: SignalTranslate, direction?: string | null): string {
  switch (direction) {
    case 'long':
      return t('signals.walletTracking.directionLong', 'Long')
    case 'short':
      return t('signals.walletTracking.directionShort', 'Short')
    case 'flat':
      return t('signals.walletTracking.directionFlat', 'Flat')
    default:
      return direction || '-'
  }
}

export function formatWalletMetricValue(value: unknown, digits = 2): string | null {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

export function formatShortAddress(address?: string | null): string {
  if (!address) return '-'
  if (address.length <= 14) return address
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

export function sortByCreatedAtDesc<T extends { created_at?: string | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aTime = parseUtcNaiveString(a.created_at)?.getTime() || 0
    const bTime = parseUtcNaiveString(b.created_at)?.getTime() || 0
    return bTime - aTime
  })
}
