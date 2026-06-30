import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { CheckCircle2 } from 'lucide-react'
import PacmanLoader from '@/components/ui/pacman-loader'
import { KLINE_PERIODS, FORWARD_PERIODS } from './constants'
import type { FactorLibraryController } from './useFactorLibrary'

export default function ComputeDialog({ ctrl }: { ctrl: FactorLibraryController }) {
  const {
    t, period, computing, computeDialogOpen, setComputeDialogOpen, dialogStep,
    computeEstimate, computeAllPeriods, handleComputeAllPeriodsChange, handleComputeConfirm,
    computeProgress, computeResult,
  } = ctrl

  return (
    <Dialog open={computeDialogOpen} onOpenChange={(open) => {
      if (!open && computing) return
      setComputeDialogOpen(open)
    }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('factors.computeConfirmTitle')}</DialogTitle>
          <DialogDescription className="space-y-1">
            <span className="block">
              {t('factors.estimateKlinePeriods')}: {(computeEstimate?.kline_periods || (computeAllPeriods ? KLINE_PERIODS : [period])).join(', ')}
            </span>
            <span className="block">{t('factors.predictionWindowsSummary', { windows: computeEstimate?.forward_periods?.join(', ') || FORWARD_PERIODS.join(', ') })}</span>
          </DialogDescription>
        </DialogHeader>
        {dialogStep === 'confirm' && (
          <>
            <div className="py-4 space-y-3">
              <p className="text-sm">{t('factors.confirmCompute')}</p>
              <div className="flex items-start gap-2 rounded-md border px-3 py-2">
                <Checkbox
                  id="compute-all-kline-periods"
                  checked={computeAllPeriods}
                  onCheckedChange={handleComputeAllPeriodsChange}
                  className="mt-0.5"
                />
                <label htmlFor="compute-all-kline-periods" className="text-xs leading-5 cursor-pointer">
                  {t('factors.computeAllKlinePeriods')}
                </label>
              </div>
              {computeEstimate && (
                <div className="rounded-md bg-muted p-3 space-y-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">{t('factors.estimateSymbols')} ({computeEstimate.symbol_count}):</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {computeEstimate.symbols?.map((s: string) => (
                        <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
                      ))}
                    </div>
                  </div>
                  <p>{t('factors.estimateKlinePeriods')}: <span className="font-medium">{computeEstimate.kline_periods?.join(', ') || computeEstimate.kline_period || computeEstimate.period || period}</span></p>
                  <p>{t('factors.estimateFactors')}: <span className="font-medium">{computeEstimate.factor_count}</span></p>
                  <p>{t('factors.estimateWindows')}: <span className="font-medium">{computeEstimate.forward_periods?.join(', ')}</span></p>
                  <p>{t('factors.estimateTime')}: <span className="font-medium">~{Math.max(1, Math.ceil((computeEstimate.estimated_seconds || 0) / 60))} min</span></p>
                </div>
              )}
            </div>
            <DialogFooter className="gap-2 sm:gap-0">
              <DialogClose asChild><Button variant="outline" size="sm">{t('common.cancel')}</Button></DialogClose>
              <Button size="sm" onClick={handleComputeConfirm}
                disabled={!computeEstimate || computeEstimate.symbol_count === 0}>
                {t('factors.startCompute')}
              </Button>
            </DialogFooter>
          </>
        )}
        {dialogStep === 'progress' && (
          <div className="py-6">
            <div className="flex flex-col items-center gap-3">
              <PacmanLoader className="w-16 h-8 text-primary" />
              <p className="text-sm font-medium">{t('factors.computing')}</p>
              {computeProgress?.status === 'running' && (
                <div className="w-full space-y-2">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{computeProgress.phase === 'values' ? t('factors.phaseValues') : t('factors.phaseEffectiveness')}</span>
                    <span>{computeProgress.period ? `${computeProgress.period} / ` : ''}{computeProgress.current_symbol} ({computeProgress.completed}/{computeProgress.total})</span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div className="bg-primary h-2 rounded-full transition-all duration-500"
                      style={{ width: `${computeProgress.total > 0 ? (computeProgress.completed / computeProgress.total) * 100 : 0}%` }} />
                  </div>
                  {computeProgress.phase === 'effectiveness' && computeProgress.current_factor && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span className="font-mono">{computeProgress.current_factor}</span>
                        <span>{computeProgress.factor_completed}/{computeProgress.factor_total}</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-1.5">
                        <div className="bg-primary/60 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${computeProgress.factor_total > 0 ? (computeProgress.factor_completed / computeProgress.factor_total) * 100 : 0}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
        {dialogStep === 'done' && (
          <>
            <div className="py-4">
              {computeResult?.error ? (
                <div className="text-center text-red-500 text-sm">{computeResult.error}</div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                  <p className="text-sm font-medium">{t('factors.computeSuccess')}</p>
                  <div className="text-xs text-muted-foreground space-y-1">
                    <p>{t('factors.estimateKlinePeriods')}: {(computeResult?.kline_periods || [computeResult?.period || period]).join(', ')}</p>
                    <p>{t('factors.resultSymbols')}: {computeResult?.values_computed ?? 0}</p>
                    <p>{t('factors.resultEffectiveness')}: {computeResult?.effectiveness_computed ?? 0}</p>
                  </div>
                </div>
              )}
            </div>
            <DialogFooter>
              <DialogClose asChild><Button variant="outline" size="sm">{t('common.close')}</Button></DialogClose>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
