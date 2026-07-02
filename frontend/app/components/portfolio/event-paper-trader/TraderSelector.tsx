import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { EventPaperTrader } from '@/lib/eventContractApi'

interface TraderSelectorProps {
  traders: EventPaperTrader[]
  selectedId: number
  onChange: (id: number) => void
}

export default function TraderSelector({ traders, selectedId, onChange }: TraderSelectorProps) {
  return (
    <Select value={String(selectedId)} onValueChange={value => onChange(Number(value))}>
      <SelectTrigger className="h-8 w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {traders.map(trader => (
          <SelectItem key={trader.id} value={String(trader.id)}>
            {trader.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
