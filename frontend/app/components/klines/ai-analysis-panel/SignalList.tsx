import { useTranslation } from 'react-i18next'
import { Badge } from '../../ui/badge'
import { FLOW_INDICATOR_LABELS } from './formatters'

interface SignalListProps {
  selectedIndicators: string[]
  selectedFlowIndicators: string[]
}

export function SignalList({ selectedIndicators, selectedFlowIndicators }: SignalListProps) {
  const { t } = useTranslation()

  return (
    <>
      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">{t('kline.analysis.indicatorsIncluded', 'Indicators Included')}</div>
        {selectedIndicators.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {selectedIndicators.map((indicator) => (
              <Badge key={indicator} variant="secondary" className="text-[11px] px-2 py-1">
                {indicator}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            {t('kline.analysis.selectIndicatorsHint', 'Select indicators in "Technical Indicators" to include them in AI analysis.')}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">{t('kline.analysis.flowIncluded', 'Market Flow Included')}</div>
        {selectedFlowIndicators.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {selectedFlowIndicators.map((key) => (
              <Badge key={key} className="text-[11px] px-2 py-1 bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                {FLOW_INDICATOR_LABELS[key] || key}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            {t('kline.analysis.selectFlowHint', 'Select indicators in "Market Flow" to include them in AI analysis.')}
          </p>
        )}
      </div>
    </>
  )
}
