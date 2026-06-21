export type ManualTradingExchangeId = 'hyperliquid' | 'binance'

export interface ManualTradingWalletLike {
  wallet_address?: string
  api_key_masked?: string
}

export interface ManualTradingExchangeConfig {
  id: ManualTradingExchangeId
  label: string
  shortLabel: string
  walletsEndpoint: string
  watchlistEndpoint: string
  defaultSymbols: string[]
  supportsApiUsage: boolean
  formatWalletIdentifier: (wallet: ManualTradingWalletLike) => string
}

const maskAddress = (address?: string) => {
  if (!address) return ''
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

const BINANCE_MANUAL_TRADING_CONFIG: ManualTradingExchangeConfig = {
  id: 'binance',
  label: 'Binance Futures',
  shortLabel: 'Binance',
  walletsEndpoint: '/api/binance/wallets/all',
  watchlistEndpoint: '/api/binance/symbols/watchlist',
  defaultSymbols: ['BTC', 'ETH', 'BNB', 'SOL', 'XRP'],
  supportsApiUsage: false,
  formatWalletIdentifier: (wallet) => wallet.api_key_masked || '****',
}

export const MANUAL_TRADING_EXCHANGES: ManualTradingExchangeConfig[] = [
  BINANCE_MANUAL_TRADING_CONFIG,
]

export const DEFAULT_MANUAL_TRADING_EXCHANGE: ManualTradingExchangeId =
  BINANCE_MANUAL_TRADING_CONFIG.id

export function getManualTradingExchangeConfig(exchange: ManualTradingExchangeId) {
  return (
    MANUAL_TRADING_EXCHANGES.find((item) => item.id === exchange) ||
    BINANCE_MANUAL_TRADING_CONFIG
  )
}

export function getManualTradingExchangeLabel(exchange: ManualTradingExchangeId) {
  return getManualTradingExchangeConfig(exchange).label
}

// Kept here so enabling Hyperliquid again is a config change instead of
// spreading endpoints and labels back through the trading page.
export const HYPERLIQUID_MANUAL_TRADING_CONFIG: ManualTradingExchangeConfig = {
  id: 'hyperliquid',
  label: 'Hyperliquid',
  shortLabel: 'Hyperliquid',
  walletsEndpoint: '/api/hyperliquid/wallets/all',
  watchlistEndpoint: '/api/hyperliquid/symbols/watchlist',
  defaultSymbols: ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ARB', 'OP'],
  supportsApiUsage: true,
  formatWalletIdentifier: (wallet) => maskAddress(wallet.wallet_address),
}
