import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { AlertTriangle, TrendingUp, TrendingDown, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { OrderFormProps, TimeInForce } from './order-form/types';
import { useOrderForm } from './order-form/useOrderForm';
import { TakeProfitStopLossSection } from './order-form/TakeProfitStopLossSection';
import { OrderRiskSummary } from './order-form/OrderRiskSummary';
import { ClosePositionSummary } from './order-form/ClosePositionSummary';

export default function OrderForm(props: OrderFormProps) {
  const { t } = useTranslation();
  const {
    symbolsLoading = false,
    maxLeverage,
    defaultLeverage,
  } = props;
  const {
    exchangeConfig,
    symbolOptions,
    symbol,
    setSymbol,
    side,
    setSide,
    timeInForce,
    setTimeInForce,
    size,
    setSize,
    price,
    setPrice,
    leverage,
    setLeverage,
    takeProfitPrice,
    setTakeProfitPrice,
    stopLossPrice,
    setStopLossPrice,
    loading,
    balance,
    currentPrice,
    calculateMaxSize,
    getCurrentPosition,
    handleMaxSize,
    handleClosePosition,
    handleAutoFillTakeProfit,
    handleAutoFillStopLoss,
    handleSubmit,
    resetForm,
    estimatedLiqPrice,
    requiredMargin,
    canAfford,
    showLeverageWarning,
  } = useOrderForm(props);

  return (
    <Card className="p-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <h2 className="text-xl font-bold">
            {t('order.manualTitle', 'Place {{exchange}} Order (Manual)', {
              exchange: exchangeConfig.label,
            })}
          </h2>
          <p className="text-sm text-gray-500">
            {t('order.description', 'Manual order placement for perpetual contracts')}
          </p>
        </div>

        {/* Symbol Selector */}
        <div className="space-y-2">
          <label htmlFor="symbol" className="block text-sm font-medium">
            {t('order.symbol', 'Symbol')}
          </label>
          <Select value={symbol} onValueChange={setSymbol} disabled={symbolsLoading}>
            <SelectTrigger>
              <SelectValue placeholder={symbolsLoading ? t('common.loading', 'Loading...') : undefined} />
            </SelectTrigger>
            <SelectContent>
              {symbolOptions.map((sym) => (
                <SelectItem key={sym} value={sym}>
                  {sym}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Side Selector */}
        <div className="space-y-2">
          <label className="block text-sm font-medium">{t('order.side', 'Side')}</label>
          <div className="grid grid-cols-3 gap-2">
            <Button
              type="button"
              variant={side === 'long' ? 'default' : 'outline'}
              onClick={() => setSide('long')}
              className={side === 'long' ? 'bg-green-600 hover:bg-green-700' : ''}
            >
              <TrendingUp className="w-4 h-4 mr-1" />
              {t('order.long', 'Long')}
            </Button>
            <Button
              type="button"
              variant={side === 'short' ? 'default' : 'outline'}
              onClick={() => setSide('short')}
              className={side === 'short' ? 'bg-red-600 hover:bg-red-700' : ''}
            >
              <TrendingDown className="w-4 h-4 mr-1" />
              {t('order.short', 'Short')}
            </Button>
            {/* Removed: Close Position button - use PositionsTable for closing positions */}
            {/* <Button
              type="button"
              variant={side === 'close' ? 'default' : 'outline'}
              onClick={() => setSide('close')}
            >
              Close Position
            </Button> */}
          </div>
        </div>

        {/* Time In Force */}
        <div className="space-y-2">
          <label htmlFor="timeInForce" className="block text-sm font-medium">
            {t('order.timeInForce', 'Time In Force')}
          </label>
          <Select value={timeInForce} onValueChange={(value: TimeInForce) => setTimeInForce(value)}>
            <SelectTrigger id="timeInForce">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Ioc">
                <div className="flex flex-col items-start">
                  <span className="font-medium">{t('order.iocRecommended', 'Ioc (Recommended)')}</span>
                  <span className="text-xs text-gray-500">{t('order.iocDesc', 'Immediate or Cancel - executes like market order')}</span>
                </div>
              </SelectItem>
              <SelectItem value="Gtc">
                <div className="flex flex-col items-start">
                  <span className="font-medium">Gtc</span>
                  <span className="text-xs text-gray-500">{t('order.gtcDesc', 'Good Till Canceled - limit order stays on book')}</span>
                </div>
              </SelectItem>
              <SelectItem value="Alo">
                <div className="flex flex-col items-start">
                  <span className="font-medium">{t('order.aloAdvanced', 'Alo (Advanced)')}</span>
                  <span className="text-xs text-gray-500">{t('order.aloDesc', 'Add Liquidity Only - maker-only orders')}</span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Size Input */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label htmlFor="size" className="block text-sm font-medium">
              {t('order.size', 'Size')}
            </label>
            {side !== 'close' && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleMaxSize}
                disabled={!balance || balance.availableBalance <= 0 || !currentPrice}
              >
                {t('order.max', 'Max')}
              </Button>
            )}
            {side === 'close' && getCurrentPosition() && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleClosePosition}
              >
                {t('order.fullPosition', 'Full Position')}
              </Button>
            )}
          </div>
          <div className="relative">
            <Input
              id="size"
              type="number"
              step="0.0001"
              value={size}
              onChange={(e) => setSize(e.target.value)}
              placeholder="0.0"
              className="pr-16"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">
              {symbol}
            </span>
          </div>
          {side !== 'close' && !canAfford && size && parseFloat(size) > 0 && (
            <p className="text-sm text-red-600">
              {t('order.insufficientFunds', 'Insufficient funds, max available:')} {calculateMaxSize().toFixed(4)} {symbol}
            </p>
          )}
          {side === 'close' && !getCurrentPosition() && (
            <p className="text-sm text-yellow-600">
              {t('order.noPositionFound', 'No {{symbol}} position found', { symbol })}
            </p>
          )}
        </div>

        {/* Leverage Slider (only for open positions) */}
        {side !== 'close' && (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label htmlFor="leverage" className="text-sm font-medium">
                {t('order.leverage', 'Leverage')}
              </label>
              <span className="text-sm font-bold">{leverage}x</span>
            </div>
            <input
              id="leverage"
              type="range"
              min="1"
              max={maxLeverage}
              value={leverage}
              onChange={(e) => setLeverage(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            {showLeverageWarning && (
              <div className="flex items-center space-x-2 text-yellow-600 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>{t('order.highLeverageWarning', 'High leverage increases liquidation risk')}</span>
              </div>
            )}
          </div>
        )}

        {/* Price Input */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label htmlFor="price" className="block text-sm font-medium">
              {t('order.limitPrice', 'Limit Price')}
            </label>
            {currentPrice > 0 && (
              <span className="text-sm text-gray-500">
                {t('order.market', 'Market')}: ${currentPrice.toFixed(2)}
              </span>
            )}
          </div>
          <div className="relative">
            <Input
              id="price"
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              className="pr-16"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">
              USDC
            </span>
          </div>
          {price && currentPrice > 0 && (
            <p className="text-sm text-gray-600">
              {side === 'long' ? t('order.buy', 'Buy') : t('order.sell', 'Sell')} {t('order.priceIs', 'price is')}{' '}
              {((parseFloat(price) - currentPrice) / currentPrice * 100).toFixed(2)}%{' '}
              {parseFloat(price) > currentPrice ? t('order.aboveMarket', 'above') : t('order.belowMarket', 'below')} {t('order.market', 'market')}
            </p>
          )}
        </div>

        {/* Take Profit / Stop Loss (only for open positions) */}
        {side !== 'close' && (
          <TakeProfitStopLossSection
            takeProfitPrice={takeProfitPrice}
            setTakeProfitPrice={setTakeProfitPrice}
            stopLossPrice={stopLossPrice}
            setStopLossPrice={setStopLossPrice}
            onAutoFillTakeProfit={handleAutoFillTakeProfit}
            onAutoFillStopLoss={handleAutoFillStopLoss}
            autoFillDisabled={!price && !currentPrice}
          />
        )}

        {/* Risk Information */}
        {side !== 'close' && size && parseFloat(size) > 0 && (
          <OrderRiskSummary
            estimatedLiqPrice={estimatedLiqPrice}
            requiredMargin={requiredMargin}
            canAfford={canAfford}
            balance={balance}
          />
        )}

        {/* Position Information (for close orders) */}
        {side === 'close' && (
          <ClosePositionSummary position={getCurrentPosition()} symbol={symbol} />
        )}

        {/* Action Buttons */}
        <div className="flex space-x-3">
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={resetForm}
          >
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button
            type="submit"
            disabled={loading || !canAfford}
            className="flex-1"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {t('order.placing', 'Placing...')}
              </>
            ) : (
              t('order.placeOrder', 'Place Order')
            )}
          </Button>
        </div>
      </form>
    </Card>
  );
}
