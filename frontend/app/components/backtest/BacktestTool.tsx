import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import { Bot, Loader2, Pause, Play, RefreshCw, Save } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  getAllBinanceWallets,
  runBinanceTestnetOrderProbe,
  type BinanceTestnetOrderProbeResponse,
} from '@/lib/binanceFuturesApi'
import {
  getEventContractSymbols,
  createEventContractBacktestTask,
  getCoinGlassEventContractCapability,
  getEventContractBacktestTask,
  getHyperAiProfile,
  getLatestEventContractBacktestTask,
  isAuthenticated,
  pauseEventContractBacktestTask,
  predictEventContract,
  type CoinGlassEventContractCapability,
  type EventAiDecision,
  type EventBacktestResponse,
  type EventBacktestTaskStatus,
  type EventContractBacktestConfig,
  type EventContractConfig,
  type EventContractSymbol,
  type EventFactorSnapshot,
  type EventPrediction,
  type EventTradeLog,
  type HyperAiProfile,
} from '@/lib/api'

import { BacktestConfigPanel } from './BacktestConfigPanel'
import { BacktestResultsPanel } from './BacktestResultsPanel'
import { PredictionPanel } from './PredictionPanel'
import { formatTime, fromLocalInputValue, toLocalInputValue } from './shared'
import { PERIOD_OPTIONS, PERIOD_SECONDS, PLATFORM_FORM_PRESETS, type FormState } from './types'

const BACKTEST_CONFIG_STORAGE_KEY = 'hyper-alpha-arena:backtest-tool:config:v1'
const BACKTEST_TASK_STORAGE_KEY = 'hyper-alpha-arena:backtest-tool:active-task:v1'
const BACKTEST_LAST_TASK_STORAGE_KEY = 'hyper-alpha-arena:backtest-tool:last-task:v1'
const ACTIVE_TASK_STATUSES = new Set(['pending', 'running', 'pause_requested'])

function buildDefaultForm(start: Date, end: Date): FormState {
  return {
    symbol: 'BTC',
    exchange: 'binance',
    environment: 'mainnet',
    period: '1m',
    consensus_mode: 'rule_only',
    decision_policy: 'professional_v1',
    max_ai_evaluations: 1,
    start_time: toLocalInputValue(start),
    end_time: toLocalInputValue(end),
    expiry_minutes: 5,
    initial_balance: 10000,
    stake_amount: 100,
    win_payout_ratio: 0.8,
    fee_rate: 0,
    slippage_bps: 0,
    delay_seconds: 3,
    consensus_threshold: 5,
    reviewer_panel_size: 25,
    target_win_rate: 75,
    enable_edge_quality_gate: true,
    max_trade_range_risk: 45,
    allow_pullback_trades: false,
    draw_result: 'loss',
    enable_fake_breakout_filter: true,
    enable_trap_filter: true,
    enable_range_filter: true,
    enable_multi_timeframe_filter: true,
    enable_volume_filter: true,
    enable_cvd_filter: false,
    enable_l2_features: true,
    min_l2_coverage_pct: 96,
    strict_l2_quality: true,
    enable_coinglass_features: false,
    min_coinglass_coverage_pct: 96,
    strict_coinglass_quality: true,
    coinglass_no_future_leakage: true,
    platform: 'custom' as const,
    non_overlapping_only: true,
  }
}

function loadSavedForm(defaultForm: FormState): FormState {
  if (typeof window === 'undefined') return defaultForm
  try {
    const raw = window.localStorage.getItem(BACKTEST_CONFIG_STORAGE_KEY)
    if (!raw) return defaultForm
    const parsed = JSON.parse(raw) as Partial<FormState>
    const merged = { ...defaultForm, ...parsed }
    if (!parsed.decision_policy) {
      merged.decision_policy = defaultForm.decision_policy
    }
    if (!parsed.platform) {
      merged.platform = defaultForm.platform
    }
    if (parsed.non_overlapping_only === undefined) {
      merged.non_overlapping_only = defaultForm.non_overlapping_only
    }
    if (!parsed.consensus_mode || merged.decision_policy === 'professional_v1') {
      merged.consensus_mode = defaultForm.consensus_mode
    }
    if (merged.decision_policy === 'professional_v1') {
      merged.max_ai_evaluations = 1
    }
    if (!parsed.reviewer_panel_size) {
      merged.reviewer_panel_size = defaultForm.reviewer_panel_size
    }
    if (!parsed.consensus_threshold || parsed.consensus_threshold > merged.reviewer_panel_size) {
      merged.consensus_threshold = defaultForm.consensus_threshold
    }
    if (merged.reviewer_panel_size === 25 && merged.consensus_threshold >= 28) {
      merged.consensus_threshold = defaultForm.consensus_threshold
    }
    if (merged.decision_policy === 'professional_v1' && merged.consensus_threshold > 20) {
      merged.consensus_threshold = 20
    }
    return merged
  } catch {
    return defaultForm
  }
}

function defaultBinanceProbeQuantity(symbol: string) {
  const normalized = symbol.toUpperCase().replace('USDT', '')
  if (normalized === 'BTC') return 0.001
  if (normalized === 'ETH') return 0.01
  if (normalized === 'BNB') return 0.05
  if (normalized === 'SOL') return 0.1
  if (normalized === 'XRP') return 10
  if (normalized === 'DOGE') return 100
  return 1
}

export default function BacktestTool() {
  const { t } = useTranslation()
  const end = useMemo(() => new Date(Date.now() - 10 * 60 * 1000), [])
  const start = useMemo(() => new Date(end.getTime() - 24 * 60 * 60 * 1000), [end])

  const [symbols, setSymbols] = useState<EventContractSymbol[]>([])
  const [hyperAiProfile, setHyperAiProfile] = useState<HyperAiProfile | null>(null)
  const [loadingSymbols, setLoadingSymbols] = useState(false)
  const [loadingPrediction, setLoadingPrediction] = useState(false)
  const [startingBacktest, setStartingBacktest] = useState(false)
  const [pausingBacktest, setPausingBacktest] = useState(false)
  const [runningBinanceProbe, setRunningBinanceProbe] = useState(false)
  const [binanceProbeResult, setBinanceProbeResult] = useState<BinanceTestnetOrderProbeResponse | null>(null)
  const [taskStatus, setTaskStatus] = useState<EventBacktestTaskStatus | null>(null)
  const [prediction, setPrediction] = useState<EventPrediction | null>(null)
  const [backtest, setBacktest] = useState<EventBacktestResponse | null>(null)
  const [selectedTrade, setSelectedTrade] = useState<EventTradeLog | null>(null)
  const [form, setForm] = useState<FormState>(() => loadSavedForm(buildDefaultForm(start, end)))
  const [coinglassCapability, setCoinGlassCapability] = useState<CoinGlassEventContractCapability | null>(null)
  const [loadingCoinGlassCapability, setLoadingCoinGlassCapability] = useState(false)
  const coinGlassAvailable = coinglassCapability?.available === true
  const runningBacktest = taskStatus ? ACTIVE_TASK_STATUSES.has(taskStatus.status) : false

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm(prev => {
      const next = { ...prev, [key]: value }
      if (key === 'decision_policy') {
        if (value === 'professional_v1') {
          next.consensus_mode = 'rule_only'
          next.max_ai_evaluations = 1
        } else if (next.max_ai_evaluations <= 1) {
          next.max_ai_evaluations = 20
        }
      }
      if (key === 'consensus_mode' && next.decision_policy === 'professional_v1') {
        next.consensus_mode = 'rule_only'
      }
      if (key === 'platform') {
        Object.assign(next, PLATFORM_FORM_PRESETS[value as string] || {})
      }
      if (key === 'enable_coinglass_features' && value === true) {
        if (!coinGlassAvailable) {
          toast.error(coinglassCapability?.reason || t('backtestTool.coinglassUnavailableShort', 'CoinGlass is not available for this period'))
          next.enable_coinglass_features = false
          return next
        }
        next.enable_cvd_filter = true
      }
      return next
    })
  }

  const selectedSymbolMeta = useMemo(() => {
    return symbols.find(item => (
      item.exchange === form.exchange &&
      item.symbol === form.symbol &&
      item.environment === form.environment
    ))
  }, [symbols, form.exchange, form.symbol, form.environment])

  const symbolOptions = useMemo(() => {
    const items = symbols.filter(item => (
      item.exchange === form.exchange &&
      item.environment === form.environment
    ))
    return Array.from(new Set(items.map(item => item.symbol))).sort()
  }, [symbols, form.exchange, form.environment])

  const periodOptions = selectedSymbolMeta?.periods?.length
    ? selectedSymbolMeta.periods.filter(period => (PERIOD_SECONDS[period] || Number.MAX_SAFE_INTEGER) <= form.expiry_minutes * 60)
    : PERIOD_OPTIONS.filter(period => PERIOD_SECONDS[period] <= form.expiry_minutes * 60)

  const saveConfig = () => {
    window.localStorage.setItem(BACKTEST_CONFIG_STORAGE_KEY, JSON.stringify(form))
    toast.success(t('backtestTool.configSaved', 'Configuration saved'))
  }

  const chartData = useMemo(() => {
    return (backtest?.equity_curve || []).map(point => ({
      ...point,
      label: formatTime(point.timestamp),
    }))
  }, [backtest])

  const displayAi: EventAiDecision[] = selectedTrade?.ai_decision_snapshot || prediction?.ai_decisions || []
  const displayFactors: EventFactorSnapshot[] = selectedTrade?.factor_snapshot || prediction?.factors || []

  const loadSymbols = useCallback(async () => {
    try {
      setLoadingSymbols(true)
      const [data, profile] = await Promise.all([
        getEventContractSymbols(),
        getHyperAiProfile().catch(() => null),
      ])
      setSymbols(data.symbols || [])
      if (profile) setHyperAiProfile(profile)
    } catch (error) {
      console.error('Failed to load event contract symbols:', error)
      toast.error(t('backtestTool.loadSymbolsFailed', 'Failed to load symbols'))
    } finally {
      setLoadingSymbols(false)
    }
  }, [t])

  const buildPredictPayload = (): EventContractConfig => ({
    symbol: form.symbol,
    exchange: form.exchange,
    environment: form.environment,
    period: form.period,
    expiry_minutes: Number(form.expiry_minutes),
    consensus_mode: form.decision_policy === 'professional_v1' ? 'rule_only' : form.consensus_mode,
    decision_policy: form.decision_policy,
    max_ai_evaluations: form.decision_policy === 'professional_v1' ? 1 : Number(form.max_ai_evaluations),
    consensus_threshold: Number(form.consensus_threshold),
    reviewer_panel_size: Number(form.reviewer_panel_size),
    target_win_rate: Number(form.target_win_rate),
    enable_edge_quality_gate: form.enable_edge_quality_gate,
    max_trade_range_risk: Number(form.max_trade_range_risk),
    allow_pullback_trades: form.allow_pullback_trades,
    enable_fake_breakout_filter: form.enable_fake_breakout_filter,
    enable_trap_filter: form.enable_trap_filter,
    enable_range_filter: form.enable_range_filter,
    enable_multi_timeframe_filter: form.enable_multi_timeframe_filter,
    enable_volume_filter: form.enable_volume_filter,
    enable_cvd_filter: form.enable_cvd_filter,
    enable_coinglass_features: form.enable_coinglass_features && coinGlassAvailable,
    min_coinglass_coverage_pct: Number(form.min_coinglass_coverage_pct),
    strict_coinglass_quality: form.strict_coinglass_quality,
    coinglass_no_future_leakage: form.coinglass_no_future_leakage,
    enable_l2_features: form.enable_l2_features,
    min_l2_coverage_pct: Number(form.min_l2_coverage_pct),
    strict_l2_quality: form.strict_l2_quality,
  })

  const buildBacktestPayload = (): EventContractBacktestConfig => ({
    ...buildPredictPayload(),
    start_time: fromLocalInputValue(form.start_time),
    end_time: fromLocalInputValue(form.end_time),
    initial_balance: Number(form.initial_balance),
    stake_amount: Number(form.stake_amount),
    win_payout_ratio: Number(form.win_payout_ratio),
    fee_rate: Number(form.fee_rate),
    slippage_bps: Number(form.slippage_bps),
    delay_seconds: Number(form.delay_seconds),
    draw_result: form.draw_result,
    max_bars: 50000,
    platform: form.platform,
    non_overlapping_only: form.non_overlapping_only,
  })

  const refreshPrediction = useCallback(async () => {
    try {
      setLoadingPrediction(true)
      const data = await predictEventContract(buildPredictPayload())
      setPrediction(data)
    } catch (error: any) {
      console.error('Prediction failed:', error)
      toast.error(error?.message || t('backtestTool.predictionFailed', 'Prediction failed'))
    } finally {
      setLoadingPrediction(false)
    }
  }, [form, coinGlassAvailable, t])

  const runBacktest = async () => {
    try {
      setStartingBacktest(true)
      setSelectedTrade(null)
      setBacktest(null)
      window.localStorage.removeItem(BACKTEST_LAST_TASK_STORAGE_KEY)
      const task = await createEventContractBacktestTask(buildBacktestPayload())
      window.localStorage.setItem(BACKTEST_TASK_STORAGE_KEY, String(task.task_id))
      setTaskStatus(task)
      toast.success(t('backtestTool.backtestStarted', 'Backtest started'))
    } catch (error: any) {
      console.error('Backtest task failed to start:', error)
      toast.error(error?.message || t('backtestTool.backtestFailed', 'Backtest failed'))
    } finally {
      setStartingBacktest(false)
    }
  }

  const pauseBacktest = async () => {
    if (!taskStatus?.task_id) return
    try {
      setPausingBacktest(true)
      const task = await pauseEventContractBacktestTask(taskStatus.task_id)
      setTaskStatus(task)
      toast.success(t('backtestTool.pauseRequested', 'Pause requested'))
    } catch (error: any) {
      console.error('Pause backtest failed:', error)
      toast.error(error?.message || t('backtestTool.pauseFailed', 'Pause failed'))
    } finally {
      setPausingBacktest(false)
    }
  }

  const runBinanceTestnetProbe = async () => {
    try {
      setRunningBinanceProbe(true)
      setBinanceProbeResult(null)
      const wallets = await getAllBinanceWallets()
      const wallet = wallets.find(item => item.environment === 'testnet' && item.is_active)
      if (!wallet) {
        throw new Error(t('backtestTool.noBinanceTestnetWallet', 'No active Binance Testnet wallet found'))
      }
      const side = prediction?.best_action === 'long' ? 'BUY' : 'SELL'
      const result = await runBinanceTestnetOrderProbe(wallet.account_id, {
        symbol: form.symbol,
        side,
        quantity: defaultBinanceProbeQuantity(form.symbol),
        leverage: 1,
        priceOffsetPct: 5,
      })
      setBinanceProbeResult(result)
      toast.success(t('backtestTool.binanceProbeSuccess', 'Binance Testnet order {{orderId}} was placed and cancelled', {
        orderId: result.order_id,
      }))
    } catch (error: any) {
      console.error('Binance testnet order probe failed:', error)
      toast.error(error?.message || t('backtestTool.binanceProbeFailed', 'Binance Testnet order probe failed'))
    } finally {
      setRunningBinanceProbe(false)
    }
  }

  const applyTaskStatus = useCallback((task: EventBacktestTaskStatus) => {
    setTaskStatus(task)
    if (task.result) {
      setBacktest(task.result)
      setSelectedTrade(task.result.trades?.[0] || null)
      window.localStorage.setItem(BACKTEST_LAST_TASK_STORAGE_KEY, String(task.task_id))
    }
    if (['completed', 'failed', 'paused'].includes(task.status)) {
      window.localStorage.removeItem(BACKTEST_TASK_STORAGE_KEY)
      if (task.task_id) {
        window.localStorage.setItem(BACKTEST_LAST_TASK_STORAGE_KEY, String(task.task_id))
      }
    }
  }, [])

  useEffect(() => {
    loadSymbols()
  }, [loadSymbols])

  useEffect(() => {
    const rawTaskId =
      window.localStorage.getItem(BACKTEST_TASK_STORAGE_KEY) ||
      window.localStorage.getItem(BACKTEST_LAST_TASK_STORAGE_KEY)
    const taskId = rawTaskId ? Number(rawTaskId) : 0
    let cancelled = false
    const restoreTask = async () => {
      try {
        const task = taskId
          ? await getEventContractBacktestTask(taskId)
          : await getLatestEventContractBacktestTask()
        if (!cancelled && task) applyTaskStatus(task)
      } catch (error) {
        if (cancelled) return
        console.error('Failed to restore backtest task:', error)
        window.localStorage.removeItem(BACKTEST_TASK_STORAGE_KEY)
        window.localStorage.removeItem(BACKTEST_LAST_TASK_STORAGE_KEY)
      }
    }
    restoreTask()
    return () => {
      cancelled = true
    }
  }, [applyTaskStatus])

  useEffect(() => {
    if (!taskStatus?.task_id || !ACTIVE_TASK_STATUSES.has(taskStatus.status)) return
    let cancelled = false
    const pollTask = async () => {
      try {
        const task = await getEventContractBacktestTask(taskStatus.task_id)
        if (!cancelled) applyTaskStatus(task)
      } catch (error) {
        if (!cancelled) console.error('Failed to poll backtest task:', error)
      }
    }
    const interval = window.setInterval(pollTask, 2000)
    pollTask()
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [taskStatus?.task_id, taskStatus?.status, applyTaskStatus])

  useEffect(() => {
    let cancelled = false
    const loadCapability = async () => {
      if (!isAuthenticated()) {
        if (cancelled) return
        setCoinGlassCapability({
          available: false,
          configured: false,
          status: 'not_authenticated',
          reason: t('backtestTool.loginRequired', 'Login required'),
          period: form.period,
          metrics: [],
        })
        setForm(prev => prev.enable_coinglass_features
          ? { ...prev, enable_coinglass_features: false }
          : prev)
        setLoadingCoinGlassCapability(false)
        return
      }
      try {
        setLoadingCoinGlassCapability(true)
        const capability = await getCoinGlassEventContractCapability({
          symbol: form.symbol,
          exchange: form.exchange,
          period: form.period,
        })
        if (cancelled) return
        setCoinGlassCapability(capability)
        if (!capability.available) {
          setForm(prev => prev.enable_coinglass_features
            ? { ...prev, enable_coinglass_features: false }
            : prev)
        }
      } catch (error) {
        if (cancelled) return
        setCoinGlassCapability({
          available: false,
          configured: false,
          status: 'check_failed',
          reason: error instanceof Error ? error.message : t('backtestTool.coinglassCheckFailed', 'CoinGlass plan check failed'),
          period: form.period,
          metrics: [],
        })
        setForm(prev => prev.enable_coinglass_features
          ? { ...prev, enable_coinglass_features: false }
          : prev)
      } finally {
        if (!cancelled) setLoadingCoinGlassCapability(false)
      }
    }
    loadCapability()
    return () => {
      cancelled = true
    }
  }, [form.symbol, form.exchange, form.period, t])

  useEffect(() => {
    if (periodOptions.length > 0 && !periodOptions.includes(form.period)) {
      updateForm('period', periodOptions[0])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodOptions.join(','), form.period])

  useEffect(() => {
    refreshPrediction()
    // Initial prediction only; user controls later refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
      <div className="shrink-0 border-b pb-3 sm:pb-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-normal sm:text-2xl">
                {t('backtestTool.title', 'Backtest Tool')}
              </h1>
              <Badge variant="secondary" className="gap-1">
                <Bot className="h-3 w-3" />
                {t('backtestTool.eventContract', '5m Event Contract')}
              </Badge>
              <Badge variant="outline">
                {form.decision_policy === 'professional_v1'
                  ? t('backtestTool.professionalPolicyBadge', 'Professional Decision')
                  : t('backtestTool.consensusBadge', 'Consensus {{required}}/{{total}}', {
                    required: form.consensus_threshold,
                    total: form.reviewer_panel_size,
                  })}
              </Badge>
              <Badge variant="outline">
                {t('backtestTool.mainLogicBadge', 'Main Logic Vote')}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {t('backtestTool.subtitle', '5-minute event contract prediction with signal edge, risk veto, execution realism, and historical settlement backtest.')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={runBinanceTestnetProbe}
              disabled={runningBinanceProbe || form.exchange !== 'binance'}
            >
              {runningBinanceProbe && <Loader2 className="h-4 w-4 animate-spin" />}
              {t('backtestTool.binanceTestnetProbe', 'Binance Testnet Order')}
            </Button>
            <Button variant="outline" onClick={saveConfig}>
              <Save className="h-4 w-4" />
              {t('backtestTool.saveConfig', 'Save Config')}
            </Button>
            <Button variant="outline" onClick={refreshPrediction} disabled={loadingPrediction}>
              {loadingPrediction ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              {t('backtestTool.refreshPrediction', 'Refresh Prediction')}
            </Button>
            {runningBacktest ? (
              <Button variant="outline" onClick={pauseBacktest} disabled={pausingBacktest || taskStatus?.status === 'pause_requested'}>
                {pausingBacktest || taskStatus?.status === 'pause_requested'
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Pause className="h-4 w-4" />}
                {taskStatus?.status === 'pause_requested'
                  ? t('backtestTool.pauseRequestedShort', 'Pausing')
                  : t('backtestTool.pauseBacktest', 'Pause')}
              </Button>
            ) : (
              <Button onClick={runBacktest} disabled={startingBacktest}>
                {startingBacktest ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {t('backtestTool.runBacktest', 'Run Event Backtest')}
              </Button>
            )}
          </div>
        </div>
        {binanceProbeResult && (
          <div className="mt-3 rounded-md border border-green-500/40 bg-green-500/5 px-3 py-2 text-xs text-green-700 dark:text-green-300">
            {t('backtestTool.binanceProbeResult', 'Binance Testnet order {{orderId}}: placed={{placeStatus}}, queried={{queryStatus}}, cancelled={{cancelStatus}}, price={{price}}', {
              orderId: binanceProbeResult.order_id,
              placeStatus: binanceProbeResult.place_status,
              queryStatus: binanceProbeResult.query_status,
              cancelStatus: binanceProbeResult.cancel_status,
              price: binanceProbeResult.limit_price,
            })}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pt-3 sm:pt-4">
        <div className="grid gap-4 2xl:grid-cols-[380px_minmax(0,1fr)]">
          <div className="space-y-4">
            <BacktestConfigPanel
              form={form}
              symbolOptions={symbolOptions}
              periodOptions={periodOptions}
              selectedSymbolMeta={selectedSymbolMeta}
              hyperAiProfile={hyperAiProfile}
              coinglassCapability={coinglassCapability}
              loadingCoinGlassCapability={loadingCoinGlassCapability}
              loadingSymbols={loadingSymbols}
              updateForm={updateForm}
            />
          </div>

          <div className="min-w-0 space-y-4">
            <PredictionPanel prediction={prediction} loadingPrediction={loadingPrediction} consensusMode={form.consensus_mode} />
            <BacktestResultsPanel
              backtest={backtest}
              runningBacktest={runningBacktest}
              taskStatus={taskStatus}
              chartData={chartData}
              displayAi={displayAi}
              displayFactors={displayFactors}
              selectedTrade={selectedTrade}
              setSelectedTrade={trade => setSelectedTrade(trade)}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
