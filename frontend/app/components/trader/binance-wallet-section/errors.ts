export const getErrorMessage = (data: any, fallback: string) => {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || JSON.stringify(detail)
  }
  return data?.message || fallback
}
