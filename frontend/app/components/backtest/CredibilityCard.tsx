import { useTranslation } from 'react-i18next'
import { FlaskConical, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EventBacktestSummary } from '@/lib/api'

type Props = {
  summary: EventBacktestSummary
  onHoldout: () => void
  holdoutRunning: boolean
}

function sampleTone(n: number): 'red' | 'yellow' | 'green' {
  if (n < 30) return 'red'
  if (n < 100) return 'yellow'
  return 'green'
}

const TONE_CLASS: Record<string, string> = {
  red: 'bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/40',
  yellow: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border-yellow-500/40',
  green: 'bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/40',
}

export function CredibilityCard({ summary, onHoldout, holdoutRunning }: Props) {
  const { t } = useTranslation()
  const decided = summary.decided_trades ?? 0
  const tone = sampleTone(decided)
  const ciLow = summary.win_rate_ci_low ?? 0
  const ciHigh = summary.win_rate_ci_high ?? 0
  const breakeven = summary.break_even_win_rate ?? 55.56
  const significant = summary.significant_vs_breakeven === true
  const sensitivity = summary.settlement_sensitivity
  const calibration = summary.calibration_report

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{t('backtestTool.credibility', 'Credibility')}</CardTitle>
          <Button size="sm" variant="outline" onClick={onHoldout} disabled={holdoutRunning}>
            {holdoutRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
            {t('backtestTool.holdoutRun', 'Verify on new window')}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-md border px-2 py-0.5 text-xs ${TONE_CLASS[tone]}`}>
            {t('backtestTool.sampleSize', '{{count}} decided trades', { count: decided })}
          </span>
          <Badge variant="outline">
            {t('backtestTool.winRateCi', 'Win rate 95% CI: {{low}}%–{{high}}%', { low: ciLow, high: ciHigh })}
          </Badge>
          <Badge variant={significant ? 'default' : 'secondary'}>
            {significant
              ? t('backtestTool.significant', 'Beats breakeven {{be}}% (p={{p}})', { be: breakeven, p: summary.p_value_vs_breakeven })
              : t('backtestTool.notSignificant', 'Not proven above breakeven {{be}}%', { be: breakeven })}
          </Badge>
          {summary.target_win_rate_status === 'insufficient_sample' && (
            <Badge variant="secondary">{t('backtestTool.insufficientSample', 'Sample too small to judge')}</Badge>
          )}
        </div>
        {sensitivity && (
          <p className="text-xs text-muted-foreground">
            {t('backtestTool.sensitivity', 'Settlement sensitivity: {{b2}}% of results flip at ±2bps, {{b5}}% at ±5bps, {{b10}}% at ±10bps.', {
              b2: sensitivity.bps_2, b5: sensitivity.bps_5, b10: sensitivity.bps_10,
            })}
          </p>
        )}
        {calibration?.status === 'ok' && calibration.buckets && (
          <div className="text-xs">
            <span className="text-muted-foreground">
              {t('backtestTool.calibration', 'Calibration (Brier {{score}}):', { score: calibration.brier_score })}
            </span>
            <div className="mt-1 grid grid-cols-2 gap-1 sm:grid-cols-4">
              {calibration.buckets.map(bucket => (
                <div key={bucket.range} className="rounded border px-2 py-1">
                  {t('backtestTool.calibrationBucket', 'Predicted {{range}}% → actual {{actual}}% (n={{n}})', {
                    range: bucket.range, actual: bucket.actual_win_rate, n: bucket.n,
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
