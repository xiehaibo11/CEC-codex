import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import type { DecisionChainItem } from './types'

interface DecisionCardProps {
  decision: DecisionChainItem
  isFirst: boolean
  isLast: boolean
}

export function DecisionCard({ decision, isFirst, isLast }: DecisionCardProps) {
  const { t } = useTranslation()

  const getOperationColor = (op: string) => {
    switch (op) {
      case 'buy': return 'bg-green-500'
      case 'sell': return 'bg-red-500'
      case 'close': return 'bg-blue-500'
      case 'hold': return 'bg-gray-400'
      default: return 'bg-gray-400'
    }
  }

  const getOperationLabel = (op: string) => {
    switch (op) {
      case 'buy': return t('attribution.replay.opBuy', 'BUY')
      case 'sell': return t('attribution.replay.opSell', 'SELL')
      case 'close': return t('attribution.replay.opClose', 'CLOSE')
      case 'hold': return t('attribution.replay.opHold', 'HOLD')
      default: return op.toUpperCase()
    }
  }

  return (
    <div className="relative">
      {!isLast && (
        <div className="absolute left-4 top-10 w-0.5 h-full bg-border" />
      )}
      <Card className={`relative ${isFirst || isLast ? 'border-primary' : ''}`}>
        <CardContent className="p-3">
          <div className="flex items-start gap-3">
            <div className={`w-8 h-8 rounded-full ${getOperationColor(decision.operation)} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
              {decision.operation.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="font-medium">{getOperationLabel(decision.operation)}</span>
                {decision.realized_pnl !== null && (
                  <span className={`text-sm font-medium ${decision.realized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${decision.realized_pnl.toFixed(2)}
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {decision.decision_time ? new Date(decision.decision_time + 'Z').toLocaleString() : '-'}
              </div>
              {decision.reason && (
                <div className="text-xs text-muted-foreground mt-2 line-clamp-3">
                  {decision.reason}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
