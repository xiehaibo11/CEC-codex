import FlipNumber from '../FlipNumber'
import { formatAccountName } from './assetCurveProcessing'
import type { AccountSummary } from './types'

interface AssetRankingGridProps {
  rankedAccounts: AccountSummary[]
  highlightAccountId?: number | 'all'
}

export function AssetRankingGrid({
  rankedAccounts,
  highlightAccountId,
}: AssetRankingGridProps) {
  return (
    <div className="mt-6">
      <div className="text-xs font-medium mb-3 text-secondary-foreground">
        AI Trader Asset Ranking
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {rankedAccounts.map((account, index) => {
          const isMuted =
            highlightAccountId &&
            highlightAccountId !== 'all' &&
            account.accountId !== highlightAccountId
          return (
            <div
              key={account.username}
              className="bg-white dark:bg-background border-2 border-gray-900 dark:border-gray-200 px-4 py-3 rounded-lg flex items-center gap-3 min-w-0"
            >
              {account.logo ? (
                <div
                  className="h-10 w-10 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: account.logo.color || '#656565' }}
                >
                  <img
                    src={account.logo.src}
                    alt={account.logo.alt}
                    className="h-8 w-8 rounded-full object-contain"
                    loading="lazy"
                  />
                </div>
              ) : (
                <div className="h-10 w-10 rounded-full bg-background/60 flex items-center justify-center text-sm font-semibold text-secondary-foreground">
                  {(account.username || 'NA').slice(0, 2).toUpperCase()}
                </div>
              )}
              <div className={`min-w-0 transition-opacity ${isMuted ? 'opacity-40' : ''}`}>
                <div className="text-xs font-medium text-secondary-foreground">
                  {formatAccountName(account.username)}
                </div>
                <FlipNumber
                  value={account.assets}
                  prefix="$"
                  className="text-lg font-bold text-secondary-foreground inline-flex items-center"
                />
              </div>
              <div
                className={`ml-auto text-xs font-semibold text-primary transition-opacity ${
                  isMuted ? 'opacity-40' : ''
                }`}
              >
                #{index + 1}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
