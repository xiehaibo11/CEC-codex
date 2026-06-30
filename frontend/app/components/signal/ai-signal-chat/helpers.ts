export const getMetricLabel = (metric: string) => {
  const labels: Record<string, string> = {
    oi: 'Open Interest',
    oi_delta_percent: 'OI Delta %',
    cvd: 'CVD',
    funding_rate: 'Funding Rate',
    depth_ratio: 'Depth Ratio',
    order_imbalance: 'Order Imbalance',
    taker_buy_ratio: 'Taker Buy Ratio',
    taker_volume: 'Taker Volume',
  }
  return labels[metric] || metric
}

export const getOperatorLabel = (op: string) => {
  const labels: Record<string, string> = {
    greater_than: '>',
    less_than: '<',
    greater_than_or_equal: '>=',
    less_than_or_equal: '<=',
    abs_greater_than: 'abs >',
  }
  return labels[op] || op
}
