import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ExchangeIcon from '@/components/exchange/ExchangeIcon'
import { CoinIcon } from '@/components/ui/coin-icon'
import type { WatchlistSettingsTabProps } from './types'

export function WatchlistSettingsTab({
  t,
  availableSymbols,
  watchlistSymbols,
  maxSymbols,
  loading,
  saving,
  error,
  success,
  searchQuery,
  onSearchQueryChange,
  onToggleSymbol,
  onSave,
}: WatchlistSettingsTabProps) {
  const filteredSymbols = searchQuery.trim()
    ? availableSymbols.filter((sym) => {
        const query = searchQuery.toUpperCase()
        return sym.name?.toUpperCase().includes(query) || sym.symbol?.toUpperCase().includes(query)
      })
    : availableSymbols

  return (
    <div className="space-y-6">
      {/* Binance Watchlist */}
      <Card>
        <CardHeader className="shrink-0 pb-3">
          <div className="flex items-center gap-2">
            <ExchangeIcon exchangeId="binance" size={24} />
            <CardTitle className="text-base">Binance</CardTitle>
          </div>
          <CardDescription className="text-xs">
            {t('settings.selectedCount', 'Selected')}: {watchlistSymbols.length} / {maxSymbols}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          {loading ? (
            <div className="text-muted-foreground text-sm">{t('common.loading', 'Loading...')}</div>
          ) : (
            <>
              {/* Search input */}
              <div className="mb-3">
                <Input
                  type="text"
                  placeholder={t('settings.searchSymbol', 'Search symbol...')}
                  value={searchQuery}
                  onChange={(e) => onSearchQueryChange(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
                {filteredSymbols.map((sym) => {
                  const symbolName = sym.name || sym.symbol || ''
                  const isSelected = watchlistSymbols.includes(symbolName.toUpperCase())
                  return (
                    <Button
                      key={symbolName}
                      variant={isSelected ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs gap-1.5"
                      onClick={() => onToggleSymbol(symbolName)}
                    >
                      <CoinIcon symbol={symbolName} size={14} />
                      {symbolName}
                    </Button>
                  )
                })}
              </div>
            </>
          )}
        </CardContent>
        <CardFooter className="shrink-0 border-t pt-3 flex items-center gap-3">
          <Button
            size="sm"
            onClick={onSave}
            disabled={saving || loading}
          >
            {saving ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
          </Button>
          {error && <span className="text-red-500 text-xs">{error}</span>}
          {success && <span className="text-green-500 text-xs">{success}</span>}
        </CardFooter>
      </Card>
    </div>
  )
}
