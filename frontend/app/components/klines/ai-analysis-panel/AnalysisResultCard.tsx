import { useTranslation } from 'react-i18next'
import { Button } from '../../ui/button'
import { Card, CardContent } from '../../ui/card'
import { AnalysisHeader } from './AnalysisHeader'
import { getAnalysisSummary } from './formatters'
import { MarkdownDisplay } from './MarkdownDisplay'
import type { AnalysisResult } from './types'

interface AnalysisResultCardProps {
  result: AnalysisResult
  onViewFull: () => void
}

export function AnalysisResultCard({ result, onViewFull }: AnalysisResultCardProps) {
  const { t } = useTranslation()

  return (
    <Card className="mt-3">
      <AnalysisHeader result={result} />
      <CardContent className="py-2 space-y-3">
        {result.success && result.analysis ? (
          <>
            <MarkdownDisplay content={getAnalysisSummary(result.analysis)} />
            <div className="flex justify-end">
              <Button
                variant="default"
                size="sm"
                onClick={onViewFull}
                className="text-xs"
              >
                {t('kline.analysis.viewFull', 'View Full Analysis')}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm text-red-600">
            {result.error || t('kline.analysis.analysisFailed', 'Analysis failed')}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
