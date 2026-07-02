export type WalletEnvironment = 'testnet' | 'mainnet'

export interface WalletData {
  id?: number
  walletAddress?: string
  maxLeverage: number
  defaultLeverage: number
  balance?: {
    totalEquity: number
    availableBalance: number
    marginUsagePercent: number
  }
}

export type InputType = 'empty' | 'valid_key' | 'key_no_prefix' | 'wallet_address' | 'invalid'
