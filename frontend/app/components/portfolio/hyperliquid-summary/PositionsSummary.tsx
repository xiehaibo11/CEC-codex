import { CoinIcon } from '@/components/ui/coin-icon'
import type { Position, SummaryTranslator } from './types'

interface PositionsSummaryProps {
  positions: Position[]
  t: SummaryTranslator
}

export default function PositionsSummary({ positions, t }: PositionsSummaryProps) {
  return (
    <div className="pt-2 border-t border-border">
      <div className="text-[10px] text-muted-foreground mb-1">
        {t('account.positions', 'Positions')} {positions.length > 0 && `(${positions.length})`}
      </div>
      {positions.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {positions.slice(0, 4).map((pos, idx) => {
            const isLong = pos.side.toLowerCase() === 'long'
            const pnlColor = pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
            return (
              <div
                key={idx}
                className={`text-[10px] px-1.5 py-1 rounded border ${
                  isLong
                    ? 'bg-green-500/10 border-green-500/20'
                    : 'bg-red-500/10 border-red-500/20'
                }`}
              >
                <div className="flex items-center gap-1">
                  <CoinIcon symbol={pos.symbol} size={14} />
                  <span className={`font-medium ${isLong ? 'text-green-600' : 'text-red-600'}`}>
                    {pos.symbol} {isLong ? 'L' : 'S'}
                  </span>
                  <span className="text-muted-foreground">{pos.leverage}x</span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className="text-muted-foreground">{pos.size.toFixed(4)}</span>
                  <span className={`font-medium ${pnlColor}`}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}
                  </span>
                </div>
              </div>
            )
          })}
          {positions.length > 4 && (
            <div className="text-[10px] text-muted-foreground self-center">
              +{positions.length - 4} {t('common.more', 'more')}
            </div>
          )}
        </div>
      ) : (
        <div className="text-[10px] text-muted-foreground">{t('account.noOpenPositions', 'No open positions')}</div>
      )}
    </div>
  )
}
