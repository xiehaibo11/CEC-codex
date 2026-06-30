import { useTranslation } from 'react-i18next'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../ui/select'

interface SymbolSelectorProps {
  value: string
  symbols: string[]
  onChange: (symbol: string) => void
  triggerClassName?: string
}

export function SymbolSelector({
  value,
  symbols,
  onChange,
  triggerClassName,
}: SymbolSelectorProps) {
  const { t } = useTranslation()

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={triggerClassName}>
        <SelectValue placeholder={t('kline.selectSymbol', 'Select Symbol')} />
      </SelectTrigger>
      <SelectContent>
        {symbols.map(symbol => (
          <SelectItem key={symbol} value={symbol}>
            {symbol}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
