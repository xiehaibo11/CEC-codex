export function calculateMarginUsageColor(percent: number): string {
  if (percent < 50) return 'text-green-500';
  if (percent < 75) return 'text-yellow-500';
  return 'text-red-500';
}

export function formatPnl(pnl: number): {
  value: string;
  color: string;
  icon: string;
} {
  const isPositive = pnl >= 0;
  return {
    value: `${isPositive ? '+' : ''}${pnl.toFixed(2)}`,
    color: isPositive ? 'text-green-600' : 'text-red-600',
    icon: isPositive ? '↑' : '↓',
  };
}

export function getPositionSide(szi: number): 'LONG' | 'SHORT' {
  return szi > 0 ? 'LONG' : 'SHORT';
}

export function formatLeverage(leverage: number): string {
  return `${leverage}x`;
}

export function validatePrivateKey(key: string): boolean {
  return /^0x[0-9a-fA-F]{64}$/.test(key);
}

export function estimateLiquidationPrice(
  entryPrice: number,
  leverage: number,
  isLong: boolean
): number {
  const liquidationPercent = 1 / leverage;
  return isLong
    ? entryPrice * (1 - liquidationPercent)
    : entryPrice * (1 + liquidationPercent);
}

export function calculateRequiredMargin(
  size: number,
  price: number,
  leverage: number
): number {
  return (size * price) / leverage;
}

export function getRiskLevel(marginPercent: number): 'low' | 'medium' | 'high' {
  if (marginPercent < 50) return 'low';
  if (marginPercent < 75) return 'medium';
  return 'high';
}
