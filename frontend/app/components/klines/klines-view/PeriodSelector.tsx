import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../ui/select'
import { KLINE_PERIODS } from './constants'

interface PeriodSelectorProps {
  value: string
  onChange: (period: string) => void
  triggerClassName?: string
}

export function PeriodSelector({ value, onChange, triggerClassName }: PeriodSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={triggerClassName}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {KLINE_PERIODS.map(period => (
          <SelectItem key={period} value={period}>
            {period}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
