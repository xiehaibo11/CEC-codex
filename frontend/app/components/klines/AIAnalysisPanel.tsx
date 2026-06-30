import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Textarea } from '../ui/textarea'
import PacmanLoader from '../ui/pacman-loader'
import { getBinancePositions, getHyperliquidPositions } from '@/lib/hyperliquidApi'
import { AnalysisResultCard } from './ai-analysis-panel/AnalysisResultCard'
import { FullAnalysisDialog } from './ai-analysis-panel/FullAnalysisDialog'
import { RiskPanel } from './ai-analysis-panel/RiskPanel'
import { SignalList } from './ai-analysis-panel/SignalList'
import {
  KLINE_LIMIT_OPTIONS,
  computeMA,
  createMarketDataPayload,
  createPositionPayload,
  mapExchangePosition,
} from './ai-analysis-panel/formatters'
import type {
  AIAnalysisPanelProps,
  AITrader,
  AnalysisResult,
  PositionItem,
  WalletOption,
} from './ai-analysis-panel/types'

export default function AIAnalysisPanel({
  symbol,
  period,
  klines,
  indicators,
  marketData,
  selectedIndicators = [],
  selectedFlowIndicators = [],
  onAnalysisComplete
}: AIAnalysisPanelProps) {
  const { t } = useTranslation()
  const [selectedTrader, setSelectedTrader] = useState<string>('')
  const [userMessage, setUserMessage] = useState<string>('')
  const [traders, setTraders] = useState<AITrader[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [showFullAnalysis, setShowFullAnalysis] = useState(false)
  const [tradersLoaded, setTradersLoaded] = useState(false)
  const [tradersLoading, setTradersLoading] = useState(false)
  const [klineLimit, setKlineLimit] = useState<number>(100)
  const [selectedWallet, setSelectedWallet] = useState<WalletOption | null>(null)
  const [positions, setPositions] = useState<PositionItem[]>([])
  const [positionsLoading, setPositionsLoading] = useState(false)
  const [indicatorLoading] = useState(false)
  const [showPrompt, setShowPrompt] = useState(false)

  // Fetch AI Traders list
  const fetchTraders = async () => {
    if (tradersLoaded) return

    try {
      setTradersLoading(true)
      // Use public account list endpoint (no auth cookie required)
      const response = await fetch('/api/account/list')
      const data = await response.json()
      const accounts: any[] = Array.isArray(data)
        ? data
        : Array.isArray((data as any)?.accounts)
          ? (data as any).accounts
          : []

      const aiTraders = accounts.filter((acc: any) => {
        const isActive = acc.is_active === true || acc.is_active === 'true'
        return acc.account_type === 'AI' && isActive
      }) || []
      setTraders(aiTraders)
      setTradersLoaded(true)
    } catch (error) {
      console.error('Failed to fetch AI traders:', error)
    } finally {
      setTradersLoading(false)
    }
  }

  // 预加载 trader 列表，避免首次打开等待
  useEffect(() => {
    fetchTraders()
  }, [])

  // 加载选中钱包的仓位
  useEffect(() => {
    const loadPositions = async () => {
      if (!selectedWallet) {
        setPositions([])
        return
      }
      try {
        setPositionsLoading(true)
        const data = selectedWallet.exchange === 'binance'
          ? await getBinancePositions(selectedWallet.account_id, selectedWallet.environment)
          : await getHyperliquidPositions(selectedWallet.account_id, selectedWallet.environment)
        const mapped = (data.positions || []).map((position: any) => mapExchangePosition(position, symbol))
        setPositions(mapped)
      } catch (err) {
        console.error('Failed to load positions:', err)
        setPositions([])
      } finally {
        setPositionsLoading(false)
      }
    }
    loadPositions()
  }, [selectedWallet])

  // Execute AI Analysis
  const handleAnalyze = async () => {
    if (!selectedTrader || !symbol || !klines.length || indicatorLoading) return

    setLoading(true)
    setResult(null)

    // Record request start time for later retrieval if connection drops
    const requestStartTime = new Date()

    try {
      const slicedKlines = klines.slice(-klineLimit)

      const ma5 = computeMA(slicedKlines, 5)
      const ma10 = computeMA(slicedKlines, 10)
      const ma20 = computeMA(slicedKlines, 20)
      const positionPayload = createPositionPayload(positions)
      const marketDataPayload = createMarketDataPayload(marketData)

      const requestData = {
        account_id: parseInt(selectedTrader),
        symbol,
        period,
        kline_limit: klineLimit,
        klines: slicedKlines.map(k => ({
          time: k.time,
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
          volume: k.volume || 0
        })),
        indicators: {
          // 直接携带现有指标
          ...indicators,
          // 补充前端计算的MA（如果后端未返回）
          ...(indicators?.MA5 && indicators.MA5.length ? {} : { MA5: ma5 }),
          ...(indicators?.MA10 && indicators.MA10.length ? {} : { MA10: ma10 }),
          ...(indicators?.MA20 && indicators.MA20.length ? {} : { MA20: ma20 }),
        },
        market_data: marketDataPayload,
        positions: positionPayload,
        selected_flow_indicators: selectedFlowIndicators,
        user_message: userMessage.trim() || null,
        prompt_snapshot: JSON.stringify({
          symbol,
          period,
          kline_limit: klineLimit,
          indicators: Object.keys(indicators || {}),
          flow_indicators: selectedFlowIndicators,
          positions: positionPayload,
          market_data: marketDataPayload,
          user_message: userMessage.trim() || null
        }, null, 2)
      }

      // Create AbortController with 10-minute timeout for AI analysis
      // Reasoning models (like deepseek-v4-pro) can be very slow
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 600000) // 10 minutes

      try {
        const response = await fetch('/api/klines/ai-analysis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestData),
          signal: controller.signal
        })

        clearTimeout(timeoutId)
        const data = await response.json()
        setResult(data)

        if (data.success && onAnalysisComplete) {
          onAnalysisComplete()
        }
      } catch (fetchError: any) {
        clearTimeout(timeoutId)
        console.error('Analysis failed:', fetchError)

        // If connection was closed but backend might have saved the result, try to retrieve it
        if (fetchError instanceof TypeError && fetchError.message.includes('fetch')) {
          console.log('Connection interrupted, attempting to retrieve saved result...')

          try {
            // Wait 2 seconds for backend to finish saving to database
            await new Promise(resolve => setTimeout(resolve, 2000))

            // Fetch recent analysis history for this symbol (get last 5 to be safe)
            const historyResponse = await fetch(
              `/api/klines/ai-analysis/history?symbol=${symbol}&limit=5`
            )

            if (historyResponse.ok) {
              const historyData = await historyResponse.json()

              // Find the analysis that matches this request by time range, symbol, and period
              if (historyData.history && historyData.history.length > 0) {
                const matchedAnalysis = historyData.history.find((item: any) => {
                  const analysisTime = new Date(item.created_at)
                  const timeDiffMs = analysisTime.getTime() - requestStartTime.getTime()

                  // Check if analysis was created within 3 minutes after request started
                  // and matches symbol + period
                  return (
                    timeDiffMs >= 0 &&
                    timeDiffMs < 180000 && // 3 minutes
                    item.symbol === symbol &&
                    item.period === period
                  )
                })

                if (matchedAnalysis) {
                  // Found the result! Display it
                  console.log('Successfully retrieved saved analysis result:', matchedAnalysis.id)
                  setResult({
                    success: true,
                    analysis_id: matchedAnalysis.id,
                    symbol: matchedAnalysis.symbol,
                    period: matchedAnalysis.period,
                    model: matchedAnalysis.model_used,
                    analysis: matchedAnalysis.analysis,
                    created_at: matchedAnalysis.created_at
                  })
                  return
                }

                console.log('No matching analysis found in history within expected time range')
              }
            }
          } catch (retrieveError) {
            console.error('Failed to retrieve saved result:', retrieveError)
          }
        }

        // Provide more specific error messages
        let errorMessage = 'Network error occurred'
        if (fetchError.name === 'AbortError') {
          errorMessage = 'Analysis timeout (10 minutes). Please try again with fewer K-lines or a simpler question.'
        }

        setResult({
          success: false,
          error: errorMessage
        })
      }
    } catch (error) {
      console.error('Analysis failed:', error)
      setResult({
        success: false,
        error: 'Failed to prepare analysis request'
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      {/* AI Trader Selection */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">{t('kline.analysis.aiTrader', 'AI Trader')}</label>
        <Select
          value={selectedTrader}
          onValueChange={setSelectedTrader}
          onOpenChange={(open) => open && fetchTraders()}
        >
          <SelectTrigger>
            <SelectValue placeholder={t('kline.analysis.selectAiTrader', 'Select AI Trader')} />
          </SelectTrigger>
          <SelectContent>
            {tradersLoading && traders.length === 0 && (
              <SelectItem value="loading" disabled>
                {t('kline.analysis.loadingTraders', 'Loading AI Traders...')}
              </SelectItem>
            )}
            {traders.map(trader => (
              <SelectItem key={trader.id} value={trader.id.toString()}>
                {trader.name} ({trader.model})
              </SelectItem>
            ))}
            {!tradersLoading && traders.length === 0 && (
              <SelectItem value="empty" disabled>
                {t('kline.analysis.noTraders', 'No AI Traders found')}
              </SelectItem>
            )}
          </SelectContent>
        </Select>
      </div>

      {/* K-line data length */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">{t('kline.analysis.klineLength', 'K-line Data Length')}</label>
        <Select value={klineLimit.toString()} onValueChange={(v) => setKlineLimit(parseInt(v))}>
          <SelectTrigger>
            <SelectValue placeholder={t('kline.analysis.selectLength', 'Select length')} />
          </SelectTrigger>
          <SelectContent>
            {KLINE_LIMIT_OPTIONS.map(len => (
              <SelectItem key={len} value={len.toString()}>
                {t('kline.analysis.lastCandles', 'Last {{count}} candles').replace('{{count}}', len.toString())}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-[11px] text-muted-foreground mt-1">{t('kline.analysis.candlesHint', 'More candles give AI more context (500 may be slower).')}</p>
      </div>

      <SignalList
        selectedIndicators={selectedIndicators}
        selectedFlowIndicators={selectedFlowIndicators}
      />

      <RiskPanel
        symbol={symbol}
        selectedWallet={selectedWallet}
        positions={positions}
        positionsLoading={positionsLoading}
        onSelectWallet={setSelectedWallet}
      />

      {/* Custom Question */}
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">{t('kline.analysis.customQuestion', 'Custom Question (Optional)')}</label>
        <Textarea
          placeholder={t('kline.analysis.questionPlaceholder', 'e.g., Should I go long now? Where are the support levels?')}
          value={userMessage}
          onChange={(e) => setUserMessage(e.target.value)}
          rows={3}
          className="text-sm"
        />
      </div>

      {/* Analysis Button */}
      <Button
        onClick={handleAnalyze}
        disabled={!selectedTrader || loading || !klines.length}
        className="w-full"
        size="sm"
      >
        {loading ? (
          <div className="flex items-center gap-2">
            <PacmanLoader className="w-4 h-4" />
            {t('kline.analysis.analyzing', 'Analyzing...')}
          </div>
        ) : (
          t('kline.analysis.aiAnalysis', 'AI Analysis')
        )}
      </Button>

      {/* Analysis Result */}
      {result && (
        <AnalysisResultCard
          result={result}
          onViewFull={() => setShowFullAnalysis(true)}
        />
      )}

      {/* Full Analysis Dialog */}
      <FullAnalysisDialog
        open={showFullAnalysis}
        onOpenChange={setShowFullAnalysis}
        symbol={symbol}
        period={period}
        result={result}
        showPrompt={showPrompt}
        onTogglePrompt={() => setShowPrompt(!showPrompt)}
      />
    </div>
  )
}
