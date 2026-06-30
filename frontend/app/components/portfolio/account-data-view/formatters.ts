export function formatCurrency(value?: number | null, fractionDigits = 2) {
  if (value === undefined || value === null || Number.isNaN(value)) return '$0.00'
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: Math.max(2, fractionDigits),
  })}`
}
