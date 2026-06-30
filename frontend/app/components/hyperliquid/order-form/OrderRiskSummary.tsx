import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';
import type { HyperliquidBalance } from '@/lib/types/hyperliquid';

interface OrderRiskSummaryProps {
  estimatedLiqPrice: number;
  requiredMargin: number;
  canAfford: boolean;
  balance: HyperliquidBalance | null;
}

/** Risk information panel shown for open orders with a positive size. */
export function OrderRiskSummary({
  estimatedLiqPrice,
  requiredMargin,
  canAfford,
  balance,
}: OrderRiskSummaryProps) {
  const { t } = useTranslation();

  return (
    <div className="p-4 bg-gray-50 rounded-lg space-y-2">
      {estimatedLiqPrice > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center text-gray-700">
            <AlertTriangle className="w-4 h-4 mr-1 text-yellow-600" />
            {t('order.estimatedLiquidation', 'Estimated Liquidation')}
          </span>
          <span className="font-medium">${estimatedLiqPrice.toFixed(2)}</span>
        </div>
      )}

      <div className="flex justify-between text-sm">
        <span className="text-gray-700">{t('order.requiredMargin', 'Required Margin')}</span>
        <span className={`font-medium ${canAfford ? 'text-green-600' : 'text-red-600'}`}>
          ${requiredMargin.toFixed(2)}
        </span>
      </div>

      {balance && (
        <div className="flex justify-between text-sm">
          <span className="text-gray-700">{t('order.availableBalance', 'Available Balance')}</span>
          <span className="font-medium">${balance.availableBalance.toFixed(2)}</span>
        </div>
      )}

      {!canAfford && (
        <div className="flex items-center space-x-2 text-red-600 text-sm pt-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{t('order.insufficientBalance', 'Insufficient balance for this order')}</span>
        </div>
      )}
    </div>
  );
}
