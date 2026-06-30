import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import TradingViewChart from './TradingViewChart'
import AIAnalysisPanel from './AIAnalysisPanel'
import PacmanLoader from '../ui/pacman-loader'
import { useCollectionDays } from '@/lib/useCollectionDays'
import { ChartControls } from './klines-view/ChartControls'
import { IndicatorPanel } from './klines-view/IndicatorPanel'
import { MarketDataList } from './klines-view/MarketDataList'
import { PeriodSelector } from './klines-view/PeriodSelector'
import { SymbolSelector } from './klines-view/SymbolSelector'
import { getFlowIndicatorAvailability } from './klines-view/constants'
import type { ChartType, FlowIndicatorKey, MarketData } from './klines-view/types'

interface KlinesViewProps {
  onAccountUpdated?: () => void
}

export default function KlinesView({ onAccountUpdated }: KlinesViewProps) {
  const { t } = useTranslation()
  const selectedExchange = 'binance' as const
  const collectionDays = useCollectionDays(selectedExchange)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC')
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1m')
  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>([])
  const [marketData, setMarketData] = useState<MarketData[]>([])
  const [isPageVisible, setIsPageVisible] = useState(true)
  const [chartType, setChartType] = useState<ChartType>('candlestick')
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [klinesData, setKlinesData] = useState<any[]>([])
  const [indicatorsData, setIndicatorsData] = useState<Record<string, any>>({})
  const [indicatorLoading, setIndicatorLoading] = useState(false)
  const [selectedFlowIndicators, setSelectedFlowIndicators] = useState<string[]>([])

  const marketDataIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const flowAvailability = getFlowIndicatorAvailability(selectedPeriod)

  // 页面可见性监听
  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsPageVisible(!document.hidden)
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [])

  // 获取 watchlist
  useEffect(() => {
    fetchWatchlist()
  }, [selectedExchange])

  // 获取市场数据
  useEffect(() => {
    const fetchData = async () => {
      try {
        const symbolsParam = watchlistSymbols.join(',')
        if (!symbolsParam) return

        const response = await fetch(`/api/market/prices?symbols=${symbolsParam}&market=${selectedExchange}`)
        if (!response.ok) return

        const data = await response.json()
        const formattedData = data.map((item: any) => ({
          symbol: item.symbol,
          price: item.price || 0,
          oracle_price: item.oracle_price || 0,
          change24h: item.change24h || 0,
          volume24h: item.volume24h || 0,
          percentage24h: item.percentage24h || 0,
          open_interest: item.open_interest || 0,
          funding_rate: item.funding_rate || 0
        }))
        setMarketData(formattedData)
      } catch (error) {
        console.error('Failed to fetch market data:', error)
      }
    }

    if (watchlistSymbols.length > 0 && isPageVisible) {
      fetchData()
      marketDataIntervalRef.current = setInterval(fetchData, 60000)
    }

    return () => {
      if (marketDataIntervalRef.current) {
        clearInterval(marketDataIntervalRef.current)
        marketDataIntervalRef.current = null
      }
    }
  }, [watchlistSymbols, isPageVisible, selectedExchange])

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (marketDataIntervalRef.current) {
        clearInterval(marketDataIntervalRef.current)
      }
    }
  }, [])

  const fetchWatchlist = async () => {
    try {
      const response = await fetch('/api/binance/symbols/watchlist')
      const data = await response.json()
      const symbols = data.symbols || []
      setWatchlistSymbols(symbols)
      if (symbols.length > 0 && !symbols.includes(selectedSymbol)) {
        setSelectedSymbol(symbols[0])
      }
    } catch (error) {
      console.error('Failed to fetch watchlist:', error)
    }
  }

  const getSymbolMarketData = (symbol: string) => {
    return marketData.find(data => data.symbol === symbol)
  }

  const toggleIndicator = (indicator: string) => {
    setSelectedIndicators(prev =>
      prev.includes(indicator)
        ? prev.filter(item => item !== indicator)
        : [...prev, indicator]
    )
  }

  const toggleFlowIndicator = (indicator: FlowIndicatorKey) => {
    setSelectedFlowIndicators(prev =>
      prev.includes(indicator)
        ? prev.filter(item => item !== indicator)
        : [...prev, indicator]
    )
  }

  return (
    <div className="flex flex-col md:flex-row h-full w-full gap-4 overflow-hidden pb-16 md:pb-0">
      {/* 左侧 70%：选择区 + 市场数据 + 指标 + K线图 */}
      <div className="flex flex-col flex-1 md:flex-[7] min-w-0 space-y-4 overflow-hidden">
        {/* Mobile: Simplified selector bar */}
        <div className="md:hidden flex items-center gap-2 px-2 py-2 bg-background border-b">
          <div className="flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium">
            <img src="/static/binance_logo.svg" alt="Binance" width={14} height={14} />
            Binance
          </div>
          <SymbolSelector
            value={selectedSymbol}
            symbols={watchlistSymbols}
            onChange={setSelectedSymbol}
            triggerClassName="flex-1 h-9"
          />
          <PeriodSelector
            value={selectedPeriod}
            onChange={setSelectedPeriod}
            triggerClassName="w-20 h-9"
          />
        </div>

        {/* Desktop: Full control panel */}
        <div className="hidden md:grid grid-cols-1 lg:grid-cols-6 gap-3 flex-shrink-0">
          {/* Symbol and Period Selection */}
          <Card className="lg:col-span-2">
            <CardContent className="pt-4 space-y-3">
              <div className="flex items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-xs font-medium">
                <img src="/static/binance_logo.svg" alt="Binance" width={16} height={16} />
                Binance
              </div>

              {/* Symbol and Period */}
              <div className="flex items-center gap-2">
                <SymbolSelector
                  value={selectedSymbol}
                  symbols={watchlistSymbols}
                  onChange={setSelectedSymbol}
                  triggerClassName="flex-1"
                />
                <PeriodSelector
                  value={selectedPeriod}
                  onChange={setSelectedPeriod}
                  triggerClassName="w-24 sm:w-28"
                />
              </div>

              {/* K-line environment warning - exchange specific */}
              <div className="pt-2 border-t">
                <p className="text-xs text-amber-600 font-medium flex items-center gap-1">
                  <span>⚠️</span>
                  <span>
                    {t('kline.binanceWarning', 'K-line analysis is only available for Binance Futures production environment')}
                  </span>
                </p>
                {collectionDays !== null && collectionDays > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {t('common.binanceCollectionDaysHint', 'Binance market flow data collected for {{days}} days', { days: collectionDays })}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Market Data */}
          <MarketDataList
            selectedSymbol={selectedSymbol}
            marketData={getSymbolMarketData(selectedSymbol)}
            selectedExchange={selectedExchange}
            selectedPeriod={selectedPeriod}
            flowAvailability={flowAvailability}
            selectedFlowIndicators={selectedFlowIndicators}
            onToggleFlowIndicator={toggleFlowIndicator}
          />

          {/* Technical Indicators */}
          <IndicatorPanel
            selectedIndicators={selectedIndicators}
            onToggleIndicator={toggleIndicator}
          />
        </div>

        {/* K-Line Chart Area */}
        <Card className="flex-1 min-h-[300px] md:min-h-[420px] min-w-0 overflow-hidden">
          <CardHeader className="py-2 md:py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 md:gap-3">
                <CardTitle className="text-xs md:text-sm">
                  {selectedSymbol} ({selectedPeriod})
                </CardTitle>
                {chartLoading && (
                  <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                    <PacmanLoader className="w-12 h-6" />
                    {t('kline.loadingKlineData', 'Loading K-line data...')}
                  </div>
                )}
              </div>
              {/* Chart type selector - hidden on mobile */}
              <ChartControls chartType={chartType} onChartTypeChange={setChartType} />
            </div>
          </CardHeader>
            <CardContent className="h-[calc(100%-3rem)] pb-4">
                <TradingViewChart
                  symbol={selectedSymbol}
                  period={selectedPeriod}
                  exchange={selectedExchange}
                  chartType={chartType}
                  selectedIndicators={selectedIndicators}
                  selectedFlowIndicators={selectedFlowIndicators}
                  onLoadingChange={setChartLoading}
                  onIndicatorLoadingChange={setIndicatorLoading}
                  onDataUpdate={(klines, indicators) => {
                    setKlinesData(klines || [])
                    setIndicatorsData(indicators || {})
                  }}
                />
          </CardContent>
        </Card>
      </div>

      {/* 右侧 30%：AI Analysis 独立列 - Hidden on mobile */}
      <div className="hidden md:flex flex-col flex-[3] min-w-[300px] space-y-4">
        <Card className="flex-1 overflow-hidden">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">{t('kline.aiAnalysis', 'AI Analysis')}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 h-full overflow-y-auto">
            <AIAnalysisPanel
              symbol={selectedSymbol}
              period={selectedPeriod}
              klines={klinesData}
              indicators={indicatorsData}
              marketData={getSymbolMarketData(selectedSymbol)}
              selectedIndicators={selectedIndicators}
              selectedFlowIndicators={selectedFlowIndicators}
              onAnalysisComplete={() => {}}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
