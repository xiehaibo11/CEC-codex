import type { TradingAccount } from '@/lib/api'

export function readInitialPromptViewId(): number | null {
  const hash = window.location.hash
  const hashParamIndex = hash.indexOf('?')

  if (hashParamIndex === -1) {
    return null
  }

  const hashParams = new URLSearchParams(hash.slice(hashParamIndex))
  const viewId = hashParams.get('view')

  if (!viewId) {
    return null
  }

  const numId = Number(viewId)
  if (isNaN(numId)) {
    return null
  }

  window.history.replaceState({}, '', window.location.pathname + hash.slice(0, hashParamIndex))
  return numId
}

export function getAiAccountOptions(accounts: TradingAccount[]): TradingAccount[] {
  return accounts
    .filter((account) => account.account_type === 'AI')
    .sort((a, b) => a.name.localeCompare(b.name))
}
