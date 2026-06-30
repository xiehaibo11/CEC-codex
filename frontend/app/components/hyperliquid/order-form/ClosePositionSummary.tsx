import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import type { HyperliquidPosition } from '@/lib/types/hyperliquid';

interface ClosePositionSummaryProps {
  position: HyperliquidPosition | undefined;
  symbol: string;
}

/** Position information panel shown when closing a position. */
export function ClosePositionSummary({ position, symbol }: ClosePositionSummaryProps) {
  const { t } = useTranslation();

  return (
    <div className="p-4 bg-blue-50 rounded-lg space-y-2">
      {position ? (
        <>
          <div className="flex justify-between text-sm">
            <span className="text-gray-700">{t('order.currentPosition', 'Current Position')}</span>
            <span className="font-medium">
              {Math.abs(position.szi)} {symbol}
              ({position.szi > 0 ? 'LONG' : 'SHORT'})
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-700">{t('order.entryPrice', 'Entry Price')}</span>
            <span className="font-medium">${position.entryPx.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-700">{t('order.unrealizedPnl', 'Unrealized PnL')}</span>
            <span className={`font-medium ${position.unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${position.unrealizedPnl.toFixed(2)}
            </span>
          </div>
        </>
      ) : (
        <div className="flex items-center space-x-2 text-yellow-600 text-sm">
          <AlertTriangle className="w-4 h-4" />
          <span>{t('order.noPositionFound', 'No {{symbol}} position found', { symbol })}</span>
        </div>
      )}
    </div>
  );
}
