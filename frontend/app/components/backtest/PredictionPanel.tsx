import { useTranslation } from 'react-i18next'
import { AlertTriangle, BarChart3, Bot, Clock, ShieldCheck, Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { EventPrediction } from '@/lib/api'

import { directionClass, formatPct, formatPrice, formatTime, MetricCard } from './shared'

type Props = {
  prediction: EventPrediction | null
  loadingPrediction: boolean
  consensusMode?: string
}

export function PredictionPanel({ prediction, loadingPrediction, consensusMode }: Props) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">{t('backtestTool.currentPrediction', 'Current 5m Prediction')}</CardTitle>
          {prediction && (
            <Badge variant="outline" className={directionClass(prediction.best_action)}>
              {prediction.best_action.toUpperCase()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {prediction ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <MetricCard label={t('backtestTool.currentPrice', 'Current Price')} value={`$${formatPrice(prediction.current_price)}`} icon={<Target className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.expiryTime', 'Expiry Time')} value={formatTime(prediction.expiry_time)} icon={<Clock className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.consensus', 'Consensus Votes')} value={`${prediction.ai_consensus.long_votes}/${prediction.ai_consensus.short_votes}/${prediction.ai_consensus.hold_votes}`} icon={<Bot className="h-3.5 w-3.5" />} />
              <MetricCard
                label={t('backtestTool.consensusSource', 'Consensus Source')}
                value={prediction.ai_model || t('backtestTool.system30Ai', '30 AI')}
                tone={prediction.ai_participated ? 'green' : 'amber'}
              />
              <MetricCard label={t('backtestTool.eventSignal', 'Event Signal')} value={prediction.event_signal_type || prediction.event_signal?.signal_type || '-'} tone={prediction.allow_trade ? 'green' : 'amber'} />
              <MetricCard label={t('backtestTool.allowTrade', 'Allow Trade')} value={prediction.allow_trade ? t('common.yes', 'Yes') : t('common.no', 'No')} tone={prediction.allow_trade ? 'green' : 'amber'} icon={<ShieldCheck className="h-3.5 w-3.5" />} />
            </div>
            {prediction.data_quality && (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard label={t('backtestTool.dataCoverage', 'Data Coverage')} value={formatPct(prediction.data_quality.coverage_pct)} tone={prediction.data_quality.warnings.length ? 'amber' : 'green'} />
                <MetricCard label={t('backtestTool.klineGaps', 'K-line Gaps')} value={String(prediction.data_quality.gap_count)} tone={prediction.data_quality.gap_count ? 'amber' : 'green'} />
                <MetricCard label={t('backtestTool.duplicates', 'Duplicates')} value={String(prediction.data_quality.duplicate_count)} tone={prediction.data_quality.duplicate_count ? 'amber' : 'green'} />
                <MetricCard label={t('backtestTool.unclosedDropped', 'Unclosed Dropped')} value={String(prediction.data_quality.unclosed_bars_dropped || 0)} />
                {prediction.data_quality.l2?.enabled && (
                  <>
                    <MetricCard
                      label={t('backtestTool.l2Coverage', 'L2 Coverage')}
                      value={formatPct(prediction.data_quality.l2.coverage_pct)}
                      tone={prediction.data_quality.l2.warnings.length ? 'amber' : 'green'}
                    />
                    <MetricCard
                      label={t('backtestTool.l2MaxLag', 'L2 Max Lag')}
                      value={`${prediction.data_quality.l2.max_lag_seconds ?? 0}s`}
                    />
                  </>
                )}
                {prediction.data_quality.coinglass?.enabled && (
                  <>
                    <MetricCard
                      label={t('backtestTool.coinglassCoverage', 'CoinGlass Coverage')}
                      value={formatPct(prediction.data_quality.coinglass.coverage_pct)}
                      tone={prediction.data_quality.coinglass.warnings.length ? 'amber' : 'green'}
                    />
                    <MetricCard
                      label={t('backtestTool.coinglassSource', 'CoinGlass Source')}
                      value={prediction.data_quality.coinglass.key_source || '-'}
                    />
                  </>
                )}
              </div>
            )}
            <div className="grid gap-3 lg:grid-cols-3">
              <ProbabilityBar label={t('backtestTool.longProbability', 'Long Win Probability')} value={prediction.long_5m_probability} toneClass="text-green-600" />
              <ProbabilityBar label={t('backtestTool.shortProbability', 'Short Win Probability')} value={prediction.short_5m_probability} toneClass="text-red-600" />
              <ProbabilityBar label={t('backtestTool.holdProbability', 'Hold Probability')} value={prediction.hold_probability} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label={t('backtestTool.marketState', 'Market State')} value={prediction.market_state} icon={<BarChart3 className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.signalStrength', 'Signal Strength')} value={formatPct(prediction.signal_strength)} />
              <MetricCard label={t('backtestTool.trapRisk', 'Trap Risk')} value={formatPct(prediction.trap_risk)} tone={prediction.trap_risk > 60 ? 'red' : 'green'} icon={<AlertTriangle className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.fakeRisk', 'Fake Breakout Risk')} value={formatPct(prediction.fake_breakout_risk)} tone={prediction.fake_breakout_risk > 60 ? 'red' : 'green'} icon={<AlertTriangle className="h-3.5 w-3.5" />} />
            </div>
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="font-medium">{prediction.reason}</div>
              {prediction.entry_warning && (
                <div className="mt-1 text-xs text-amber-600">{prediction.entry_warning}</div>
              )}
              {prediction.event_signal?.avoid_condition && (
                <div className="mt-1 text-xs text-amber-600">{prediction.event_signal.avoid_condition}</div>
              )}
              {prediction.similar_patterns?.[0] && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {t('backtestTool.similarWinRate', 'Similar pattern win rate')}: {formatPct(prediction.similar_patterns[0].historical_win_rate)}
                  {' '}({prediction.similar_patterns[0].sample_size} {t('backtestTool.samples', 'samples')})
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="py-8 text-center text-sm text-muted-foreground">
            {loadingPrediction ? (
              consensusMode === 'ai_confirmed'
                ? t('backtestTool.loadingAiConfirm', 'Running 30 AI confirmations... (≈45s)')
                : t('common.loading', 'Loading...')
            ) : t('backtestTool.noPrediction', 'No prediction yet')}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ProbabilityBar({
  label,
  value,
  toneClass = 'text-foreground',
}: {
  label: string
  value: number
  toneClass?: string
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span>{label}</span>
        <span className={`font-medium ${toneClass}`}>{formatPct(value)}</span>
      </div>
      <Progress value={value} />
    </div>
  )
}
