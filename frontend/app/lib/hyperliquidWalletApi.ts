import { apiRequest } from './apiClient';
import type {
  HyperliquidEnvironment,
  AgentWalletUpgradeRequest,
  AgentWalletConfigRequest,
  AgentWalletUpgradeResponse,
  AgentWalletConfigResponse,
  AgentWalletStatus,
  WalletUpgradeCheckResponse,
} from './types/hyperliquid';

const HYPERLIQUID_API_BASE = '/hyperliquid';

export async function getWalletRateLimit(
  accountId: number,
  environment?: HyperliquidEnvironment
): Promise<{
  success: boolean;
  accountId: number;
  rateLimit: {
    cumVlm: number;
    nRequestsUsed: number;
    nRequestsCap: number;
    nRequestsSurplus: number;
    remaining: number;
    usagePercent: number;
    isOverLimit: boolean;
    environment: string;
    walletAddress: string;
  };
}> {
  const url = environment
    ? `${HYPERLIQUID_API_BASE}/accounts/${accountId}/rate-limit?environment=${environment}`
    : `${HYPERLIQUID_API_BASE}/accounts/${accountId}/rate-limit`;

  const response = await apiRequest(url);
  return response.json();
}

export interface WalletConfig {
  id: number;
  walletAddress: string;
  maxLeverage: number;
  defaultLeverage: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface WalletConfigRequest {
  privateKey: string;
  maxLeverage: number;
  defaultLeverage: number;
}

export interface WalletInfo {
  success: boolean;
  configured: boolean;
  accountId: number;
  accountName: string;
  wallet?: WalletConfig;
  globalTradingMode?: string;
  balance?: {
    totalEquity: number;
    availableBalance: number;
    marginUsagePercent: number;
  };
}

export async function getAccountWallet(accountId: number): Promise<WalletInfo> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet`
  );
  return response.json();
}

export async function configureAccountWallet(
  accountId: number,
  config: WalletConfigRequest
): Promise<{ success: boolean; walletId: number; walletAddress: string; message: string; requires_authorization?: boolean }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet`,
    {
      method: 'POST',
      body: JSON.stringify(config),
    }
  );
  return response.json();
}

export async function deleteAccountWallet(
  accountId: number,
  environment: 'testnet' | 'mainnet'
): Promise<{ success: boolean; message: string; environment: string }> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet?environment=${environment}`,
    {
      method: 'DELETE',
    }
  );
  return response.json();
}

export async function testWalletConnection(
  accountId: number,
  environment?: 'testnet' | 'mainnet'
): Promise<{
  success: boolean;
  accountId: number;
  accountName: string;
  environment: string;
  walletAddress?: string;
  connection: string;
  accountState?: {
    totalEquity: number;
    availableBalance: number;
    marginUsage: number;
  };
  error?: string;
}> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet/test`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ environment: environment || null }),
    }
  );
  return response.json();
}

export interface TradingModeInfo {
  success: boolean;
  mode: 'testnet' | 'mainnet';
  description: string;
}

export async function getGlobalTradingMode(): Promise<TradingModeInfo> {
  const response = await apiRequest(`${HYPERLIQUID_API_BASE}/trading-mode`);
  return response.json();
}

export async function setGlobalTradingMode(
  mode: 'testnet' | 'mainnet'
): Promise<{
  success: boolean;
  mode: string;
  changed: boolean;
  oldMode?: string;
  message: string;
}> {
  const response = await apiRequest(`${HYPERLIQUID_API_BASE}/trading-mode`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
  return response.json();
}

export async function upgradeToAgentWallet(
  accountId: number,
  environment: HyperliquidEnvironment,
  agentName?: string
): Promise<AgentWalletUpgradeResponse> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet/upgrade-to-agent`,
    {
      method: 'POST',
      body: JSON.stringify({ environment, agentName: agentName || `HyperArena-${accountId}` }),
    }
  );
  return response.json();
}

export async function configureAgentWallet(
  accountId: number,
  config: AgentWalletConfigRequest
): Promise<AgentWalletConfigResponse> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet/agent`,
    {
      method: 'POST',
      body: JSON.stringify(config),
    }
  );
  return response.json();
}

export async function getAgentWalletStatus(
  accountId: number,
  environment: HyperliquidEnvironment
): Promise<AgentWalletStatus> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/accounts/${accountId}/wallet/agent-status?environment=${environment}`
  );
  return response.json();
}

export async function checkWalletUpgradeNeeded(): Promise<WalletUpgradeCheckResponse> {
  const response = await apiRequest(
    `${HYPERLIQUID_API_BASE}/wallet-upgrade-check`
  );
  return response.json();
}
