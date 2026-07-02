import { useTranslation } from 'react-i18next'
import { AlertTriangle, BarChart3, Bot, Clock, ShieldCheck, Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import type { EventPrediction } from '@/lib/api'

import { formatPct, formatPrice, formatTime, MetricCard, missingKlineCount } from './shared'

type Props = {
  prediction: EventPrediction | null
  loadingPrediction: boolean
  consensusMode?: string
}

export function PredictionPanel({ prediction, loadingPrediction, consensusMode }: Props) {
  const { t } = useTranslation()
  const consensus = prediction?.ai_consensus
  const topVotes = consensus?.top_votes ?? Math.max(consensus?.long_votes ?? 0, consensus?.short_votes ?? 0)
  const reviewerCount = consensus?.reviewer_count ?? (
    (consensus?.long_votes ?? 0) + (consensus?.short_votes ?? 0) + (consensus?.hold_votes ?? 0)
  )
  const requiredVotes = consensus?.required_votes ?? 5
  const mainLogicDirection = consensus?.main_logic_direction || 'hold'
  const professionalMode = (prediction?.decision_policy || consensus?.decision_policy) === 'professional_v1'
  const directionBias = consensus?.top_direction && consensus.top_direction !== 'hold'
    ? consensus.top_direction
    : (mainLogicDirection || prediction?.best_action || 'hold')
  const missingKlines = missingKlineCount(prediction?.data_quality)
  const sourceLabel = prediction?.ai_model || (
    professionalMode
      ? t('backtestTool.professionalRuleDesk', 'Professional rule desk')
      : prediction?.ai_participated
      ? t('backtestTool.realAi', 'Real AI')
      : t('backtestTool.systemPanel', 'Rule Panel')
  )

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">{t('backtestTool.currentPrediction', 'Current 5m Prediction')}</CardTitle>
          {prediction && (
            <Badge variant="outline" className={tradeActionClass(prediction)}>
              {tradeActionLabel(prediction, t)}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {prediction ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <MetricCard label={t('backtestTool.currentPrice', 'Current Price')} value={`$${formatPrice(prediction.current_price)}`} icon={<Target className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.expiryTime', 'Expiry Time')} value={formatTime(prediction.expiry_time)} icon={<Clock className="h-3.5 w-3.5" />} />
              <MetricCard
                label={t('backtestTool.directionBias', 'Direction Bias')}
                value={directionLabel(directionBias, t)}
                tone={directionTone(directionBias)}
                icon={<BarChart3 className="h-3.5 w-3.5" />}
              />
              <MetricCard
                label={t('backtestTool.tradeAction', 'Trade Action')}
                value={tradeActionLabel(prediction, t)}
                tone={tradeActionTone(prediction)}
                icon={<ShieldCheck className="h-3.5 w-3.5" />}
              />
              <MetricCard
                label={professionalMode ? t('backtestTool.directionSupport', 'Direction Support') : t('backtestTool.consensus', 'Consensus Votes')}
                value={`${topVotes}/${reviewerCount || 25}`}
                tone={topVotes >= requiredVotes ? 'green' : 'amber'}
                icon={<Bot className="h-3.5 w-3.5" />}
              />
              <MetricCard
                label={t('backtestTool.mainLogic', 'Main Logic')}
                value={consensus?.main_logic_participated ? directionLabel(mainLogicDirection, t) : t('common.no', 'No')}
                tone={consensus?.main_logic_participated ? 'green' : 'amber'}
              />
              <MetricCard
                label={t('backtestTool.consensusSource', 'Consensus Source')}
                value={sourceLabel}
                tone={prediction.ai_participated ? 'green' : 'amber'}
              />
              <MetricCard label={t('backtestTool.eventSignal', 'Event Signal')} value={signalTypeLabel(prediction.event_signal_type || prediction.event_signal?.signal_type, t)} tone={prediction.allow_trade ? 'green' : 'amber'} />
              <MetricCard label={t('backtestTool.riskBlockReason', 'Risk Block')} value={riskBlockReason(prediction, t)} tone={prediction.allow_trade ? 'green' : 'red'} icon={<AlertTriangle className="h-3.5 w-3.5" />} />
              <MetricCard label={t('backtestTool.nextTradeCondition', 'Next Condition')} value={nextTradeCondition(prediction, t)} tone={prediction.allow_trade ? 'green' : 'amber'} />
            </div>
            <ProfessionalDecisionPanel prediction={prediction} />
            {prediction.data_quality && (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <MetricCard label={t('backtestTool.dataCoverage', 'Data Coverage')} value={formatPct(prediction.data_quality.coverage_pct)} tone={prediction.data_quality.warnings.length ? 'amber' : 'green'} />
                <MetricCard label={t('backtestTool.klineGapSegments', 'K-line Gap Segments')} value={String(prediction.data_quality.gap_count)} tone={prediction.data_quality.gap_count ? 'amber' : 'green'} />
                <MetricCard label={t('backtestTool.missingKlines', 'Missing K-lines')} value={String(missingKlines)} tone={missingKlines ? 'amber' : 'green'} />
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
                ? t('backtestTool.loadingAiConfirm', 'Running AI confirmations...')
                : t('common.loading', 'Loading...')
            ) : t('backtestTool.noPrediction', 'No prediction yet')}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ProfessionalDecisionPanel({ prediction }: { prediction: EventPrediction }) {
  const { t } = useTranslation()
  const readiness = prediction.trade_readiness || prediction.event_signal?.trade_readiness
  const edgeScore = prediction.edge_score ?? prediction.event_signal?.edge_score
  const riskScore = prediction.risk_score ?? prediction.event_signal?.risk_score
  const executionScore = prediction.execution_score ?? prediction.event_signal?.execution_score
  const grade = prediction.decision_grade || prediction.event_signal?.decision_grade
  const vetoReasons = prediction.veto_reasons?.length ? prediction.veto_reasons : prediction.event_signal?.veto_reasons || []
  if (!readiness && edgeScore == null && riskScore == null && executionScore == null) return null

  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{t('backtestTool.professionalDecision', 'Professional Decision')}</div>
          <div className="text-xs text-muted-foreground">
            {t('backtestTool.professionalDecisionHint', 'Signal edge, risk veto, and execution feasibility are evaluated before counting a trade.')}
          </div>
        </div>
        {grade && <Badge variant="outline">{t('backtestTool.decisionGrade', 'Grade')} {grade}</Badge>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label={t('backtestTool.tradeReadiness', 'Trade Readiness')} value={readinessLabel(readiness, t)} tone={readinessTone(readiness)} />
        <MetricCard label={t('backtestTool.edgeScore', 'Edge Score')} value={edgeScore == null ? '-' : formatPct(edgeScore)} tone={(edgeScore ?? 0) >= 75 ? 'green' : 'amber'} />
        <MetricCard label={t('backtestTool.riskScore', 'Risk Score')} value={riskScore == null ? '-' : formatPct(riskScore)} tone={(riskScore ?? 100) <= 45 ? 'green' : 'red'} />
        <MetricCard label={t('backtestTool.executionScore', 'Execution Score')} value={executionScore == null ? '-' : formatPct(executionScore)} tone={(executionScore ?? 0) >= 65 ? 'green' : 'amber'} />
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

function directionLabel(direction: string | null | undefined, t: ReturnType<typeof useTranslation>['t']) {
  if (direction === 'long') return t('backtestTool.directionLong', 'Long')
  if (direction === 'short') return t('backtestTool.directionShort', 'Short')
  if (direction === 'hold') return t('backtestTool.directionHold', 'Hold')
  return '-'
}

function directionTone(direction: string | null | undefined): 'green' | 'amber' | 'red' | undefined {
  if (direction === 'long') return 'green'
  if (direction === 'short') return 'red'
  if (direction === 'hold') return 'amber'
  return undefined
}

function predictionReadiness(prediction: EventPrediction) {
  return prediction.trade_readiness || prediction.event_signal?.trade_readiness
}

function tradeActionLabel(prediction: EventPrediction, t: ReturnType<typeof useTranslation>['t']) {
  const readiness = predictionReadiness(prediction)
  if (prediction.allow_trade || readiness === 'tradable') return t('backtestTool.actionTradable', 'Tradable')
  if (readiness === 'watch') return t('backtestTool.actionWatch', 'Watch')
  return t('backtestTool.actionBlocked', 'Blocked')
}

function tradeActionTone(prediction: EventPrediction): 'green' | 'amber' | 'red' | undefined {
  const readiness = predictionReadiness(prediction)
  if (prediction.allow_trade || readiness === 'tradable') return 'green'
  if (readiness === 'watch') return 'amber'
  return 'red'
}

function tradeActionClass(prediction: EventPrediction) {
  const tone = tradeActionTone(prediction)
  if (tone === 'green') return 'text-green-600 border-green-500 bg-green-500/10'
  if (tone === 'amber') return 'text-amber-600 border-amber-500 bg-amber-500/10'
  return 'text-red-600 border-red-500 bg-red-500/10'
}

function signalTypeLabel(signalType: string | null | undefined, t: ReturnType<typeof useTranslation>['t']) {
  const normalized = (signalType || '').toLowerCase()
  if (!normalized) return '-'
  if (normalized.includes('long')) return t('backtestTool.directionLong', 'Long')
  if (normalized.includes('short')) return t('backtestTool.directionShort', 'Short')
  if (normalized.includes('watch')) return t('backtestTool.actionWatch', 'Watch')
  if (normalized.includes('hold') || normalized.includes('blocked')) return t('backtestTool.actionBlocked', 'Blocked')
  return signalType || '-'
}

function riskBlockReason(prediction: EventPrediction, t: ReturnType<typeof useTranslation>['t']) {
  if (prediction.allow_trade) return t('backtestTool.noRiskBlock', 'No hard block')
  const vetoReasons = prediction.veto_reasons?.length ? prediction.veto_reasons : prediction.event_signal?.veto_reasons || []
  if (vetoReasons.length) return vetoReasons[0]
  if (prediction.entry_warning) return prediction.entry_warning
  if (prediction.event_signal?.avoid_condition) return prediction.event_signal.avoid_condition
  return t('backtestTool.conditionBlocked', 'Wait until blocking conditions clear')
}

function nextTradeCondition(prediction: EventPrediction, t: ReturnType<typeof useTranslation>['t']) {
  if (prediction.allow_trade) {
    return t('backtestTool.conditionTradable', 'Conditions met; ready for paper execution')
  }
  const riskScore = prediction.risk_score ?? prediction.event_signal?.risk_score
  const readiness = predictionReadiness(prediction)
  if (typeof riskScore === 'number' && riskScore > 45) {
    return t('backtestTool.conditionRiskBelow', 'Wait for risk score below 45')
  }
  if (readiness === 'watch') {
    return t('backtestTool.conditionWatch', 'Wait for risk confirmation or a better execution window')
  }
  return t('backtestTool.conditionBlocked', 'Wait until blocking conditions clear')
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
