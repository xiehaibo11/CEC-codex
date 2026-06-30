import type { Position } from '../HyperliquidMultiAccountSummary'
import type { AccountDetailTranslator } from './types'

interface PositionsSectionProps {
  positions: Position[]
  t: AccountDetailTranslator
}

export default function PositionsSection({ positions, t }: PositionsSectionProps) {
  if (positions.length === 0) {
    return (
      <div className="border rounded-lg p-4">
        <h3 className="text-sm font-semibold mb-3">{t('accountDetail.openPositions', 'Open Positions')}</h3>
        <div className="text-sm text-muted-foreground">{t('accountDetail.noOpenPositions', 'No open positions')}</div>
      </div>
    )
  }

  return (
    <div className="border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">{t('accountDetail.openPositions', 'Open Positions')} ({positions.length})</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="text-left py-2 pr-2">{t('accountDetail.symbol', 'Symbol')}</th>
              <th className="text-left py-2 pr-2">{t('accountDetail.side', 'Side')}</th>
              <th className="text-right py-2 pr-2">{t('accountDetail.size', 'Size')}</th>
              <th className="text-right py-2 pr-2">{t('accountDetail.entry', 'Entry')}</th>
              <th className="text-right py-2 pr-2">{t('accountDetail.mark', 'Mark')}</th>
              <th className="text-right py-2 pr-2">{t('accountDetail.pnl', 'PnL')}</th>
              <th className="text-right py-2">{t('accountDetail.lev', 'Lev')}</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos, idx) => {
              const pnlColor = pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
              const sideColor = pos.side.toLowerCase() === 'long' ? 'text-green-600' : 'text-red-600'
              return (
                <tr key={idx} className="border-b last:border-0">
                  <td className="py-2 pr-2 font-medium">{pos.symbol}</td>
                  <td className={`py-2 pr-2 ${sideColor}`}>{pos.side}</td>
                  <td className="py-2 pr-2 text-right">{pos.size.toFixed(4)}</td>
                  <td className="py-2 pr-2 text-right">${pos.entry_price.toLocaleString()}</td>
                  <td className="py-2 pr-2 text-right">${pos.mark_price.toLocaleString()}</td>
                  <td className={`py-2 pr-2 text-right font-medium ${pnlColor}`}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}
                  </td>
                  <td className="py-2 text-right">{pos.leverage}x</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
