import type { ExchangeType } from '../WalletSelector';

export interface OrderFormProps {
  accountId: number;
  environment: 'testnet' | 'mainnet';
  exchange: ExchangeType;
  availableSymbols: string[];
  symbolsLoading?: boolean;
  maxLeverage: number;
  defaultLeverage: number;
  onOrderPlaced?: () => void;
}

export type OrderSide = 'long' | 'short' | 'close';
export type TimeInForce = 'Ioc' | 'Gtc' | 'Alo';
