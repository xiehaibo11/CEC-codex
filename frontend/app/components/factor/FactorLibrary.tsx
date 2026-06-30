import { TooltipProvider } from '@/components/ui/tooltip'
import FactorAnalysisDialog from './FactorAnalysisDialog'
import {
  ControlsRow,
  ComputeDialog,
  CustomFactorLabDialog,
  CategoryFilter,
  FactorTable,
  useFactorLibrary,
} from './factor-library'

export default function FactorLibrary() {
  const ctrl = useFactorLibrary()
  const {
    t, loading, library, analysisOpen, setAnalysisOpen, analysisFactor,
    symbol, period, exchange, forwardPeriod,
  } = ctrl

  if (loading && !library) {
    return <div className="flex items-center justify-center h-40 text-muted-foreground">{t('factors.loading')}</div>
  }

  return (
    <TooltipProvider>
      <div className="flex flex-col flex-1 min-h-0 space-y-3">
        {/* Controls row */}
        <ControlsRow ctrl={ctrl} />

        {/* Compute dialog */}
        <ComputeDialog ctrl={ctrl} />

        {/* Custom Factor Lab Dialog */}
        <CustomFactorLabDialog ctrl={ctrl} />

        {/* Category filter - includes Custom */}
        <CategoryFilter ctrl={ctrl} />

        {/* Data table */}
        <FactorTable ctrl={ctrl} />
      </div>
      <FactorAnalysisDialog
        open={analysisOpen}
        onOpenChange={setAnalysisOpen}
        factorName={analysisFactor.name}
        displayName={analysisFactor.displayName}
        symbol={symbol}
        period={period}
        exchange={exchange}
        forwardPeriod={forwardPeriod}
      />
    </TooltipProvider>
  )
}
