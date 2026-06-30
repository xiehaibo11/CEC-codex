import { useEffect, useState } from 'react'
import AiAttributionChatModal from './AiAttributionChatModal'
import TradeReplayModal from './TradeReplayModal'
import { TradingAccount, checkPnlSyncStatus, updateArenaPnl } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import {
  fetchAccounts,
  fetchByDimension,
  fetchProgramByDimension,
  fetchSummary,
  fetchTrades,
} from './attribution-analysis/api'
import DimensionTabs from './attribution-analysis/DimensionTabs'
import FiltersBar from './attribution-analysis/FiltersBar'
import NoticeCard from './attribution-analysis/NoticeCard'
import SummaryCards from './attribution-analysis/SummaryCards'
import SyncNotice from './attribution-analysis/SyncNotice'
import type {
  Account,
  DimensionResponse,
  SummaryResponse,
  TradeDetail,
} from './attribution-analysis/types'

export default function AttributionAnalysis() {
  const { loading: authLoading } = useAuth()

  // Filter states
  const [environment, setEnvironment] = useState<string>('mainnet')
  const [exchange, setExchange] = useState<string>('all')
  const [accountId, setAccountId] = useState<string>('all')
  const [timeRange, setTimeRange] = useState<string>('all')

  // Data states
  const [accounts, setAccounts] = useState<Account[]>([])
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [bySymbol, setBySymbol] = useState<DimensionResponse | null>(null)
  const [byStrategy, setByStrategy] = useState<DimensionResponse | null>(null)
  const [byTrigger, setByTrigger] = useState<DimensionResponse | null>(null)
  const [byOperation, setByOperation] = useState<DimensionResponse | null>(null)
  const [byFactor, setByFactor] = useState<DimensionResponse | null>(null)
  const [progBySymbol, setProgBySymbol] = useState<DimensionResponse | null>(null)
  const [progByProgram, setProgByProgram] = useState<DimensionResponse | null>(null)
  const [progByTrigger, setProgByTrigger] = useState<DimensionResponse | null>(null)
  const [progByOperation, setProgByOperation] = useState<DimensionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [showNotice, setShowNotice] = useState(true)
  const [aiChatOpen, setAiChatOpen] = useState(false)

  // PnL sync status
  const [needsSync, setNeedsSync] = useState(false)
  const [unsyncCount, setUnsyncCount] = useState(0)
  const [syncing, setSyncing] = useState(false)

  // Trade details states
  const [activeTab, setActiveTab] = useState('dimensions')
  const [trades, setTrades] = useState<TradeDetail[]>([])
  const [, setTradesTotal] = useState(0)
  const [tradesLoading, setTradesLoading] = useState(false)
  const [tagFilter, setTagFilter] = useState<string | null>(null)
  const [replayOpen, setReplayOpen] = useState(false)
  const [replayTradeId, setReplayTradeId] = useState<number | null>(null)

  // Load accounts after auth initializes
  useEffect(() => {
    if (authLoading) return
    fetchAccounts().then(setAccounts).catch(console.error)
  }, [authLoading])

  // Check PnL sync status when environment changes
  useEffect(() => {
    checkPnlSyncStatus(environment)
      .then(status => {
        setNeedsSync(status.needs_sync)
        setUnsyncCount(status.unsync_count)
      })
      .catch(console.error)
  }, [environment])

  // Load data when filters change
  useEffect(() => {
    loadData()
  }, [environment, exchange, accountId, timeRange])

  // Load trades when tab changes to 'trades' or filter changes
  useEffect(() => {
    if (activeTab === 'trades') {
      loadTrades(tagFilter)
    }
  }, [activeTab, tagFilter, environment, exchange, accountId, timeRange])

  const buildParams = () => {
    const params = new URLSearchParams()
    params.set('environment', environment)
    params.set('exchange', exchange)
    if (accountId !== 'all') params.set('account_id', accountId)

    // Calculate date range based on timeRange
    const now = new Date()
    let startDate: Date | null = null

    if (timeRange === 'today') {
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    } else if (timeRange === 'week') {
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7)
    } else if (timeRange === 'month') {
      startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate())
    }

    if (startDate) {
      params.set('start_date', startDate.toISOString().split('T')[0])
      params.set('end_date', now.toISOString().split('T')[0])
    }

    return params
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const params = buildParams()
      const safe = <T,>(p: Promise<T>, fallback: T): Promise<T> =>
        p.catch(() => fallback)
      const emptyDim: DimensionResponse = { items: [], unattributed: { count: 0, metrics: null } }
      const [
        summaryData,
        symbolData,
        strategyData,
        triggerData,
        operationData,
        factorData,
        progSymbolData,
        progProgramData,
        progTriggerData,
        progOperationData,
      ] = await Promise.all([
        safe(fetchSummary(params), null),
        safe(fetchByDimension('symbol', params), emptyDim),
        safe(fetchByDimension('strategy', params), emptyDim),
        safe(fetchByDimension('trigger-type', params), emptyDim),
        safe(fetchByDimension('operation', params), emptyDim),
        safe(fetchByDimension('factor', params), emptyDim),
        safe(fetchProgramByDimension('symbol', params), emptyDim),
        safe(fetchProgramByDimension('program', params), emptyDim),
        safe(fetchProgramByDimension('trigger-type', params), emptyDim),
        safe(fetchProgramByDimension('operation', params), emptyDim),
      ])

      if (summaryData) setSummary(summaryData)
      setBySymbol(symbolData)
      setByStrategy(strategyData)
      setByTrigger(triggerData)
      setByOperation(operationData)
      setByFactor(factorData)
      setProgBySymbol(progSymbolData)
      setProgByProgram(progProgramData)
      setProgByTrigger(progTriggerData)
      setProgByOperation(progOperationData)
    } catch (error) {
      console.error('Failed to load analytics data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadTrades = async (filter?: string | null) => {
    setTradesLoading(true)
    try {
      const params = buildParams()
      if (filter) params.set('tag_filter', filter)
      const data = await fetchTrades(params)
      setTrades(data.trades)
      setTradesTotal(data.total)
    } catch (error) {
      console.error('Failed to load trades:', error)
    } finally {
      setTradesLoading(false)
    }
  }

  const handleSyncPnl = async () => {
    setSyncing(true)
    try {
      await updateArenaPnl()
      const status = await checkPnlSyncStatus(environment)
      setNeedsSync(status.needs_sync)
      setUnsyncCount(status.unsync_count)
      await loadData()
    } catch (error) {
      console.error('Failed to sync PnL:', error)
    } finally {
      setSyncing(false)
    }
  }

  const handleReplayTrade = (tradeId: number) => {
    setReplayTradeId(tradeId)
    setReplayOpen(true)
  }

  return (
    <div className="flex-1 p-4 space-y-4 overflow-auto">
      {showNotice && <NoticeCard onDismiss={() => setShowNotice(false)} />}

      {needsSync && (
        <SyncNotice
          unsyncCount={unsyncCount}
          syncing={syncing}
          onSync={handleSyncPnl}
        />
      )}

      <FiltersBar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        exchange={exchange}
        onExchangeChange={setExchange}
        environment={environment}
        onEnvironmentChange={setEnvironment}
        accountId={accountId}
        onAccountIdChange={setAccountId}
        accounts={accounts}
        onOpenAiChat={() => setAiChatOpen(true)}
      />

      {loading ? (
        <div className="text-center py-8 text-muted-foreground">Loading...</div>
      ) : (
        <>
          <SummaryCards summary={summary} />
          <DimensionTabs
            activeTab={activeTab}
            onActiveTabChange={setActiveTab}
            accountId={accountId}
            exchange={exchange}
            tagFilter={tagFilter}
            onTagFilterChange={setTagFilter}
            trades={trades}
            tradesLoading={tradesLoading}
            onReplayTrade={handleReplayTrade}
            bySymbol={bySymbol}
            byStrategy={byStrategy}
            byTrigger={byTrigger}
            byOperation={byOperation}
            byFactor={byFactor}
            progBySymbol={progBySymbol}
            progByProgram={progByProgram}
            progByTrigger={progByTrigger}
            progByOperation={progByOperation}
          />
        </>
      )}

      <AiAttributionChatModal
        open={aiChatOpen}
        onOpenChange={setAiChatOpen}
        accounts={accounts as unknown as TradingAccount[]}
        accountsLoading={false}
      />

      <TradeReplayModal
        open={replayOpen}
        onOpenChange={setReplayOpen}
        tradeId={replayTradeId}
      />
    </div>
  )
}
