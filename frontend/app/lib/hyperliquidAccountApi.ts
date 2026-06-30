import { apiRequest } from './apiClient';
import type {
  HyperliquidConfig,
  HyperliquidBalance,
  HyperliquidAccountState,
  HyperliquidPositionsResponse,
  HyperliquidActionSummary,
  SetupRequest,
  SwitchEnvironmentRequest,
  ManualOrderRequest,
  ManualOrderResponse,
  TestConnectionResponse,
  HyperliquidHealthResponse,
} from './types/hyperliquid';

const HYPERLIQUID_API_BASE = '/hyperliquid';

export async function setupHyperliquidAccount(
  accountId: number,
  config: SetupRequest
): Promise<{ success: boolean; message: string }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/setup`,
    {
      method: 'POST',
      body: JSON.stringify(config),
    }
  );
  return response.json();
}

export async function getHyperliquidConfig(
  accountId: number
): Promise<HyperliquidConfig> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/config`
  );
  return response.json();
}

export async function switchEnvironment(
  accountId: number,
  request: SwitchEnvironmentRequest
): Promise<{ success: boolean; message: string }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/switch-environment`,
    {
      method: 'POST',
      body: JSON.stringify(request),
    }
  );
  return response.json();
}

export async function getHyperliquidBalance(
  accountId: number,
  environment?: 'testnet' | 'mainnet'
): Promise<HyperliquidBalance> {
  const params = new URLSearchParams();
  if (environment) {
    params.append('environment', environment);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/balance${query}`
  );
  const data = await response.json();
  const lastUpdated =
    data.cached_at ??
    (data.timestamp ? new Date(data.timestamp).toISOString() : undefined);
  return {
    totalEquity: data.total_equity ?? 0,
    availableBalance: data.available_balance ?? 0,
    usedMargin: data.used_margin ?? 0,
    maintenanceMargin: data.maintenance_margin ?? 0,
    marginUsagePercent: data.margin_usage_percent ?? 0,
    withdrawalAvailable: data.withdrawal_available ?? 0,
    lastUpdated,
    walletAddress: data.wallet_address ?? undefined,
  };
}

export async function getHyperliquidAccountState(
  accountId: number
): Promise<HyperliquidAccountState> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/account-state`
  );
  return response.json();
}

export async function getHyperliquidPositions(
  accountId: number,
  environment?: 'testnet' | 'mainnet',
  force_refresh?: boolean
): Promise<HyperliquidPositionsResponse> {
  const params = new URLSearchParams();
  if (environment) {
    params.append('environment', environment);
  }
  if (force_refresh) {
    params.append('force_refresh', 'true');
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/positions${query}`
  );
  const data = await response.json();
  const positions = Array.isArray(data.positions) ? data.positions : [];

  return {
    positions: positions.map((pos: any) => ({
      coin: pos.coin ?? pos.symbol ?? '',
      szi: Number(pos.szi ?? pos.contracts ?? 0),
      entryPx: Number(pos.entry_px ?? pos.entryPx ?? 0),
      positionValue: Number(pos.position_value ?? pos.positionValue ?? 0),
      unrealizedPnl: Number(pos.unrealized_pnl ?? pos.unrealizedPnl ?? 0),
      marginUsed: Number(pos.margin_used ?? pos.marginUsed ?? 0),
      liquidationPx: Number(pos.liquidation_px ?? pos.liquidationPx ?? 0),
      leverage: Number(pos.leverage ?? 1),
    })),
    count: data.count ?? positions.length,
    environment: data.environment,
    source: data.source ?? 'live',
    cachedAt: data.cached_at,
  };
}

export async function getCurrentPrice(symbol: string): Promise<number> {
  const response = await apiRequest(`/market/price/${symbol}?market=CRYPTO`);
  const data = await response.json();
  return Number(data.price ?? 0);
}

export async function placeManualOrder(
  accountId: number,
  order: ManualOrderRequest
): Promise<ManualOrderResponse> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/orders/manual`,
    {
      method: 'POST',
      body: JSON.stringify(order),
    }
  );
  return response.json();
}

export async function testConnection(
  accountId: number
): Promise<TestConnectionResponse> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/test-connection`
  );
  return response.json();
}

export async function getHyperliquidHealth(): Promise<HyperliquidHealthResponse> {
  const response = await apiRequest(`${HYPERLIQUID_API_BASE}/health`);
  return response.json();
}

export async function getHyperliquidActionSummary(params?: {
  accountId?: number;
  windowMinutes?: number;
}): Promise<HyperliquidActionSummary> {
  const search = new URLSearchParams();
  if (params?.accountId) {
    search.append('account_id', params.accountId.toString());
  }
  if (params?.windowMinutes) {
    search.append('window_minutes', params.windowMinutes.toString());
  }
  const query = search.toString() ? `?${search.toString()}` : '';
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/actions/summary${query}`
  );
  const data = await response.json();
  return {
    windowMinutes: data.window_minutes ?? params?.windowMinutes ?? 1440,
    accountId: data.account_id ?? params?.accountId,
    totalActions: data.total_actions ?? 0,
    generatedAt: data.generated_at,
    latestActionAt: data.latest_action_at,
    byAction: Array.isArray(data.by_action)
      ? data.by_action.map((entry: any) => ({
          actionType: entry.action_type,
          count: entry.count ?? 0,
          errors: entry.errors ?? 0,
          lastOccurrence: entry.last_occurrence,
        }))
      : [],
  };
}

export async function enableHyperliquid(
  accountId: number
): Promise<{ success: boolean; message: string }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/enable`,
    {
      method: 'POST',
    }
  );
  return response.json();
}

export async function disableHyperliquid(
  accountId: number
): Promise<{ success: boolean; message: string }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/disable`,
    {
      method: 'POST',
    }
  );
  return response.json();
}
