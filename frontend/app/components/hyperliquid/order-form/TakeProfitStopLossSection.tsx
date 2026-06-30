import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface TakeProfitStopLossSectionProps {
  takeProfitPrice: string;
  setTakeProfitPrice: (value: string) => void;
  stopLossPrice: string;
  setStopLossPrice: (value: string) => void;
  onAutoFillTakeProfit: () => void;
  onAutoFillStopLoss: () => void;
  autoFillDisabled: boolean;
}

/** Optional take-profit / stop-loss inputs, shown only for open positions. */
export function TakeProfitStopLossSection({
  takeProfitPrice,
  setTakeProfitPrice,
  stopLossPrice,
  setStopLossPrice,
  onAutoFillTakeProfit,
  onAutoFillStopLoss,
  autoFillDisabled,
}: TakeProfitStopLossSectionProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      {/* Take Profit */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <label htmlFor="takeProfit" className="block text-sm font-medium">
            {t('order.takeProfitOptional', 'Take Profit Price (Optional)')}
          </label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAutoFillTakeProfit}
            disabled={autoFillDisabled}
          >
            {t('order.autoFill', 'Auto Fill')}
          </Button>
        </div>
        <div className="relative">
          <Input
            id="takeProfit"
            type="number"
            step="0.01"
            value={takeProfitPrice}
            onChange={(e) => setTakeProfitPrice(e.target.value)}
            placeholder="0.00"
            className="pr-16"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">
            USDC
          </span>
        </div>
        <p className="text-xs text-gray-500">
          {t('order.takeProfitHint', 'Auto-fill sets +10% profit target from entry price')}
        </p>
      </div>

      {/* Stop Loss */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <label htmlFor="stopLoss" className="block text-sm font-medium">
            {t('order.stopLossOptional', 'Stop Loss Price (Optional)')}
          </label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAutoFillStopLoss}
            disabled={autoFillDisabled}
          >
            {t('order.autoFill', 'Auto Fill')}
          </Button>
        </div>
        <div className="relative">
          <Input
            id="stopLoss"
            type="number"
            step="0.01"
            value={stopLossPrice}
            onChange={(e) => setStopLossPrice(e.target.value)}
            placeholder="0.00"
            className="pr-16"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">
            USDC
          </span>
        </div>
        <p className="text-xs text-gray-500">
          {t('order.stopLossHint', 'Auto-fill sets -5% stop loss from entry price')}
        </p>
      </div>
    </div>
  );
}
