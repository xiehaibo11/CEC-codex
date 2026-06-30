export function formatPrice(price: number | null | undefined): string {
  if (price === null || price === undefined) return '-'
  if (price >= 10000) return price.toFixed(0)
  if (price >= 100) return price.toFixed(1)
  return price.toFixed(2)
}
