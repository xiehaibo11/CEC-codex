import { useTranslation } from 'react-i18next'
import { CHART_TYPES } from './constants'
import type { ChartType } from './types'

interface ChartControlsProps {
  chartType: ChartType
  onChartTypeChange: (chartType: ChartType) => void
}

export function ChartControls({ chartType, onChartTypeChange }: ChartControlsProps) {
  const { t } = useTranslation()

  return (
    <div className="hidden md:flex gap-1 bg-background/80 backdrop-blur-sm rounded-md p-1 border">
      {CHART_TYPES.map(({ value, labelKey, fallback }) => (
        <button
          key={value}
          onClick={() => onChartTypeChange(value)}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            chartType === value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
          }`}
        >
          {t(labelKey, fallback)}
        </button>
      ))}
    </div>
  )
}
