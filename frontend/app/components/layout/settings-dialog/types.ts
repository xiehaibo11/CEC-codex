import type { TradingAccount, TradingAccountCreate } from '@/lib/api'

export interface AIAccount extends TradingAccount {
  model?: string
  base_url?: string
  api_key?: string
}

export interface AIAccountCreate extends TradingAccountCreate {
  model?: string
  base_url?: string
  api_key?: string
}
