import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { EventPaperTraderBet } from '@/lib/eventContractApi'
import { formatCountdown, formatPnl, parseUtcMs } from './formatters'

interface BetsTableProps {
  bets: EventPaperTraderBet[]
  nowMs: number
}

const DIRECTION_CLASS: Record<string, string> = {
  long: 'bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/40',
  short: 'bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/40',
}

const RESULT_VARIANT: Record<string, 'default' | 'destructive' | 'secondary'> = {
  win: 'default',
  loss: 'destructive',
  draw: 'secondary',
}

export default function BetsTable({ bets, nowMs }: BetsTableProps) {
  const { t } = useTranslation()

  if (bets.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        {t('eventPaperTrader.noBets', 'No bets yet')}
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('eventPaperTrader.direction', 'Direction')}</TableHead>
          <TableHead>{t('eventPaperTrader.decisionTime', 'Decision Time')}</TableHead>
          <TableHead className="text-right">{t('eventPaperTrader.entryPrice', 'Entry Price')}</TableHead>
          <TableHead className="text-right">{t('eventPaperTrader.expiry', 'Expiry')}</TableHead>
          <TableHead className="text-right">{t('eventPaperTrader.result', 'Result')}</TableHead>
          <TableHead className="text-right">{t('eventPaperTrader.pnl', 'PnL')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {bets.map(bet => (
          <BetRow key={bet.id} bet={bet} nowMs={nowMs} t={t} />
        ))}
      </TableBody>
    </Table>
  )
}

function BetRow({ bet, nowMs, t }: { bet: EventPaperTraderBet; nowMs: number; t: TFunction }) {
  const decisionMs = parseUtcMs(bet.decision_time)
  const expiryMs = parseUtcMs(bet.expiry_time)
  const isOpen = bet.status === 'pending_entry' || bet.status === 'open'

  return (
    <TableRow>
      <TableCell>
        <span className={`rounded-md border px-2 py-0.5 text-xs ${DIRECTION_CLASS[bet.direction] ?? ''}`}>
          {t(`eventPaperTrader.${bet.direction}`, bet.direction)}
        </span>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {decisionMs != null ? new Date(decisionMs).toLocaleString() : '—'}
      </TableCell>
      <TableCell className="text-right">
        {bet.status === 'pending_entry' || bet.entry_price == null ? '—' : bet.entry_price.toFixed(2)}
      </TableCell>
      <TableCell className="text-right text-xs">
        {isOpen
          ? expiryMs != null
            ? formatCountdown(expiryMs - nowMs)
            : '—'
          : expiryMs != null
            ? new Date(expiryMs).toLocaleTimeString()
            : '—'}
      </TableCell>
      <TableCell className="text-right">
        {bet.status === 'settled' && bet.result ? (
          <Badge variant={RESULT_VARIANT[bet.result] ?? 'secondary'}>
            {t(`eventPaperTrader.${bet.result}`, bet.result)}
          </Badge>
        ) : (
          <Badge variant="outline">{t('eventPaperTrader.pending', 'Pending')}</Badge>
        )}
      </TableCell>
      <TableCell
        className={`text-right text-xs ${
          bet.status === 'settled' && bet.pnl != null
            ? bet.pnl >= 0
              ? 'text-green-500'
              : 'text-red-500'
            : 'text-muted-foreground'
        }`}
      >
        {bet.status === 'settled' && bet.pnl != null ? formatPnl(bet.pnl) : '—'}
      </TableCell>
    </TableRow>
  )
}
