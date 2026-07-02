import { useCallback, useMemo, useState } from 'react'
import { Card } from '@/components/ui/card'
import { useTradingMode } from '@/contexts/TradingModeContext'
import {
  applyLiveAccountTotals,
  buildAccountMeta,
  buildBaseProcessedData,
  buildYAxisDomain,
} from './asset-curve/assetCurveProcessing'
import { AssetCurveChart } from './asset-curve/AssetCurveChart'
import { AssetRankingGrid } from './asset-curve/AssetRankingGrid'
import { useAssetCurveData } from './asset-curve/useAssetCurveData'
import { DEFAULT_TIMEFRAME } from './asset-curve/types'
import type { AssetCurveProps } from './asset-curve/types'

export default function AssetCurve({
  data: initialData,
  wsRef,
  highlightAccountId,
  onHighlightAccountChange,
}: AssetCurveProps) {
  const { tradingMode } = useTradingMode()
  const timeframe = DEFAULT_TIMEFRAME
  const [hoveredAccountId, setHoveredAccountId] = useState<number | null>(null)
  const { data, loading, error, liveAccountTotals, logoPulseMap } = useAssetCurveData({
    initialData,
    wsRef,
    timeframe,
    tradingMode,
  })

  const baseProcessedData = useMemo(() => buildBaseProcessedData(data), [data])
  const processedData = useMemo(
    () => applyLiveAccountTotals(baseProcessedData, liveAccountTotals),
    [baseProcessedData, liveAccountTotals],
  )
  const { chartData, accountSummaries, uniqueUsers, rankedAccounts } = processedData

  const handleLegendClick = useCallback(
    (accountId: number | 'all') => {
      if (!onHighlightAccountChange) return
      const current = highlightAccountId ?? 'all'
      onHighlightAccountChange(current === accountId ? 'all' : accountId)
    },
    [highlightAccountId, onHighlightAccountChange],
  )

  const handleChartClick = useCallback(() => {
    if (highlightAccountId && highlightAccountId !== 'all') {
      onHighlightAccountChange?.('all')
    }
  }, [highlightAccountId, onHighlightAccountChange])

  const activeLegendAccountId =
    highlightAccountId && highlightAccountId !== 'all' ? highlightAccountId : null
  const yAxisDomain = useMemo(
    () => buildYAxisDomain(chartData, uniqueUsers, accountSummaries, activeLegendAccountId),
    [chartData, uniqueUsers, accountSummaries, activeLegendAccountId],
  )
  const accountMeta = useMemo(
    () => buildAccountMeta(uniqueUsers, accountSummaries),
    [uniqueUsers, accountSummaries],
  )

  if (!data || data.length === 0) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center h-96">
          <div className="text-muted-foreground">
            {loading ? 'Loading...' : error || 'No asset data available'}
          </div>
        </div>
      </Card>
    )
  }

  return (
    <div className="p-6 h-full min-h-0 flex flex-col gap-6">
      <div className="flex-1 min-h-0 flex flex-col gap-4">
        <AssetCurveChart
          chartData={chartData}
          accountSummaries={accountSummaries}
          uniqueUsers={uniqueUsers}
          accountMeta={accountMeta}
          yAxisDomain={yAxisDomain}
          activeLegendAccountId={activeLegendAccountId}
          hoveredAccountId={hoveredAccountId}
          logoPulseMap={logoPulseMap}
          loading={loading}
          onChartClick={handleChartClick}
          onHoverAccount={setHoveredAccountId}
          onLegendClick={handleLegendClick}
        />
      </div>
      <AssetRankingGrid
        rankedAccounts={rankedAccounts}
        highlightAccountId={highlightAccountId}
      />
    </div>
  )
}
