import { CATEGORY_LABELS, DATASET_LABELS, PLAN_LABELS, PLAN_ORDER } from './constants'
import type { CoinGlassDataset, CoinGlassEndpoint } from './types'

export function planRank(plan?: string | null) {
  if (!plan) return -1
  const normalized = PLAN_ORDER.find((item) => item.toLowerCase() === plan.toLowerCase())
  return normalized ? PLAN_ORDER.indexOf(normalized) : -1
}

export function displayPlan(plan?: string | null) {
  if (!plan) return '-'
  const normalized = PLAN_ORDER.find((item) => item.toLowerCase() === plan.toLowerCase())
  return normalized ? PLAN_LABELS[normalized] : plan
}

export function keySourceLabel(source?: 'user' | 'server' | 'none') {
  if (source === 'user') return '个人'
  if (source === 'server') return '服务器'
  return '无'
}

export function categoryTitle(category?: string | null) {
  if (!category) return '-'
  return CATEGORY_LABELS[category] || category
}

export function datasetTitle(dataset?: CoinGlassDataset | null) {
  if (!dataset) return '-'
  return DATASET_LABELS[dataset.id] || dataset.label || '-'
}

export function endpointTitle(endpoint?: CoinGlassEndpoint | null) {
  if (!endpoint) return '-'
  const fileName = endpoint.doc_path?.split('/').pop()?.replace(/\.md$/, '')
  return fileName || endpoint.title || endpoint.path
}

export function statusTitle(loading: boolean, result: any) {
  if (loading) return '加载中'
  if (result?.ok) return '成功'
  if (result) return '已返回'
  return '-'
}

export function displayError(message: string) {
  const normalized = message.toLowerCase()
  if (normalized.includes('api key') && normalized.includes('required')) return '请输入 CoinGlass API 密钥'
  if (normalized.includes('api key') && normalized.includes('not configured')) return '未配置 CoinGlass API 密钥'
  if (normalized.includes('failed to save')) return '保存 CoinGlass API 密钥失败'
  if (normalized.includes('failed to remove')) return '删除 CoinGlass API 密钥失败'
  if (normalized.includes('failed to load')) return '加载 CoinGlass 数据失败'
  if (normalized.includes('does not allow')) return '当前 CoinGlass 权限等级不支持该接口或参数'
  if (normalized.includes('forbidden') || normalized.includes('permission')) return '当前 CoinGlass 权限不足'
  if (normalized.includes('unauthorized') || normalized.includes('invalid')) return 'CoinGlass API 密钥无效或未授权'
  return message
}

export function formatNumber(value: unknown) {
  const number = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(number)) return String(value ?? '-')
  const abs = Math.abs(number)
  if (abs >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`
  if (abs >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${(number / 1_000).toFixed(2)}K`
  if (abs > 0 && abs < 0.01) return number.toPrecision(3)
  return number.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

export function formatTime(value: unknown) {
  const raw = Number(value)
  if (!Number.isFinite(raw)) return String(value ?? '-')
  const timestamp = raw < 10_000_000_000 ? raw * 1000 : raw
  return new Date(timestamp).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
