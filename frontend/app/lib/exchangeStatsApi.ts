import { apiRequest } from './apiClient';
import type { HyperliquidEnvironment } from './types/hyperliquid';

const HYPERLIQUID_API_BASE = '/hyperliquid';
const BINANCE_API_BASE = '/binance';

export interface TradingStats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  volume: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  gross_profit: number;
  gross_loss: number;
  error?: string;
}

export async function getTradingStats(
  accountId: number,
  environment?: HyperliquidEnvironment
): Promise<{
  success: boolean;
  accountId: number;
  environment: string;
  stats: TradingStats;
}> {
  const url = environment
    ? `${HYPERLIQUID_API_BASE}/accounts/${accountId}/trading-stats?environment=${environment}`
    : `${HYPERLIQUID_API_BASE}/accounts/${accountId}/trading-stats`;

  const response = await apiRequest(url);
  return response.json();
}

export async function getBinanceTradingStats(
  accountId: number,
  environment?: 'testnet' | 'mainnet'
): Promise<{
  success: boolean;
  accountId: number;
  environment: string;
  stats: TradingStats;
}> {
  const url = environment
    ? `${BINANCE_API_BASE}/accounts/${accountId}/trading-stats?environment=${environment}`
    : `${BINANCE_API_BASE}/accounts/${accountId}/trading-stats`;

  const response = await apiRequest(url);
  return response.json();
}
