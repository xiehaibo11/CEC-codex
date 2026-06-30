import { useTranslation } from 'react-i18next'
import { CardHeader, CardTitle } from '../../ui/card'
import type { AnalysisResult } from './types'

interface AnalysisHeaderProps {
  result: AnalysisResult
}

export function AnalysisHeader({ result }: AnalysisHeaderProps) {
  const { t } = useTranslation()

  return (
    <CardHeader className="py-2">
      <CardTitle className="text-sm flex items-center justify-between">
        <span>
          {result.success ? t('kline.analysis.analysisResult', 'Analysis Result') : t('kline.analysis.analysisFailed', 'Analysis Failed')}
          {result.trader_name && ` - ${result.trader_name}`}
        </span>
      </CardTitle>
    </CardHeader>
  )
}
