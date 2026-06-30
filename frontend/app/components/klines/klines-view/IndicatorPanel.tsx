import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card'
import { TECHNICAL_INDICATOR_GROUPS } from './constants'

interface IndicatorPanelProps {
  selectedIndicators: string[]
  onToggleIndicator: (indicator: string) => void
}

export function IndicatorPanel({
  selectedIndicators,
  onToggleIndicator,
}: IndicatorPanelProps) {
  const { t } = useTranslation()

  return (
    <Card className="lg:col-span-2">
      <CardHeader className="py-3">
        <CardTitle className="text-sm">{t('kline.technicalIndicators', 'Technical Indicators')}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-1.5">
        {TECHNICAL_INDICATOR_GROUPS.map(({ labelKey, fallback, indicators }) => (
          <div key={labelKey} className="flex items-center gap-2">
            <span className="text-[9px] text-muted-foreground font-medium min-w-[52px]">
              {t(labelKey, fallback)}
            </span>
            <div className="flex gap-1 flex-wrap">
              {indicators.map(indicator => (
                <button
                  key={indicator}
                  onClick={() => onToggleIndicator(indicator)}
                  className={`px-1.5 py-0.5 text-[10px] rounded transition-colors min-w-[38px] ${
                    selectedIndicators.includes(indicator)
                      ? 'bg-primary/20 text-primary border border-primary/30'
                      : 'hover:bg-muted border'
                  }`}
                >
                  {indicator}
                </button>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
