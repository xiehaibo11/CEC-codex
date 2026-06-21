import {
  closeBinancePosition,
  getBinanceBalance,
  getBinancePositions,
  getBinancePrice,
  getCurrentPrice,
  getHyperliquidBalance,
  getHyperliquidPositions,
  placeBinanceOrder,
  placeManualOrder,
} from '@/lib/hyperliquidApi'
import type {
  HyperliquidBalance,
  HyperliquidPositionsResponse,
  ManualOrderRequest,
} from '@/lib/types/hyperliquid'
import type { ManualTradingExchangeId } from './manualTradingExchanges'

export type ManualTradingEnvironment = 'testnet' | 'mainnet'
export type ManualTradingTimeInForce = 'Ioc' | 'Gtc' | 'Alo'

export interface ManualTradingOrderInput {
  accountId: number
  environment: ManualTradingEnvironment
  symbol: string
  isBuy: boolean
  size: number
  price: number
  timeInForce: ManualTradingTimeInForce
  reduceOnly: boolean
  leverage: number
  takeProfitPrice?: number
  stopLossPrice?: number
}

export interface ManualTradingOrderResult {
  status?: string
  averagePrice?: number
  error?: string
  raw: unknown
}

export interface ManualTradingExchangeAdapter {
  getBalance: (accountId: number, environment: ManualTradingEnvironment) => Promise<HyperliquidBalance>
  getPositions: (accountId: number, environment: ManualTradingEnvironment, forceRefresh?: boolean) => Promise<HyperliquidPositionsResponse>
  getPrice: (symbol: string) => Promise<number>
  placeOrder: (order: ManualTradingOrderInput) => Promise<ManualTradingOrderResult>
  closePosition: (accountId: number, symbol: string, environment: ManualTradingEnvironment, side: string, size: number, fallbackPrice?: number) => Promise<ManualTradingOrderResult>
}

const normalizeOrderResult = (raw: any): ManualTradingOrderResult => {
  const order = raw?.order_result?.main_order || raw?.order_result || raw || {}
  return {
    status: order.status,
    averagePrice: order.averagePrice || order.average_price || order.avg_price || order.price,
    error: order.error || raw?.error,
    raw,
  }
}

const hyperliquidAdapter: ManualTradingExchangeAdapter = {
  getBalance: getHyperliquidBalance,
  getPositions: getHyperliquidPositions,
  getPrice: getCurrentPrice,
  placeOrder: async (order) => {
    const request: ManualOrderRequest = {
      symbol: order.symbol,
      is_buy: order.isBuy,
      size: order.size,
      price: order.price,
      time_in_force: order.timeInForce,
      reduce_only: order.reduceOnly,
      leverage: order.leverage,
      take_profit_price: order.takeProfitPrice,
      stop_loss_price: order.stopLossPrice,
      environment: order.environment,
    }
    return normalizeOrderResult(await placeManualOrder(order.accountId, request))
  },
  closePosition: async (accountId, symbol, environment, side, size, fallbackPrice) => {
    const marketPrice = await getCurrentPrice(symbol)
    const executionPrice = marketPrice || fallbackPrice || 0
    if (!executionPrice || executionPrice <= 0) {
      throw new Error('Unable to determine market price for closing the position')
    }
    return normalizeOrderResult(await placeManualOrder(accountId, {
      symbol,
      is_buy: side === 'SHORT',
      size,
      price: executionPrice,
      time_in_force: 'Ioc',
      leverage: 1,
      reduce_only: true,
      environment,
    }))
  },
}

const binanceAdapter: ManualTradingExchangeAdapter = {
  getBalance: getBinanceBalance,
  getPositions: getBinancePositions,
  getPrice: getBinancePrice,
  placeOrder: async (order) => normalizeOrderResult(await placeBinanceOrder(order.accountId, {
    symbol: order.symbol,
    side: order.isBuy ? 'BUY' : 'SELL',
    quantity: order.size,
    orderType: order.timeInForce === 'Ioc' ? 'MARKET' : 'LIMIT',
    price: order.timeInForce !== 'Ioc' ? order.price : undefined,
    leverage: order.leverage,
    reduceOnly: order.reduceOnly,
    takeProfitPrice: order.takeProfitPrice,
    stopLossPrice: order.stopLossPrice,
  }, order.environment)),
  closePosition: async (accountId, symbol, environment) => {
    const raw = await closeBinancePosition(accountId, symbol, environment)
    if (raw?.message?.includes('No position')) {
      return { status: 'error', error: 'No position to close', raw }
    }
    return normalizeOrderResult({ ...raw, status: 'filled' })
  },
}

export const MANUAL_TRADING_ADAPTERS: Record<ManualTradingExchangeId, ManualTradingExchangeAdapter> = {
  hyperliquid: hyperliquidAdapter,
  binance: binanceAdapter,
}

export function getManualTradingAdapter(exchange: ManualTradingExchangeId) {
  return MANUAL_TRADING_ADAPTERS[exchange]
}
