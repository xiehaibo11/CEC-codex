import { apiRequest } from './apiClient';
import type {
  HyperliquidBalance,
  HyperliquidPositionsResponse,
} from './types/hyperliquid';

const HIBT_API_BASE = '/hibt';

export interface HibtSummary {
  account_id: number;
  environment: string;
  exchange: string;
  equity: number;
  available_balance: number;
  used_margin: number;
  margin_usage: number;
  unrealized_pnl: number;
  rate_limit: null;
  last_updated: number | string | null;
}

export async function getHibtSummary(accountId: number): Promise<HibtSummary> {
  const response = await apiRequest(`${HIBT_API_BASE}/accounts/${accountId}/summary`);
  return response.json();
}

export async function getHibtBalance(
  accountId: number,
  environment?: 'testnet' | 'mainnet'
): Promise<HyperliquidBalance> {
  const params = new URLSearchParams();
  if (environment) {
    params.append('environment', environment);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await apiRequest(`${HIBT_API_BASE}/accounts/${accountId}/balance${query}`);
  const data = await response.json();
  return {
    totalEquity: data.total_equity ?? 0,
    availableBalance: data.available_balance ?? 0,
    usedMargin: data.used_margin ?? 0,
    maintenanceMargin: data.maintenance_margin ?? 0,
    marginUsagePercent: data.margin_usage_percent ?? 0,
    withdrawalAvailable: 0,
    lastUpdated: data.timestamp ? new Date(data.timestamp).toISOString() : undefined,
  };
}

export async function getHibtPositions(
  accountId: number,
  environment?: 'testnet' | 'mainnet'
): Promise<HyperliquidPositionsResponse> {
  const params = new URLSearchParams();
  if (environment) {
    params.append('environment', environment);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await apiRequest(`${HIBT_API_BASE}/accounts/${accountId}/positions${query}`);
  const data = await response.json();
  const positions = Array.isArray(data.positions) ? data.positions : [];

  return {
    positions: positions.map((pos: any) => ({
      coin: pos.coin ?? pos.symbol ?? '',
      szi: Number(pos.szi ?? 0),
      entryPx: Number(pos.entry_px ?? pos.entryPx ?? 0),
      positionValue: Number(pos.position_value ?? pos.positionValue ?? 0),
      unrealizedPnl: Number(pos.unrealized_pnl ?? pos.unrealizedPnl ?? 0),
      marginUsed: Number(pos.margin_used ?? pos.marginUsed ?? 0),
      liquidationPx: Number(pos.liquidation_px ?? pos.liquidationPx ?? 0),
      leverage: Number(pos.leverage ?? 1),
    })),
    count: positions.length,
    environment: data.environment,
    source: 'live',
  };
}

export async function getHibtPrice(symbol: string): Promise<number> {
  const response = await apiRequest(`${HIBT_API_BASE}/price/${symbol}`);
  const data = await response.json();
  return Number(data.price ?? 0);
}

export interface HibtOrderRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  orderType: 'MARKET' | 'LIMIT';
  price?: number;
  leverage: number;
  reduceOnly: boolean;
  takeProfitPrice?: number;
  stopLossPrice?: number;
}

export async function placeHibtOrder(
  accountId: number,
  order: HibtOrderRequest,
  environment?: 'testnet' | 'mainnet'
): Promise<any> {
  const params = new URLSearchParams();
  if (environment) {
    params.append('environment', environment);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await apiRequest(`${HIBT_API_BASE}/accounts/${accountId}/order${query}`, {
    method: 'POST',
    body: JSON.stringify({
      symbol: order.symbol,
      side: order.side,
      quantity: order.quantity,
      order_type: order.orderType,
      price: order.price,
      leverage: order.leverage,
      reduce_only: order.reduceOnly,
      take_profit_price: order.takeProfitPrice,
      stop_loss_price: order.stopLossPrice,
    }),
  });
  return response.json();
}

export async function closeHibtPosition(
  accountId: number,
  symbol: string,
  environment?: 'testnet' | 'mainnet'
): Promise<any> {
  const params = new URLSearchParams();
  params.append('symbol', symbol);
  if (environment) {
    params.append('environment', environment);
  }
  const response = await apiRequest(
    `${HIBT_API_BASE}/accounts/${accountId}/close-position?${params.toString()}`,
    { method: 'POST' }
  );
  return response.json();
}
