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
  EventBacktestResponse,
  EventFactorSnapshot,
  EventTradeLog,
} from '@/lib/api'

import {
  directionClass,
  formatMoney,
  formatPct,
  formatPrice,
  formatTime,
  MetricCard,
  resultClass,
} from './shared'

type Props = {
  backtest: EventBacktestResponse | null
  runningBacktest: boolean
  chartData: Array<{ timestamp: number; equity: number; label: string }>
  displayAi: EventAiDecision[]
  displayFactors: EventFactorSnapshot[]
  selectedTrade: EventTradeLog | null
  setSelectedTrade: (trade: EventTradeLog) => void
}

export function BacktestResultsPanel({
  backtest,
  runningBacktest,
  chartData,
  displayAi,
  displayFactors,
  selectedTrade,
  setSelectedTrade,
}: Props) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t('backtestTool.results', 'Backtest Results')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {backtest ? (
          <>
            <SummaryGrid backtest={backtest} />
            <EquityChart chartData={chartData} />
            <Tabs defaultValue="trades" className="min-h-[420px]">
              <TabsList className="w-full justify-start overflow-x-auto">
                <TabsTrigger value="trades">{t('backtestTool.tradeLogs', 'Trade Logs')}</TabsTrigger>
                <TabsTrigger value="ai">{t('backtestTool.aiConsensus', 'AI / Rule Decisions')}</TabsTrigger>
                <TabsTrigger value="factors">{t('backtestTool.factorSnapshot', 'Factor Snapshot')}</TabsTrigger>
                <TabsTrigger value="filters">{t('backtestTool.filters', 'Filters')}</TabsTrigger>
              </TabsList>
              <TradeLogsTab
                trades={backtest.trades}
                selectedTrade={selectedTrade}
                setSelectedTrade={setSelectedTrade}
              />
              <AiDecisionsTab items={displayAi} />
              <FactorsTab items={displayFactors} />
              <FiltersTab backtest={backtest} />
            </Tabs>
          </>
        ) : (
          <div className="py-12 text-center text-sm text-muted-foreground">
            {runningBacktest
              ? t('backtestTool.running', 'Running event-contract backtest...')
              : t('backtestTool.runHint', 'Configure AI confirmation and run an event-contract backtest.')}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SummaryGrid({ backtest }: { backtest: EventBacktestResponse }) {
  const { t } = useTranslation()
  const summary = backtest.summary

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label={t('backtestTool.totalTrades', 'Total Trades')} value={String(summary.total_trades)} />
      <MetricCard
        label={t('backtestTool.aiEvaluated', 'AI Evaluated')}
        value={String(summary.ai_evaluated_count || 0)}
        tone={summary.ai_confirmed ? 'green' : 'amber'}
      />
      <MetricCard label={t('backtestTool.llmEvaluated', 'LLM Evaluated')} value={String(summary.llm_evaluated_count || 0)} />
      <MetricCard label={t('backtestTool.winRate', 'Win Rate')} value={formatPct(summary.win_rate)} tone={summary.win_rate >= 50 ? 'green' : 'red'} />
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
                <div className="truncate text-sm font-medium">{item.ai_name}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant="secondary" className="text-[10px]">
                    {item.source === 'llm_ai' ? (item.model || t('backtestTool.realAi', 'Real AI')) : t('backtestTool.system30Ai', '30 AI')}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{item.reason}</div>
              </div>
              <Badge variant="outline" className={directionClass(item.direction)}>{item.direction}</Badge>
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

  return (
    <TabsContent value="filters" className="mt-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard label={t('backtestTool.fakeFiltered', 'Fake Breakout Filtered')} value={String(summary.fake_breakout_filtered_count)} />
        <MetricCard label={t('backtestTool.trapFiltered', 'Trap Filtered')} value={String(summary.trap_filtered_count)} />
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
            <MetricCard label={t('backtestTool.klineGaps', 'K-line Gaps')} value={String(summary.data_quality.gap_count)} tone={summary.data_quality.gap_count ? 'amber' : 'green'} />
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
