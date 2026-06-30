export const SUPPORTED_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE'] as const

export type SupportedSymbol = typeof SUPPORTED_SYMBOLS[number]
