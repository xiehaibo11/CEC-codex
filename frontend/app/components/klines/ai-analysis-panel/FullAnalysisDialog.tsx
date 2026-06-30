import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../ui/dialog'
import { MarkdownDisplay } from './MarkdownDisplay'
import { ReasoningDisplay } from './ReasoningDisplay'
import type { AnalysisResult } from './types'

interface FullAnalysisDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  symbol: string
  period: string
  result: AnalysisResult | null
  showPrompt: boolean
  onTogglePrompt: () => void
}

export function FullAnalysisDialog({
  open,
  onOpenChange,
  symbol,
  period,
  result,
  showPrompt,
  onTogglePrompt,
}: FullAnalysisDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-[1200px] max-h-[85vh] overflow-y-auto"
        aria-describedby={undefined}
      >
        <DialogHeader>
          <DialogTitle>
            {symbol} {period} {t('kline.analysis.reportTitle', 'AI Analysis Report')}
            {result?.trader_name && ` - ${result.trader_name}`}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-md border p-4 bg-background">
            <MarkdownDisplay content={result?.analysis || ''} variant="full" />
          </div>
          <ReasoningDisplay
            prompt={result?.prompt}
            showPrompt={showPrompt}
            onTogglePrompt={onTogglePrompt}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
