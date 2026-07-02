import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Progress } from '@/components/ui/progress'
import { getEventContractValidationProgress, type EventValidationProgress } from '@/lib/eventContractApi'

type Props = {
  fingerprint: string
}

const SEGMENT_STATUS_CLASS: Record<string, string> = {
  recorded: 'bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/40',
  pending: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border-yellow-500/40',
  failed: 'bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/40',
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function RollingValidationSection({ fingerprint }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<EventValidationProgress | null>(null)

  useEffect(() => {
    let cancelled = false
    setProgress(null)
    setError(null)
    if (!fingerprint) return
    setLoading(true)
    getEventContractValidationProgress(fingerprint)
      .then(data => {
        if (!cancelled) setProgress(data)
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fingerprint])

  const segments = progress?.segments ?? []
  const n = progress?.n ?? 0
  const targetN = progress?.target_n ?? 550
  const hasSample = n > 0

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2 border-t pt-2">
      <CollapsibleTrigger className="w-full">
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
          <span className="flex items-center gap-1">
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            {t('backtestTool.rollingValidation', 'Rolling validation progress')}
          </span>
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 space-y-2 text-sm">
          {error && (
            <p className="text-xs text-red-600 dark:text-red-400">
              {t('backtestTool.rollingValidationError', 'Failed to load rolling validation progress: {{error}}', { error })}
            </p>
          )}
          {!error && progress && (
            <>
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{t('backtestTool.rollingValidationProgressLabel', 'Cumulative sample')}</span>
                  <span>{t('backtestTool.rollingValidationProgressCount', '{{n}} / {{target}}', { n, target: targetN })}</span>
                </div>
                <Progress value={n} max={targetN} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {hasSample ? (
                  <>
                    <Badge variant="outline">
                      {t('backtestTool.winRateCi', 'Win rate 95% CI: {{low}}%–{{high}}%', {
                        low: progress.ci_low,
                        high: progress.ci_high,
                      })}
                    </Badge>
                    <Badge variant="secondary">
                      {t('backtestTool.rollingValidationBreakeven', 'Breakeven {{be}}% (p={{p}})', {
                        be: progress.break_even_win_rate,
                        p: progress.p_value,
                      })}
                    </Badge>
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {t('backtestTool.rollingValidationNoSample', 'Not enough decided holdout trades yet for a confidence interval.')}
                  </span>
                )}
              </div>
              {segments.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  {t('backtestTool.rollingValidationEmpty', 'No rolling validation windows recorded yet')}
                </p>
              ) : (
                <ul className="space-y-1">
                  {segments.map((segment, idx) => (
                    <li
                      key={`${segment.window_start ?? idx}-${segment.window_end ?? idx}`}
                      className="flex items-center justify-between gap-2 rounded border px-2 py-1 text-xs"
                    >
                      <span className="text-muted-foreground">
                        {formatDate(segment.window_start)} → {formatDate(segment.window_end)}
                      </span>
                      <span className="flex items-center gap-2">
                        <span>
                          {t('backtestTool.rollingValidationSegmentStat', '{{wins}}/{{decided}} wins', {
                            wins: segment.wins,
                            decided: segment.decided,
                          })}
                        </span>
                        <span
                          className={`rounded-md border px-1.5 py-0.5 ${SEGMENT_STATUS_CLASS[segment.status] ?? ''}`}
                        >
                          {t(`backtestTool.rollingValidationStatus.${segment.status}`, segment.status)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
