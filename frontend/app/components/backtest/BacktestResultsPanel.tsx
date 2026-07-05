import { useTranslation } from 'react-i18next'
import { TrendingDown, TrendingUp } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type {
  EventAiDecision,
  EventAiReviewerStatus,
  EventBacktestResponse,
  EventBacktestResearchReport,
  EventBacktestTaskStatus,
  EventBacktestQualityGate,
  EventBacktestValidationReport,
  EventBacktestWindowReuse,
  EventFactorSnapshot,
  EventTradeLog,
} from '@/lib/api'

import { CredibilityCard } from './CredibilityCard'
import {
  directionClass,
  formatMoney,
  formatPct,
  formatPrice,
  formatTime,
  MetricCard,
  missingKlineCount,
  resultClass,
} from './shared'

type Props = {
  backtest: EventBacktestResponse | null
  runningBacktest: boolean
  taskStatus: EventBacktestTaskStatus | null
  chartData: Array<{ timestamp: number; equity: number; label: string }>
  displayAi: EventAiDecision[]
  displayFactors: EventFactorSnapshot[]
  selectedTrade: EventTradeLog | null
  setSelectedTrade: (trade: EventTradeLog) => void
  onHoldout: () => void
  holdoutRunning: boolean
}

const REVIEWER_NAME_KEYS: Record<string, string> = {
  'Main Logic': 'mainLogic',
  'Trend Micro AI': 'trendMicro',
  'Trend Structure AI': 'trendStructure',
  'Momentum AI': 'momentum',
  'Volume AI': 'volume',
  'Volatility AI': 'volatility',
  'Kline Pattern AI': 'klinePattern',
  'Wick Rejection AI': 'wickRejection',
  'Breakout AI': 'breakout',
  'Fake Breakout AI': 'fakeBreakout',
  'Pullback AI': 'pullback',
  'Range AI': 'range',
  'Trap Detection AI': 'trapDetection',
  'Bull Trap AI': 'bullTrap',
  'Bear Trap AI': 'bearTrap',
  'Liquidity Sweep AI': 'liquiditySweep',
  'Stop Hunt AI': 'stopHunt',
  'Orderbook AI': 'orderbook',
  'Spread AI': 'spread',
  'CVD AI': 'cvd',
  'Taker Ratio AI': 'takerRatio',
  'Open Interest AI': 'openInterest',
  'Funding Rate AI': 'fundingRate',
  'Liquidation AI': 'liquidation',
  'Support Resistance AI': 'supportResistance',
  'VWAP AI': 'vwap',
  'Multi Timeframe AI': 'multiTimeframe',
  'Market Regime AI': 'marketRegime',
  'Noise Filter AI': 'noiseFilter',
  'Entry Timing AI': 'entryTiming',
  'Final Risk AI': 'finalRisk',
}

export function BacktestResultsPanel({
  backtest,
  runningBacktest,
  taskStatus,
  chartData,
  displayAi,
  displayFactors,
  selectedTrade,
  setSelectedTrade,
  onHoldout,
  holdoutRunning,
}: Props) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t('backtestTool.results', 'Backtest Results')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {taskStatus && <TaskProgressPanel taskStatus={taskStatus} />}
        {backtest ? (
          <>
            {backtest.summary && (
              <CredibilityCard summary={backtest.summary} onHoldout={onHoldout} holdoutRunning={holdoutRunning} />
            )}
            <SummaryGrid backtest={backtest} />
            <WindowReuseNotice windowReuse={backtest.summary.research_report?.window_reuse} />
            <ProfessionalDecisionSummary trade={selectedTrade || backtest.trades[0]} />
            <QualityGatePanel qualityGate={backtest.summary.quality_gate} />
            <ValidationReportPanel validationReport={backtest.summary.validation_report} />
            <EquityChart chartData={chartData} />
            <Tabs defaultValue="trades" className="min-h-[420px]">
              <TabsList className="w-full justify-start overflow-x-auto">
                <TabsTrigger value="trades">{t('backtestTool.tradeLogs', 'Trade Logs')}</TabsTrigger>
                <TabsTrigger value="ai">{t('backtestTool.aiConsensus', 'AI / Rule Decisions')}</TabsTrigger>
                <TabsTrigger value="factors">{t('backtestTool.factorSnapshot', 'Factor Snapshot')}</TabsTrigger>
                <TabsTrigger value="filters">{t('backtestTool.filters', 'Filters')}</TabsTrigger>
                <TabsTrigger value="research">{t('backtestTool.researchMode', 'Research Mode')}</TabsTrigger>
              </TabsList>
              <TradeLogsTab
                trades={backtest.trades}
                selectedTrade={selectedTrade}
                setSelectedTrade={setSelectedTrade}
              />
              <AiDecisionsTab items={displayAi} />
              <FactorsTab items={displayFactors} />
              <FiltersTab backtest={backtest} />
              <ResearchModeTab researchReport={backtest.summary.research_report} />
            </Tabs>
          </>
        ) : (
          <div className="py-12 text-center text-sm text-muted-foreground">
            {runningBacktest
              ? t('backtestTool.running', 'Running event-contract backtest...')
              : t('backtestTool.runHint', 'Results will appear here after you run an event-contract backtest.')}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ProfessionalDecisionSummary({ trade }: { trade?: EventTradeLog | null }) {
  const { t } = useTranslation()
  const signal = trade?.event_signal
  if (!signal?.trade_readiness && signal?.edge_score == null && signal?.risk_score == null && signal?.execution_score == null) {
    return null
  }
  const vetoReasons = signal?.veto_reasons || []

  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{t('backtestTool.professionalDecision', 'Professional Decision')}</div>
          <div className="text-xs text-muted-foreground">
            {trade
              ? t('backtestTool.professionalDecisionTradeHint', 'Showing diagnostics for the selected or first returned trade.')
              : t('backtestTool.professionalDecisionNoTradeHint', 'No settled trade diagnostics yet.')}
          </div>
        </div>
        {signal?.decision_grade && (
          <Badge variant="outline">{t('backtestTool.decisionGrade', 'Grade')} {signal.decision_grade}</Badge>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t('backtestTool.tradeReadiness', 'Trade Readiness')} value={readinessLabel(signal?.trade_readiness, t)} tone={readinessTone(signal?.trade_readiness)} />
        <MetricCard label={t('backtestTool.edgeScore', 'Edge Score')} value={signal?.edge_score == null ? '-' : formatPct(signal.edge_score)} tone={(signal?.edge_score ?? 0) >= 75 ? 'green' : 'amber'} />
        <MetricCard label={t('backtestTool.riskScore', 'Risk Score')} value={signal?.risk_score == null ? '-' : formatPct(signal.risk_score)} tone={(signal?.risk_score ?? 100) <= 45 ? 'green' : 'red'} />
        <MetricCard label={t('backtestTool.executionScore', 'Execution Score')} value={signal?.execution_score == null ? '-' : formatPct(signal.execution_score)} tone={(signal?.execution_score ?? 0) >= 65 ? 'green' : 'amber'} />
      </div>
      {vetoReasons.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <div className="font-medium">{t('backtestTool.vetoReasons', 'Risk Veto Reasons')}</div>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {vetoReasons.map(reason => <li key={reason}>{reason}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

/** Data-snooping banner: warns when this window has already been re-optimized
 * with many different configs, so a good-looking result may just fit the
 * window's noise. Rendered only at medium/high risk. */
function WindowReuseNotice({ windowReuse }: { windowReuse?: EventBacktestWindowReuse }) {
  const { t } = useTranslation()
  if (!windowReuse?.available) return null
  const risk = windowReuse.overfit_risk || 'low'
  if (risk === 'low') return null
  const tone = risk === 'high'
    ? 'border-red-500/40 bg-red-500/5 text-red-700 dark:text-red-300'
    : 'border-amber-500/40 bg-amber-500/5 text-amber-700 dark:text-amber-300'
  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${tone}`}>
      <div className="font-medium">
        {t('backtestTool.windowReuseTitle', 'Data-snooping risk: this window has been re-tested')}
      </div>
      <div className="mt-1">
        {t('backtestTool.windowReuseBody', '{{fingerprints}} distinct strategy variants have already been tested on this window ({{runs}} prior runs). The more strategies are tuned against one window, the more the best result fits that window\'s noise. Confirm with a frozen-parameter holdout on an unseen window before trusting it.', {
          runs: windowReuse.prior_runs,
          fingerprints: windowReuse.distinct_fingerprints,
        })}
      </div>
    </div>
  )
}

/** Map known backend abort reasons to a localized, actionable explanation.
 * Returns null for unrecognized errors so the raw message still shows. */
function localizeBacktestError(message: string | null | undefined, t: ReturnType<typeof useTranslation>['t']): string | null {
  if (!message) return null
  const l2Match = message.match(/L2 coverage ([\d.]+)% below ([\d.]+)%/)
  if (l2Match) {
    return t('backtestTool.errL2Coverage', 'L2 orderbook coverage for this window is {{actual}}%, below the strict threshold of {{required}}%. L2 history cannot be backfilled — pick a window with better coverage (use the Data Quality Precheck), lower the L2 min coverage, or disable strict L2 quality.', {
      actual: l2Match[1],
      required: l2Match[2],
    })
  }
  const klineMatch = message.match(/K-line data quality check failed.*coverage ([\d.]+)% below ([\d.]+)%/)
  if (klineMatch) {
    return t('backtestTool.errKlineCoverage', 'K-line coverage for this window is {{actual}}%, below the strict threshold of {{required}}%. Pick a different window or relax the data quality settings.', {
      actual: klineMatch[1],
      required: klineMatch[2],
    })
  }
  if (/Not enough .* K-line data/.test(message)) {
    return t('backtestTool.errNotEnoughKlines', 'Not enough K-line history for this window (warmup + expiry bars required). Choose a later start time or a shorter window.')
  }
  return null
}

function TaskProgressPanel({ taskStatus }: { taskStatus: EventBacktestTaskStatus }) {
  const { t } = useTranslation()
  const ai_reviewer_statuses = taskStatus.ai_reviewer_statuses || []
  const completedAi = ai_reviewer_statuses.filter(item => item.status === 'completed').length
  const runningAi = ai_reviewer_statuses.filter(item => item.status === 'running').length
  const failedAi = ai_reviewer_statuses.filter(item => item.status === 'failed').length
  const skippedAi = ai_reviewer_statuses.filter(item => item.status === 'skipped').length
  const totalReviewers = ai_reviewer_statuses.length || taskStatus.config?.reviewer_panel_size || 25
  // rule_only mode never calls the LLM reviewers - hide the per-reviewer cards
  // and the AI counters to avoid the "30 stuck on pending" impression.
  const isExpired = taskStatus.status === 'failed' && taskStatus.phase === 'expired'
  const reviewersActive = !isExpired && ai_reviewer_statuses.length > 0 && skippedAi !== ai_reviewer_statuses.length
  const isActive = ['pending', 'running', 'pause_requested'].includes(taskStatus.status)
  const statusBadgeVariant = isActive ? 'default' : taskStatus.status === 'failed' ? 'destructive' : 'secondary'

  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={statusBadgeVariant}>{taskStatusLabel(taskStatus.status, t, taskStatus.phase)}</Badge>
            <span className="text-sm font-medium">
              {taskStatus.phase || t('backtestTool.taskPhase', 'Backtest task')}
            </span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {taskStatus.latest_message || taskStatus.error_message || t('backtestTool.taskWaiting', 'Waiting for task updates')}
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <div>{formatPct(taskStatus.progress_pct || 0)}</div>
          <div>
            {taskStatus.processed_decision_bars}/{taskStatus.total_decision_bars || '-'} {t('backtestTool.decisionBars', 'Decision Bars')}
          </div>
        </div>
      </div>
      <Progress value={taskStatus.progress_pct || 0} className="mt-3" />
      {taskStatus.status === 'failed' && !isExpired && localizeBacktestError(taskStatus.error_message, t) && (
        <div className="mt-3 rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-xs text-red-700 dark:text-red-300">
          {localizeBacktestError(taskStatus.error_message, t)}
        </div>
      )}
      {isExpired && (
        <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          {t('backtestTool.taskExpiredHint', 'This backtest task is expired and is no longer running. Start a new backtest to continue.')}
        </div>
      )}
      {reviewersActive ? (
        <>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <MetricCard label={t('backtestTool.aiCompleted', 'AI Completed')} value={`${completedAi}/${totalReviewers}`} tone={completedAi === totalReviewers ? 'green' : undefined} />
            <MetricCard label={t('backtestTool.aiRunning', 'AI Running')} value={String(runningAi)} tone={runningAi ? 'amber' : undefined} />
            <MetricCard label={t('backtestTool.aiFailed', 'AI Failed')} value={String(failedAi)} tone={failedAi ? 'red' : undefined} />
          </div>
          {runningAi > 0 && (
            <div className="mt-3 rounded-md border border-dashed bg-background/50 px-3 py-2 text-xs text-muted-foreground">
              {t('backtestTool.aiReviewerRunningHint', 'Running reviewers have not returned direction/confidence yet. This is waiting state, not missing data.')}
            </div>
          )}
          <div className="mt-3 grid max-h-[210px] gap-2 overflow-auto sm:grid-cols-2 xl:grid-cols-3">
            {ai_reviewer_statuses.map(item => (
              <div key={item.ai_name} className="rounded-md border bg-background px-2 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-xs font-medium">{reviewerNameLabel(item.ai_name, t)}</span>
                  <Badge variant="outline" className="text-[10px]">{reviewerStatusLabel(item.status, t)}</Badge>
                </div>
                <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                  {item.direction || item.confidence != null ? (
                    <>
                      <span className={directionClass(item.direction || 'hold')}>{reviewerDirectionLabel(item.direction, t)}</span>
                      <span>{item.confidence == null ? t('backtestTool.aiReviewerConfidencePending', 'Waiting confidence') : formatPct(item.confidence)}</span>
                    </>
                  ) : (
                    <span>{reviewerPendingLabel(item.status, t)}</span>
                  )}
                </div>
                {item.status === 'running' && !item.direction && item.confidence == null && (
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {t('backtestTool.aiReviewerPendingHint', 'Waiting for the AI call to return direction and confidence.')}
                  </div>
                )}
                {item.error && (
                  <div className="mt-1 line-clamp-2 text-[11px] text-red-500">{item.error}</div>
                )}
              </div>
            ))}
          </div>
        </>
      ) : !isExpired && skippedAi > 0 && (
        <div className="mt-3 rounded-md border border-dashed bg-background/40 px-3 py-2 text-xs text-muted-foreground">
          {t('backtestTool.aiReviewersSkipped', 'Rule-only mode: LLM reviewers skipped (rule consensus is deterministic).')}
        </div>
      )}
    </div>
  )
}

function taskStatusLabel(status: EventBacktestTaskStatus['status'], t: ReturnType<typeof useTranslation>['t'], phase?: string) {
  if (status === 'failed' && phase === 'expired') return t('backtestTool.taskStatusExpired', 'Expired')
  if (status === 'pending') return t('backtestTool.taskStatusPending', 'Queued')
  if (status === 'running') return t('backtestTool.taskStatusRunning', 'Running')
  if (status === 'pause_requested') return t('backtestTool.taskStatusPauseRequested', 'Pause requested')
  if (status === 'paused') return t('backtestTool.taskStatusPaused', 'Paused')
  if (status === 'completed') return t('backtestTool.taskStatusCompleted', 'Completed')
  if (status === 'failed') return t('backtestTool.taskStatusFailed', 'Failed')
  return status
}

function reviewerStatusLabel(status: EventAiReviewerStatus['status'], t: ReturnType<typeof useTranslation>['t']) {
  if (status === 'pending') return t('backtestTool.aiReviewerStatusPending', 'Queued')
  if (status === 'running') return t('backtestTool.aiReviewerStatusRunning', 'Running')
  if (status === 'completed') return t('backtestTool.aiReviewerStatusCompleted', 'Completed')
  if (status === 'failed') return t('backtestTool.aiReviewerStatusFailed', 'Failed')
  if (status === 'skipped') return t('backtestTool.aiReviewerStatusSkipped', 'Skipped')
  return status
}

function reviewerPendingLabel(status: EventAiReviewerStatus['status'], t: ReturnType<typeof useTranslation>['t']) {
  if (status === 'running') return t('backtestTool.aiReviewerPending', 'Waiting for AI direction/confidence')
  if (status === 'pending') return t('backtestTool.aiReviewerQueued', 'Queued for review')
  if (status === 'skipped') return t('backtestTool.aiReviewerSkippedShort', 'Skipped by rule mode')
  if (status === 'failed') return t('backtestTool.aiReviewerFailedShort', 'Review failed')
  return t('backtestTool.aiReviewerNoResult', 'No result yet')
}

function reviewerDirectionLabel(
  direction: EventAiReviewerStatus['direction'],
  t: ReturnType<typeof useTranslation>['t'],
) {
  if (direction === 'long') return t('backtestTool.directionLong', 'Long')
  if (direction === 'short') return t('backtestTool.directionShort', 'Short')
  if (direction === 'hold') return t('backtestTool.directionHold', 'Hold')
  return t('backtestTool.aiReviewerDirectionPending', 'Waiting direction')
}

function reviewerNameLabel(name: string, t: ReturnType<typeof useTranslation>['t']) {
  const key = REVIEWER_NAME_KEYS[name]
  if (key) return t(`backtestTool.reviewerNames.${key}`, name)
  if (name.endsWith(' Rule Agent')) {
    return t('backtestTool.ruleAgentReviewerName', '{{name}} Rule Reviewer', {
      name: name.replace(' Rule Agent', ''),
    })
  }
  if (name.endsWith(' AI')) {
    return t('backtestTool.genericAiReviewerName', '{{name}} Reviewer', {
      name: name.replace(' AI', ''),
    })
  }
  return name
}

function QualityGatePanel({ qualityGate }: { qualityGate?: EventBacktestQualityGate }) {
  const { t } = useTranslation()
  if (!qualityGate) return null
  const toneClass =
    qualityGate.status === 'pass' ? 'border-green-500 bg-green-500/5' :
    qualityGate.status === 'fail' ? 'border-red-500 bg-red-500/5' :
    'border-amber-500 bg-amber-500/5'
  const badgeClass =
    qualityGate.status === 'pass' ? 'border-green-500 text-green-600' :
    qualityGate.status === 'fail' ? 'border-red-500 text-red-600' :
    'border-amber-500 text-amber-600'
  const statusLabel =
    qualityGate.status === 'pass'
      ? t('backtestTool.qualityStatusPass', 'Pass')
      : qualityGate.status === 'fail'
        ? t('backtestTool.qualityStatusFail', 'Fail')
        : t('backtestTool.qualityStatusWarning', 'Warning')
  const attentionChecks = qualityGate.checks.filter(check => check.status !== 'pass')
  const visibleChecks = attentionChecks.length ? attentionChecks : qualityGate.checks.slice(0, 3)

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{t('backtestTool.qualityGate', 'Quality Gate')}</span>
            <Badge variant="outline" className={badgeClass}>
              {t('backtestTool.qualityGrade', 'Grade')} {qualityGate.grade}
            </Badge>
            <Badge variant="outline" className={badgeClass}>{statusLabel}</Badge>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t('backtestTool.qualityGateHint', 'Credibility audit based on sample size, partial status, data quality, and execution-cost assumptions.')}
          </div>
        </div>
        <div className="text-left sm:text-right">
          <div className="text-2xl font-semibold">{qualityGate.score}</div>
          <div className="text-xs text-muted-foreground">{t('backtestTool.qualityScore', 'Quality Score')}</div>
        </div>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {visibleChecks.map(check => (
          <div key={check.id} className="rounded-md border bg-background/70 px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-xs font-medium">{check.label}</div>
                <div className="mt-1 text-xs text-muted-foreground">{check.message}</div>
              </div>
              <Badge variant="outline" className={`shrink-0 text-[10px] ${qualityCheckClass(check.status)}`}>
                {check.status}
              </Badge>
            </div>
          </div>
        ))}
      </div>

      {qualityGate.recommendations.length > 0 && (
        <div className="mt-3 rounded-md border border-dashed bg-background/60 px-3 py-2">
          <div className="text-xs font-medium">{t('backtestTool.qualityRecommendations', 'Recommendations')}</div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {qualityGate.recommendations.map(item => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function edgeMonotonicityLabel(
  verdict: 'monotonic' | 'partial' | 'flat_or_inverted' | undefined,
  t: ReturnType<typeof useTranslation>['t'],
): string {
  if (verdict === 'monotonic') return t('backtestTool.monotonic', 'monotonic')
  if (verdict === 'partial') return t('backtestTool.partialMonotonic', 'partial')
  return t('backtestTool.flatOrInverted', 'no discrimination')
}

function ValidationReportPanel({ validationReport }: { validationReport?: EventBacktestValidationReport }) {
  const { t } = useTranslation()
  if (!validationReport) return null
  const verdictTone = validationReport.verdict === 'pass' ? 'green' : validationReport.verdict === 'fail' ? 'red' : 'amber'
  const toneClass =
    validationReport.verdict === 'pass' ? 'border-green-500 bg-green-500/5' :
    validationReport.verdict === 'fail' ? 'border-red-500 bg-red-500/5' :
    'border-amber-500 bg-amber-500/5'
  const weakestRegime = validationReport.regime_stability.weakest_regime || '-'

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{t('backtestTool.validationReport', 'Validation Report')}</span>
            <Badge variant="outline" className={validationVerdictClass(validationReport.verdict)}>
              {validationVerdictLabel(validationReport.verdict, t)}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t('backtestTool.validationReportHint', 'Credibility checks using walk-forward windows, Monte Carlo sequence stress, regime stability, and conservative live decay.')}
          </div>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label={t('backtestTool.walkForwardPassRate', 'Walk-Forward Pass Rate')}
          value={formatPct(validationReport.walk_forward.pass_rate)}
          tone={validationReport.walk_forward.pass_rate >= 70 ? 'green' : 'amber'}
        />
        <MetricCard
          label={t('backtestTool.mcProfitableRatio', 'MC Profitable Ratio')}
          value={formatPct(validationReport.monte_carlo.profitable_ratio)}
          tone={validationReport.monte_carlo.profitable_ratio >= 90 ? 'green' : 'amber'}
        />
        <MetricCard
          label={t('backtestTool.weakestRegime', 'Weakest Regime')}
          value={weakestRegime}
          tone={validationReport.regime_stability.unstable_regime_count ? 'red' : 'green'}
        />
        <MetricCard
          label={t('backtestTool.liveDecayPnl', 'Conservative Live PnL')}
          value={formatMoney(validationReport.live_decay_estimate.conservative_pnl)}
          tone={verdictTone}
        />
        <MetricCard
          label={t('backtestTool.worstWindowPnl', 'Worst Window PnL')}
          value={formatMoney(validationReport.walk_forward.worst_window_pnl)}
          tone={validationReport.walk_forward.worst_window_pnl >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          label={t('backtestTool.mcP5Pnl', 'MC P5 PnL')}
          value={formatMoney(validationReport.monte_carlo.p5_pnl)}
          tone={validationReport.monte_carlo.p5_pnl >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          label={t('backtestTool.unstableRegimes', 'Unstable Regimes')}
          value={String(validationReport.regime_stability.unstable_regime_count)}
          tone={validationReport.regime_stability.unstable_regime_count ? 'red' : 'green'}
        />
        <MetricCard
          label={t('backtestTool.expectedDecay', 'Expected Decay')}
          value={formatPct(validationReport.live_decay_estimate.expected_decay_pct)}
          tone={validationReport.live_decay_estimate.expected_decay_pct >= 65 ? 'amber' : 'green'}
        />
        <MetricCard
          label={t('backtestTool.edgeMonotonicity', 'Edge Monotonicity')}
          value={
            validationReport.edge_monotonicity?.status === 'ok'
              ? `${edgeMonotonicityLabel(validationReport.edge_monotonicity.verdict, t)} (${(validationReport.edge_monotonicity.top_minus_bottom ?? 0) >= 0 ? '+' : ''}${validationReport.edge_monotonicity.top_minus_bottom ?? 0}pp)`
              : t('backtestTool.insufficientSample', 'insufficient sample')
          }
          tone={
            validationReport.edge_monotonicity?.status !== 'ok'
              ? undefined
              : validationReport.edge_monotonicity.verdict === 'monotonic'
                ? 'green'
                : validationReport.edge_monotonicity.verdict === 'partial'
                  ? 'amber'
                  : 'red'
          }
        />
        <MetricCard
          label={t('backtestTool.thresholdSensitivity', 'Threshold Sensitivity')}
          value={
            validationReport.threshold_sensitivity?.status === 'ok'
              ? `${t('backtestTool.maxDelta', 'max Δ')} ${Math.max(...(validationReport.threshold_sensitivity.dimensions || []).map(d => Math.abs(d.win_rate_delta)), 0).toFixed(1)}pp`
              : t('backtestTool.insufficientSample', 'insufficient sample')
          }
          tone={
            validationReport.threshold_sensitivity?.status !== 'ok'
              ? undefined
              : Math.max(...(validationReport.threshold_sensitivity.dimensions || []).map(d => Math.abs(d.win_rate_delta)), 0) > 15
                ? 'amber'
                : 'green'
          }
        />
      </div>
      {validationReport.warnings.length > 0 && (
        <div className="mt-3 rounded-md border border-dashed bg-background/60 px-3 py-2">
          <div className="text-xs font-medium">{t('backtestTool.validationWarnings', 'Validation Warnings')}</div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {validationReport.warnings.map(item => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function validationVerdictLabel(verdict: string, t: ReturnType<typeof useTranslation>['t']) {
  if (verdict === 'pass') return t('backtestTool.validationPass', 'Pass')
  if (verdict === 'fail') return t('backtestTool.validationFail', 'Fail')
  return t('backtestTool.validationWarning', 'Warning')
}

function validationVerdictClass(verdict: string) {
  if (verdict === 'pass') return 'border-green-500 text-green-600'
  if (verdict === 'fail') return 'border-red-500 text-red-600'
  return 'border-amber-500 text-amber-600'
}

function ResearchModeTab({ researchReport }: { researchReport?: EventBacktestResearchReport }) {
  const { t } = useTranslation()
  if (!researchReport) {
    return (
      <TabsContent value="research" className="mt-3">
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          {t('backtestTool.researchNoReport', 'No research report is available for this run. Re-run the backtest with the latest backend.')}
        </div>
      </TabsContent>
    )
  }

  const verdictTone =
    researchReport.verdict.status === 'paper_candidate'
      ? 'green'
      : researchReport.verdict.status === 'watch'
        ? 'amber'
        : 'red'
  const aiTeam = researchReport.ai_trader_team

  return (
    <TabsContent value="research" className="mt-3 space-y-3">
      <div className={`rounded-md border p-3 ${researchVerdictPanelClass(researchReport.verdict.status)}`}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{t('backtestTool.researchMode', 'Research Mode')}</span>
              <Badge variant="outline" className={researchVerdictBadgeClass(researchReport.verdict.status)}>
                {researchVerdictLabel(researchReport.verdict.status, researchReport.verdict.label, t)}
              </Badge>
              {researchReport.verdict.best_candidate_name && (
                <Badge variant="secondary">{researchReport.verdict.best_candidate_name}</Badge>
              )}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t('backtestTool.researchModeHint', 'Automatic research audit: OOS validation, candidate strategies, factor discovery, overfitting warnings, and missing data.')}
            </div>
          </div>
        </div>
        {researchReport.verdict.reasons.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {researchReport.verdict.reasons.map(reason => <li key={reason}>{reason}</li>)}
          </ul>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t('backtestTool.trainWinRate', 'Train Win Rate')} value={formatPct(researchReport.oos_validation.train_win_rate)} />
        <MetricCard label={t('backtestTool.oosWinRate', 'OOS Win Rate')} value={formatPct(researchReport.oos_validation.oos_win_rate)} tone={verdictTone} />
        <MetricCard label={t('backtestTool.oosTradeCount', 'OOS Trades')} value={String(researchReport.oos_validation.oos_trade_count)} />
        <MetricCard label={t('backtestTool.winRateGap', 'Win Rate Gap')} value={formatPct(researchReport.oos_validation.win_rate_gap)} tone={researchReport.oos_validation.win_rate_gap > 15 ? 'red' : 'amber'} />
        <MetricCard label={t('backtestTool.oosPnl', 'OOS PnL')} value={formatMoney(researchReport.oos_validation.oos_pnl)} tone={researchReport.oos_validation.oos_pnl >= 0 ? 'green' : 'red'} />
        <MetricCard label={t('backtestTool.researchTarget', 'Research Target')} value={formatPct(researchReport.oos_validation.target_win_rate)} />
        <MetricCard label={t('backtestTool.researchBreakEven', 'Break-even')} value={formatPct(researchReport.oos_validation.break_even_win_rate)} />
        <MetricCard label={t('backtestTool.overfitRisk', 'Overfit Risk')} value={overfitRiskLabel(researchReport.oos_validation.overfit_risk, t)} tone={researchReport.oos_validation.overfit_risk === 'critical' || researchReport.oos_validation.overfit_risk === 'high' ? 'red' : 'amber'} />
      </div>

      {aiTeam && (
        <div className="rounded-md border p-3">
          <div className="mb-3 flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-semibold">{t('backtestTool.aiTraderTeam', '30 AI Traders')}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {aiTeam.description || t('backtestTool.aiTraderTeamHint', 'Each AI trades independently and is ranked by its own OOS results. This is not consensus voting.')}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">
                {t('backtestTool.aiTraderCount', 'Traders')}: {aiTeam.total_traders}
              </Badge>
              <Badge variant="outline">
                {t('backtestTool.aiTraderTeamTrades', 'Team Trades')}: {aiTeam.total_team_trades}
              </Badge>
              <Badge variant="outline" className="border-green-500 text-green-600">
                {t('backtestTool.paperCandidates', 'Paper Candidates')}: {aiTeam.paper_candidates.length}
              </Badge>
            </div>
          </div>
          <div className="max-h-[420px] overflow-auto">
            <Table className="min-w-[1120px]">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('backtestTool.aiTrader', 'AI Trader')}</TableHead>
                  <TableHead>{t('backtestTool.strategyType', 'Strategy Type')}</TableHead>
                  <TableHead>{t('backtestTool.totalTrades', 'Total Trades')}</TableHead>
                  <TableHead>{t('backtestTool.winRate', 'Win Rate')}</TableHead>
                  <TableHead>{t('backtestTool.oosWinRate', 'OOS Win Rate')}</TableHead>
                  <TableHead>{t('backtestTool.pnl', 'P&L')}</TableHead>
                  <TableHead>{t('backtestTool.maxDrawdown', 'Max Drawdown')}</TableHead>
                  <TableHead>{t('backtestTool.overfitRisk', 'Overfit Risk')}</TableHead>
                  <TableHead>{t('backtestTool.researchRecommendation', 'Recommendation')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {aiTeam.traders.map(trader => (
                  <TableRow key={trader.trader_id}>
                    <TableCell>
                      <div className="font-medium">{trader.name}</div>
                      <div className="mt-1 max-w-[260px] text-xs text-muted-foreground">
                        {trader.factor_focus.slice(0, 3).join(' / ') || trader.ai_name}
                      </div>
                    </TableCell>
                    <TableCell>{trader.strategy_type}</TableCell>
                    <TableCell>
                      <div>{trader.trade_count}</div>
                      <div className="text-xs text-muted-foreground">
                        {t('backtestTool.holdCount', 'Hold')}: {trader.hold_count}
                      </div>
                    </TableCell>
                    <TableCell>{formatPct(trader.win_rate)}</TableCell>
                    <TableCell>
                      <div>{formatPct(trader.oos_win_rate)}</div>
                      <div className="text-xs text-muted-foreground">
                        n={trader.oos_trade_count}
                      </div>
                    </TableCell>
                    <TableCell className={trader.pnl >= 0 ? 'text-green-600' : 'text-red-600'}>{formatMoney(trader.pnl)}</TableCell>
                    <TableCell>{formatPct(trader.max_drawdown)}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={overfitRiskClass(trader.overfit_risk)}>
                        {overfitRiskLabel(trader.overfit_risk, t)}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[260px] text-xs">{trader.recommendation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      <div className="rounded-md border p-3">
        <div className="mb-2 text-sm font-semibold">{t('backtestTool.strategyCandidates', 'Strategy Candidates')}</div>
        <div className="max-h-[360px] overflow-auto">
          <Table className="min-w-[980px]">
            <TableHeader>
              <TableRow>
                <TableHead>{t('backtestTool.candidate', 'Candidate')}</TableHead>
                <TableHead>{t('backtestTool.totalTrades', 'Total Trades')}</TableHead>
                <TableHead>{t('backtestTool.winRate', 'Win Rate')}</TableHead>
                <TableHead>{t('backtestTool.pnl', 'P&L')}</TableHead>
                <TableHead>{t('backtestTool.oosWinRate', 'OOS Win Rate')}</TableHead>
                <TableHead>{t('backtestTool.overfitRisk', 'Overfit Risk')}</TableHead>
                <TableHead>{t('backtestTool.researchRecommendation', 'Recommendation')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {researchReport.strategy_candidates.map(candidate => (
                <TableRow key={candidate.candidate_id}>
                  <TableCell>
                    <div className="font-medium">{candidate.name}</div>
                    <div className="mt-1 max-w-[320px] text-xs text-muted-foreground">{candidate.description}</div>
                  </TableCell>
                  <TableCell>{candidate.trade_count}</TableCell>
                  <TableCell>{formatPct(candidate.win_rate)}</TableCell>
                  <TableCell className={candidate.pnl >= 0 ? 'text-green-600' : 'text-red-600'}>{formatMoney(candidate.pnl)}</TableCell>
                  <TableCell>{formatPct(candidate.oos_win_rate)}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={overfitRiskClass(candidate.overfit_risk)}>
                      {overfitRiskLabel(candidate.overfit_risk, t)}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-[260px] text-xs">{candidate.recommendation}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="rounded-md border p-3">
        <div className="mb-2 text-sm font-semibold">{t('backtestTool.factorDiscovery', 'Factor Discovery')}</div>
        <div className="max-h-[320px] overflow-auto">
          <Table className="min-w-[900px]">
            <TableHeader>
              <TableRow>
                <TableHead>{t('backtestTool.factor', 'Factor')}</TableHead>
                <TableHead>{t('backtestTool.category', 'Category')}</TableHead>
                <TableHead>{t('backtestTool.sampleCount', 'Samples')}</TableHead>
                <TableHead>{t('backtestTool.winMean', 'Win Mean')}</TableHead>
                <TableHead>{t('backtestTool.lossMean', 'Loss Mean')}</TableHead>
                <TableHead>{t('backtestTool.separationScore', 'Separation')}</TableHead>
                <TableHead>{t('backtestTool.factorReliability', 'Reliability')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {researchReport.factor_insights.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-6 text-center text-muted-foreground">
                    {t('backtestTool.noFactorInsights', 'No factor insight yet. Need settled trades with factor snapshots.')}
                  </TableCell>
                </TableRow>
              ) : researchReport.factor_insights.map(factor => (
                <TableRow key={factor.factor_name}>
                  <TableCell>
                    <div className="font-medium">{factor.factor_name}</div>
                    <div className="mt-1 max-w-[360px] text-xs text-muted-foreground">{factor.interpretation}</div>
                  </TableCell>
                  <TableCell>{factor.category}</TableCell>
                  <TableCell>{factor.sample_count}</TableCell>
                  <TableCell>{factor.win_mean}</TableCell>
                  <TableCell>{factor.loss_mean}</TableCell>
                  <TableCell>{formatPct(factor.separation_score)}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={factorReliabilityClass(factor.reliability)}>
                      {factorReliabilityLabel(factor.reliability, t)}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <ResearchListPanel
          title={t('backtestTool.overfittingWarnings', 'Overfitting Warnings')}
          empty={t('backtestTool.noOverfittingWarnings', 'No overfitting warning from this report.')}
          items={researchReport.overfitting_warnings.map(item => ({
            key: `${item.severity}-${item.message}`,
            badge: item.severity,
            badgeClass: warningSeverityClass(item.severity),
            title: item.message,
            body: item.evidence,
          }))}
        />
        <ResearchListPanel
          title={t('backtestTool.missingDataRecommendations', 'Missing Data Recommendations')}
          empty={t('backtestTool.noMissingDataRecommendations', 'No missing-data recommendation from this report.')}
          items={researchReport.missing_data_recommendations.map(item => ({
            key: `${item.data_type}-${item.status}`,
            badge: item.status,
            badgeClass: 'border-amber-500 text-amber-600',
            title: item.data_type,
            body: item.recommendation,
          }))}
        />
      </div>
    </TabsContent>
  )
}

function ResearchListPanel({
  title,
  empty,
  items,
}: {
  title: string
  empty: string
  items: Array<{ key: string; badge: string; badgeClass: string; title: string; body: string }>
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 text-sm font-semibold">{title}</div>
      {items.length === 0 ? (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">{empty}</div>
      ) : (
        <div className="space-y-2">
          {items.map(item => (
            <div key={item.key} className="rounded-md border bg-muted/20 px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="text-xs font-medium">{item.title}</div>
                <Badge variant="outline" className={`shrink-0 text-[10px] ${item.badgeClass}`}>{item.badge}</Badge>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">{item.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function researchVerdictLabel(status: EventBacktestResearchReport['verdict']['status'], fallback: string, t: ReturnType<typeof useTranslation>['t']) {
  if (status === 'paper_candidate') return t('backtestTool.researchVerdictPaper', 'Paper candidate')
  if (status === 'watch') return t('backtestTool.researchVerdictWatch', 'Research watch')
  if (status === 'rejected') return t('backtestTool.researchVerdictRejected', 'Rejected')
  return fallback
}

function researchVerdictPanelClass(status: EventBacktestResearchReport['verdict']['status']) {
  if (status === 'paper_candidate') return 'border-green-500 bg-green-500/5'
  if (status === 'watch') return 'border-amber-500 bg-amber-500/5'
  return 'border-red-500 bg-red-500/5'
}

function researchVerdictBadgeClass(status: EventBacktestResearchReport['verdict']['status']) {
  if (status === 'paper_candidate') return 'border-green-500 text-green-600'
  if (status === 'watch') return 'border-amber-500 text-amber-600'
  return 'border-red-500 text-red-600'
}

function overfitRiskLabel(risk: string, t: ReturnType<typeof useTranslation>['t']) {
  if (risk === 'critical') return t('backtestTool.overfitCritical', 'Critical')
  if (risk === 'high') return t('backtestTool.overfitHigh', 'High')
  if (risk === 'medium') return t('backtestTool.overfitMedium', 'Medium')
  if (risk === 'low') return t('backtestTool.overfitLow', 'Low')
  return t('backtestTool.overfitNone', 'None')
}

function overfitRiskClass(risk: string) {
  if (risk === 'critical' || risk === 'high') return 'border-red-500 text-red-600'
  if (risk === 'medium') return 'border-amber-500 text-amber-600'
  return 'border-green-500 text-green-600'
}

function factorReliabilityLabel(reliability: string, t: ReturnType<typeof useTranslation>['t']) {
  if (reliability === 'strong') return t('backtestTool.factorStrong', 'Strong')
  if (reliability === 'medium') return t('backtestTool.factorMedium', 'Medium')
  if (reliability === 'low_sample') return t('backtestTool.factorLowSample', 'Low sample')
  return t('backtestTool.factorWeak', 'Weak')
}

function factorReliabilityClass(reliability: string) {
  if (reliability === 'strong') return 'border-green-500 text-green-600'
  if (reliability === 'medium') return 'border-amber-500 text-amber-600'
  if (reliability === 'low_sample') return 'border-red-500 text-red-600'
  return 'border-muted-foreground text-muted-foreground'
}

function warningSeverityClass(severity: string) {
  if (severity === 'critical' || severity === 'high') return 'border-red-500 text-red-600'
  return 'border-amber-500 text-amber-600'
}

function SummaryGrid({ backtest }: { backtest: EventBacktestResponse }) {
  const { t } = useTranslation()
  const summary = backtest.summary
  const breakEvenWinRate = summary.break_even_win_rate ?? 50
  const targetWinRate = summary.target_win_rate ?? 75
  const winRateTone = summary.target_win_rate_met
    ? 'green'
    : summary.win_rate >= breakEvenWinRate
      ? 'amber'
      : 'red'

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label={t('backtestTool.totalTrades', 'Total Trades')} value={String(summary.total_trades)} />
      <MetricCard
        label={t('backtestTool.aiEvaluated', 'AI Evaluated')}
        value={String(summary.ai_evaluated_count || 0)}
        tone={summary.ai_confirmed ? 'green' : 'amber'}
      />
      <MetricCard label={t('backtestTool.llmEvaluated', 'LLM Evaluated')} value={String(summary.llm_evaluated_count || 0)} />
      <MetricCard label={t('backtestTool.winRate', 'Win Rate')} value={formatPct(summary.win_rate)} tone={winRateTone} />
      <MetricCard
        label={t('backtestTool.targetWinRate', 'Target Win Rate')}
        value={formatPct(targetWinRate)}
        tone={summary.target_win_rate_met ? 'green' : 'amber'}
      />
      <MetricCard
        label={t('backtestTool.breakEvenWinRate', 'Break-even Win Rate')}
        value={formatPct(breakEvenWinRate)}
        tone={summary.win_rate >= breakEvenWinRate ? 'green' : 'red'}
      />
      <MetricCard
        label={t('backtestTool.auditStatus', 'Audit Status')}
        value={summary.audit_status || (summary.partial ? 'partial' : 'complete')}
        tone={summary.partial ? 'amber' : 'green'}
      />
      <MetricCard label={t('backtestTool.totalPnl', 'Total PnL')} value={formatMoney(summary.total_pnl)} tone={summary.total_pnl >= 0 ? 'green' : 'red'} />
      <MetricCard label={t('backtestTool.maxDrawdown', 'Max Drawdown')} value={formatPct(summary.max_drawdown)} tone={summary.max_drawdown > 10 ? 'red' : 'amber'} />
      <MetricCard label={t('backtestTool.profitFactor', 'Profit Factor')} value={summary.profit_factor.toFixed(2)} />
      <MetricCard label={t('backtestTool.expectancy', 'Expectancy')} value={formatMoney(summary.expectancy)} tone={summary.expectancy >= 0 ? 'green' : 'red'} />
      <MetricCard label={t('backtestTool.longWinRate', 'Long Win Rate')} value={formatPct(summary.long_win_rate)} icon={<TrendingUp className="h-3.5 w-3.5" />} />
      <MetricCard label={t('backtestTool.shortWinRate', 'Short Win Rate')} value={formatPct(summary.short_win_rate)} icon={<TrendingDown className="h-3.5 w-3.5" />} />
      {summary.data_quality?.l2?.enabled && (
        <MetricCard
          label={t('backtestTool.l2Coverage', 'L2 Coverage')}
          value={formatPct(summary.data_quality.l2.coverage_pct)}
          tone={summary.data_quality.l2.warnings.length ? 'amber' : 'green'}
        />
      )}
      {summary.data_quality?.coinglass?.enabled && (
        <MetricCard
          label={t('backtestTool.coinglassCoverage', 'CoinGlass Coverage')}
          value={formatPct(summary.data_quality.coinglass.coverage_pct)}
          tone={summary.data_quality.coinglass.warnings.length ? 'amber' : 'green'}
        />
      )}
    </div>
  )
}

function qualityCheckClass(status: EventBacktestQualityGate['status']) {
  if (status === 'pass') return 'border-green-500 text-green-600'
  if (status === 'fail') return 'border-red-500 text-red-600'
  return 'border-amber-500 text-amber-600'
}

function EquityChart({ chartData }: { chartData: Array<{ timestamp: number; equity: number; label: string }> }) {
  return (
    <div className="h-[260px] rounded-md border p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="label" minTickGap={32} tick={{ fontSize: 11 }} />
          <YAxis width={70} tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
          <Tooltip formatter={(value: unknown) => [`$${Number(value).toFixed(2)}`, 'Equity']} />
          <Line type="monotone" dataKey="equity" stroke="#2563eb" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function TradeLogsTab({
  trades,
  selectedTrade,
  setSelectedTrade,
}: {
  trades: EventTradeLog[]
  selectedTrade: EventTradeLog | null
  setSelectedTrade: (trade: EventTradeLog) => void
}) {
  const { t } = useTranslation()

  return (
    <TabsContent value="trades" className="mt-3 min-h-0">
      <div className="max-h-[420px] overflow-auto rounded-md border">
        <Table className="min-w-[980px]">
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>{t('backtestTool.entry', 'Entry')}</TableHead>
              <TableHead>{t('backtestTool.direction', 'Direction')}</TableHead>
              <TableHead>{t('backtestTool.eventSignal', 'Event Signal')}</TableHead>
              <TableHead>{t('backtestTool.entryPrice', 'Entry Price')}</TableHead>
              <TableHead>{t('backtestTool.expiryPrice', 'Expiry Price')}</TableHead>
              <TableHead>{t('backtestTool.result', 'Result')}</TableHead>
              <TableHead>{t('backtestTool.pnl', 'P&L')}</TableHead>
              <TableHead>{t('backtestTool.votes', 'Votes')}</TableHead>
              <TableHead>{t('backtestTool.state', 'State')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="py-8 text-center text-muted-foreground">
                  {t('backtestTool.noTrades', 'No trades met the event-contract gates. In real AI mode, only model-confirmed candidates are counted.')}
                </TableCell>
              </TableRow>
            ) : trades.map(trade => (
              <TableRow
                key={trade.trade_index}
                className={`cursor-pointer ${selectedTrade?.trade_index === trade.trade_index ? 'bg-muted' : ''}`}
                onClick={() => setSelectedTrade(trade)}
              >
                <TableCell>{trade.trade_index}</TableCell>
                <TableCell className="text-xs">{formatTime(trade.entry_time)}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={directionClass(trade.direction)}>{trade.direction}</Badge>
                </TableCell>
                <TableCell>{trade.signal_type || trade.event_signal?.signal_type || '-'}</TableCell>
                <TableCell>${formatPrice(trade.entry_price)}</TableCell>
                <TableCell>${formatPrice(trade.expiry_price)}</TableCell>
                <TableCell className={resultClass(trade.result)}>{trade.result}</TableCell>
                <TableCell className={resultClass(trade.result)}>{formatMoney(trade.profit_loss)}</TableCell>
                <TableCell>{trade.long_votes}/{trade.short_votes}/{trade.hold_votes}</TableCell>
                <TableCell>{trade.market_state}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TabsContent>
  )
}

function AiDecisionsTab({ items }: { items: EventAiDecision[] }) {
  const { t } = useTranslation()

  return (
    <TabsContent value="ai" className="mt-3 min-h-0">
      <div className="grid max-h-[420px] gap-2 overflow-auto lg:grid-cols-2">
        {items.map(item => (
          <div key={item.ai_name} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{reviewerNameLabel(item.ai_name, t)}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-[10px]">
                    {item.source === 'llm_ai'
                      ? (item.model || t('backtestTool.realAi', 'Real AI'))
                      : item.source === 'main_logic'
                        ? t('backtestTool.mainLogic', 'Main Logic')
                        : t('backtestTool.systemPanel', 'Rule Panel')}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{item.reason}</div>
              </div>
              <Badge variant="outline" className={directionClass(item.direction)}>{reviewerDirectionLabel(item.direction, t)}</Badge>
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs">
              <span className="w-16 text-muted-foreground">{formatPct(item.confidence)}</span>
              <Progress value={item.confidence} />
            </div>
            {item.risk_flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {item.risk_flags.map(flag => (
                  <Badge key={flag} variant="secondary" className="text-[10px]">{flag}</Badge>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </TabsContent>
  )
}

function FactorsTab({ items }: { items: EventFactorSnapshot[] }) {
  const { t } = useTranslation()

  return (
    <TabsContent value="factors" className="mt-3 min-h-0">
      <div className="max-h-[420px] overflow-auto rounded-md border">
        <Table className="min-w-[760px]">
          <TableHeader>
            <TableRow>
              <TableHead>{t('backtestTool.factor', 'Factor')}</TableHead>
              <TableHead>{t('backtestTool.category', 'Category')}</TableHead>
              <TableHead>{t('backtestTool.value', 'Value')}</TableHead>
              <TableHead>{t('backtestTool.bias', 'Bias')}</TableHead>
              <TableHead>{t('backtestTool.confidence', 'Confidence')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(factor => (
              <TableRow key={`${factor.factor_name}-${factor.category}`}>
                <TableCell className="font-medium">{factor.factor_name}</TableCell>
                <TableCell>{factor.category}</TableCell>
                <TableCell>{factor.value}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={directionClass(factor.direction_bias === 'neutral' ? 'hold' : factor.direction_bias)}>{factor.direction_bias}</Badge>
                </TableCell>
                <TableCell>{formatPct(factor.confidence)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TabsContent>
  )
}

function FiltersTab({ backtest }: { backtest: EventBacktestResponse }) {
  const { t } = useTranslation()
  const summary = backtest.summary
  const missingKlines = missingKlineCount(summary.data_quality)

  return (
    <TabsContent value="filters" className="mt-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard label={t('backtestTool.fakeFiltered', 'Fake Breakout Filtered')} value={String(summary.fake_breakout_filtered_count)} />
        <MetricCard label={t('backtestTool.trapFiltered', 'Trap Filtered')} value={String(summary.trap_filtered_count)} />
        <MetricCard label={t('backtestTool.edgeFiltered', 'Edge Gate Filtered')} value={String(summary.edge_quality_filtered_count || 0)} />
        <MetricCard label={t('backtestTool.noTradeFiltered', 'No Trade Filtered')} value={String(summary.no_trade_filtered_count)} />
        <MetricCard label={t('backtestTool.rulePrefiltered', 'Rule Prefiltered')} value={String(summary.rule_prefiltered_count || 0)} />
        <MetricCard label={t('backtestTool.aiRejected', 'AI Rejected')} value={String(summary.ai_rejected_count || 0)} />
        <MetricCard label={t('backtestTool.llmEvaluated', 'LLM Evaluated')} value={String(summary.llm_evaluated_count || 0)} />
        <MetricCard label={t('backtestTool.aiSkippedCap', 'AI Cap Skipped')} value={String(summary.ai_skipped_cap_count || 0)} />
        <MetricCard label={t('backtestTool.missingExpiry', 'Missing Expiry')} value={String(summary.missing_expiry_count || 0)} />
        <MetricCard label={t('backtestTool.expiryLagSkipped', 'Expiry Lag Skipped')} value={String(summary.expiry_lag_skipped_count || 0)} />
        <MetricCard label={t('backtestTool.decisionBars', 'Decision Bars')} value={String(summary.decision_bars_count || 0)} />
        <MetricCard label={t('backtestTool.candidateSignals', 'Candidates')} value={String(summary.candidate_signals_count || 0)} />
        {summary.data_quality && (
          <>
            <MetricCard label={t('backtestTool.dataCoverage', 'Data Coverage')} value={formatPct(summary.data_quality.coverage_pct)} tone={summary.data_quality.warnings.length ? 'amber' : 'green'} />
            <MetricCard label={t('backtestTool.klineGapSegments', 'K-line Gap Segments')} value={String(summary.data_quality.gap_count)} tone={summary.data_quality.gap_count ? 'amber' : 'green'} />
            <MetricCard label={t('backtestTool.missingKlines', 'Missing K-lines')} value={String(missingKlines)} tone={missingKlines ? 'amber' : 'green'} />
          </>
        )}
        {summary.data_quality?.coinglass?.enabled && (
          <>
            <MetricCard
              label={t('backtestTool.coinglassCoverage', 'CoinGlass Coverage')}
              value={formatPct(summary.data_quality.coinglass.coverage_pct)}
              tone={summary.data_quality.coinglass.warnings.length ? 'amber' : 'green'}
            />
            <MetricCard
              label={t('backtestTool.coinglassSource', 'CoinGlass Source')}
              value={summary.data_quality.coinglass.key_source || '-'}
            />
            {(summary.data_quality.coinglass.metric_coverage || []).map(metric => (
              <MetricCard
                key={metric.metric}
                label={metric.label || metric.metric}
                value={formatPct(metric.coverage_pct)}
                tone={metric.warnings?.length ? 'amber' : 'green'}
              />
            ))}
          </>
        )}
        {summary.data_quality?.l2?.enabled && (
          <>
            <MetricCard
              label={t('backtestTool.l2Coverage', 'L2 Coverage')}
              value={formatPct(summary.data_quality.l2.coverage_pct)}
              tone={summary.data_quality.l2.warnings.length ? 'amber' : 'green'}
            />
            <MetricCard
              label={t('backtestTool.l2MaxLag', 'L2 Max Lag')}
              value={`${summary.data_quality.l2.max_lag_seconds ?? 0}s`}
              tone={(summary.data_quality.l2.warnings || []).length ? 'amber' : 'green'}
            />
            <MetricCard
              label={t('backtestTool.l2Records', 'L2 Records')}
              value={String(summary.data_quality.l2.records_loaded || 0)}
            />
          </>
        )}
        <MetricCard label={t('backtestTool.avgStrength', 'Avg Strength')} value={formatPct(summary.average_signal_strength)} />
        <MetricCard label={t('backtestTool.avgTrapRisk', 'Avg Trap Risk')} value={formatPct(summary.average_trap_risk)} />
        <MetricCard label={t('backtestTool.executionTime', 'Execution Time')} value={`${summary.execution_time_ms}ms`} />
      </div>
    </TabsContent>
  )
}

function readinessLabel(readiness: string | undefined, t: ReturnType<typeof useTranslation>['t']) {
  if (readiness === 'tradable') return t('backtestTool.readinessTradable', 'Tradable')
  if (readiness === 'watch') return t('backtestTool.readinessWatch', 'Watch')
  if (readiness === 'blocked') return t('backtestTool.readinessBlocked', 'Blocked')
  return '-'
}

function readinessTone(readiness: string | undefined): 'green' | 'amber' | 'red' | undefined {
  if (readiness === 'tradable') return 'green'
  if (readiness === 'watch') return 'amber'
  if (readiness === 'blocked') return 'red'
  return undefined
}
