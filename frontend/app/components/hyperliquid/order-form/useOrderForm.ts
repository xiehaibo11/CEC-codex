import { useMemo, useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import {
  estimateLiquidationPrice,
  calculateRequiredMargin,
} from '@/lib/hyperliquidApi';
import type { HyperliquidBalance, HyperliquidPosition } from '@/lib/types/hyperliquid';
import { getManualTradingExchangeConfig } from '../manualTradingExchanges';
import { getManualTradingAdapter } from '../manualTradingApi';
import type { OrderFormProps, OrderSide, TimeInForce } from './types';

/**
 * useOrderForm - encapsulates all state, data loading, handlers, and derived
 * values for the manual OrderForm. The presentational component consumes the
 * returned bag of values/handlers. Behaviour is identical to the original
 * inline implementation.
 */
export function useOrderForm({
  accountId,
  environment,
  exchange,
  availableSymbols,
  maxLeverage,
  defaultLeverage,
  onOrderPlaced,
}: OrderFormProps) {
  const exchangeConfig = getManualTradingExchangeConfig(exchange);
  const exchangeAdapter = getManualTradingAdapter(exchange);
  const symbolOptions = useMemo(
    () => (availableSymbols.length > 0 ? availableSymbols : exchangeConfig.defaultSymbols),
    [availableSymbols, exchangeConfig]
  );
  const [symbol, setSymbol] = useState(symbolOptions[0] || 'BTC');
  const [side, setSide] = useState<OrderSide>('long');
  const [timeInForce, setTimeInForce] = useState<TimeInForce>('Ioc');
  const [size, setSize] = useState('');
  const [price, setPrice] = useState('');
  const [leverage, setLeverage] = useState(defaultLeverage);
  const [takeProfitPrice, setTakeProfitPrice] = useState('');
  const [stopLossPrice, setStopLossPrice] = useState('');
  const [loading, setLoading] = useState(false);
  const [balance, setBalance] = useState<HyperliquidBalance | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [positions, setPositions] = useState<HyperliquidPosition[]>([]);

  useEffect(() => {
    loadBalance();
    loadPositions();
  }, [accountId, environment, exchange]);

  useEffect(() => {
    if (symbolOptions.length > 0 && !symbolOptions.includes(symbol)) {
      setSymbol(symbolOptions[0]);
    }
  }, [symbolOptions, symbol]);

  useEffect(() => {
    setLeverage(defaultLeverage);
  }, [defaultLeverage]);

  useEffect(() => {
    setPrice('');
    loadCurrentPrice();
  }, [symbol, exchange]);

  useEffect(() => {
    if (currentPrice > 0 && !price) {
      const adjustedPrice = side === 'long' ? currentPrice * 1.001 : currentPrice * 0.999;
      setPrice(adjustedPrice.toFixed(2));
    }
  }, [currentPrice, side, price]);

  const loadBalance = async () => {
    try {
      const data = await exchangeAdapter.getBalance(accountId, environment);
      setBalance(data);
    } catch (error) {
      console.error('Failed to load balance:', error);
    }
  };

  const loadCurrentPrice = async () => {
    try {
      const priceValue = await exchangeAdapter.getPrice(symbol);
      setCurrentPrice(priceValue);
    } catch (error) {
      console.error('Failed to load current price:', error);
    }
  };

  const loadPositions = async () => {
    try {
      const data = await exchangeAdapter.getPositions(accountId, environment);
      setPositions(data.positions || []);
    } catch (error) {
      console.error('Failed to load positions:', error);
    }
  };

  const calculateMaxSize = () => {
    if (!balance || balance.availableBalance <= 0) return 0;
    const priceToUse = price ? parseFloat(price) : currentPrice;
    if (!priceToUse || priceToUse <= 0) return 0;
    return (balance.availableBalance * leverage) / priceToUse;
  };

  const getCurrentPosition = () => {
    return positions.find(pos => pos.coin === symbol);
  };

  const handleMaxSize = () => {
    const maxSize = calculateMaxSize();
    if (maxSize > 0) {
      setSize(maxSize.toFixed(4));
    }
  };

  const handleClosePosition = () => {
    const position = getCurrentPosition();
    if (position) {
      // For close position, always use absolute value of position size
      const positionSize = Math.abs(position.szi);
      setSize(positionSize.toString());
    }
  };

  const handleAutoFillTakeProfit = () => {
    const priceToUse = price ? parseFloat(price) : currentPrice;
    if (priceToUse > 0) {
      // 10% profit for long, 10% profit for short
      const tpPrice = side === 'long'
        ? priceToUse * 1.1
        : priceToUse * 0.9;
      setTakeProfitPrice(tpPrice.toFixed(2));
    }
  };

  const handleAutoFillStopLoss = () => {
    const priceToUse = price ? parseFloat(price) : currentPrice;
    if (priceToUse > 0) {
      // 5% loss for long, 5% loss for short
      const slPrice = side === 'long'
        ? priceToUse * 0.95
        : priceToUse * 1.05;
      setStopLossPrice(slPrice.toFixed(2));
    }
  };

  const resetForm = () => {
    setSize('');
    setPrice('');
    setLeverage(defaultLeverage);
    setTakeProfitPrice('');
    setStopLossPrice('');
    setTimeInForce('Ioc');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!size || parseFloat(size) <= 0) {
      toast.error('Please enter a valid size');
      return;
    }

    if (!price || parseFloat(price) <= 0) {
      toast.error('Please enter a valid price');
      return;
    }

    if (side !== 'close' && leverage > maxLeverage) {
      toast.error(`Leverage cannot exceed ${maxLeverage}x`);
      return;
    }

    if (side === 'close' && !getCurrentPosition()) {
      toast.error(`No position found for ${symbol}`);
      return;
    }

    setLoading(true);
    try {
      // For close position, determine correct direction based on current position
      let isBuy = side === 'long';
      if (side === 'close') {
        const position = getCurrentPosition();
        if (position) {
          isBuy = position.szi < 0;
        }
      }

      const result = await exchangeAdapter.placeOrder({
        accountId,
        environment,
        symbol,
        isBuy,
        size: parseFloat(size),
        price: parseFloat(price),
        timeInForce,
        reduceOnly: side === 'close',
        leverage: side !== 'close' ? leverage : 1,
        takeProfitPrice: takeProfitPrice && parseFloat(takeProfitPrice) > 0 ? parseFloat(takeProfitPrice) : undefined,
        stopLossPrice: stopLossPrice && parseFloat(stopLossPrice) > 0 ? parseFloat(stopLossPrice) : undefined,
      });

      const priceText = result.averagePrice ? ` @ $${Number(result.averagePrice).toFixed(2)}` : '';
      if (result.status === 'filled') {
        toast.success(`Order Filled! ${side.toUpperCase()} ${size} ${symbol}${priceText}`);
      } else if (result.status === 'resting') {
        toast.success(`Order Placed! ${side.toUpperCase()} ${size} ${symbol}${priceText} (waiting to fill)`);
      } else {
        toast.error(`Order failed: ${result.error || result.status || 'Unknown error'}`);
      }

      // Reset form
      setSize('');
      setPrice('');
      setLeverage(defaultLeverage);
      setTakeProfitPrice('');
      setStopLossPrice('');
      setTimeInForce('Ioc');

      // Reload balance, positions and notify parent
      await loadBalance();
      await loadPositions();
      if (onOrderPlaced) {
        onOrderPlaced();
      }
    } catch (error: any) {
      console.error('Failed to place order:', error);
      toast.error(error.message || 'Failed to place order');
    } finally {
      setLoading(false);
    }
  };

  const estimatedLiqPrice =
    side !== 'close' && size && parseFloat(size) > 0
      ? estimateLiquidationPrice(
          parseFloat(price || '0'),
          leverage,
          side === 'long'
        )
      : 0;

  const requiredMargin =
    side !== 'close' && size && parseFloat(size) > 0 && price
      ? calculateRequiredMargin(parseFloat(size), parseFloat(price), leverage)
      : 0;

  const canAfford = balance
    ? requiredMargin <= balance.availableBalance
    : true;

  const showLeverageWarning = leverage > 5;

  return {
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
  };
}
