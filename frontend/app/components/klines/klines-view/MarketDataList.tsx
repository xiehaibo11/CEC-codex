import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card'
import PacmanLoader from '../../ui/pacman-loader'
import { FLOW_INDICATORS, formatCompactNumber } from './constants'
import type { FlowAvailability, FlowIndicatorKey, MarketData } from './types'

interface MarketDataListProps {
  selectedSymbol: string
  marketData?: MarketData
  selectedExchange: string
  selectedPeriod: string
  flowAvailability: FlowAvailability
  selectedFlowIndicators: string[]
  onToggleFlowIndicator: (indicator: FlowIndicatorKey) => void
}

export function MarketDataList({
  selectedSymbol,
  marketData,
  selectedExchange,
  selectedPeriod,
  flowAvailability,
  selectedFlowIndicators,
  onToggleFlowIndicator,
}: MarketDataListProps) {
  const { t } = useTranslation()

  return (
    <Card className="lg:col-span-2">
      <CardHeader className="py-2">
        <CardTitle className="text-sm">{t('kline.marketData', 'Market Data')}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-2">
        {selectedSymbol && (
          <div className="grid grid-cols-3 gap-2">
            {marketData ? (
              <>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.markPrice', 'Mark Price')}</p>
                  <p className="text-sm font-semibold">{marketData.price.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.oraclePrice', 'Oracle Price')}</p>
                  <p className="text-sm font-semibold">{marketData.oracle_price.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.change24h', '24h Change')}</p>
                  <p className={`text-sm font-semibold ${marketData.change24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {marketData.percentage24h >= 0 ? '+' : ''}{marketData.percentage24h.toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.volume24h', '24h Volume')}</p>
                  <p className="text-sm font-semibold">${formatCompactNumber(marketData.volume24h)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.openInterest', 'Open Interest')}</p>
                  <p className="text-sm font-semibold">${formatCompactNumber(marketData.open_interest)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('kline.fundingRate', 'Funding Rate')}</p>
                  <p className="text-sm font-semibold">{(marketData.funding_rate * 100).toFixed(4)}%</p>
                </div>
              </>
            ) : (
              <div className="col-span-full text-center text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <PacmanLoader className="w-12 h-6" />
                  <span className="text-xs">{t('common.loading', 'Loading...')}</span>
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-2 pt-2 border-t">
          <span className="text-xs text-muted-foreground font-medium">{t('kline.flow', 'Flow')}</span>
          <div className="flex gap-1.5 flex-wrap">
            {FLOW_INDICATORS.map(({ key, label }) => {
              const isAvailable = flowAvailability[key]
              return (
                <button
                  key={key}
                  disabled={!isAvailable}
                  title={!isAvailable ? t('kline.indicatorUnavailable', 'Not available for {{exchange}} at {{period}}', { exchange: selectedExchange, period: selectedPeriod }) : undefined}
                  onClick={() => isAvailable && onToggleFlowIndicator(key)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    !isAvailable
                      ? 'opacity-40 cursor-not-allowed border border-muted'
                      : selectedFlowIndicators.includes(key)
                        ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                        : 'hover:bg-muted border'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
