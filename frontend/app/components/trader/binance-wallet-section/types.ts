export type BinanceWalletEnvironment = 'testnet' | 'mainnet'

export interface BinanceWalletData {
  configured: boolean
  apiKeyMasked?: string
  maxLeverage: number
  defaultLeverage: number
  balance?: {
    total_equity: number
    available_balance: number
    unrealized_pnl: number
  }
}

export interface MainnetQuota {
  limited: boolean
  used: number
  limit: number
  remaining: number
}
