import type { TFunction } from 'i18next'
import type { NewsSourceConfig, NewsStatsResponse } from '@/lib/api'
import type { NewsSourceAdapter } from './types'

export function extractDomain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function formatDateTime(
  value: string | null | undefined,
  currentLang: 'en' | 'zh',
  t: TFunction
) {
  if (!value) return t('settings.notAvailable', 'N/A')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return t('settings.notAvailable', 'N/A')
  return date.toLocaleString(currentLang === 'zh' ? 'zh-CN' : 'en-US')
}

export function getNewsCountsByDomain(newsStats: NewsStatsResponse | null) {
  return Object.entries(newsStats?.last_24h?.by_domain || {}).reduce<Record<string, number>>((acc, [domain, count]) => {
    const normalizedDomain = domain.replace(/^www\./, '')
    acc[normalizedDomain] = (acc[normalizedDomain] || 0) + count
    return acc
  }, {})
}

export function buildNewsSourceConfig({
  adapter,
  url,
  intervalValue,
  authToken,
  apiKey,
}: {
  adapter: NewsSourceAdapter
  url: string
  intervalValue: string
  authToken: string
  apiKey: string
}) {
  const interval = parseInt(intervalValue, 10)
  const intervalSeconds = Number.isFinite(interval) && interval > 0 ? interval : 300

  const config: Record<string, any> = {}
  if (adapter === 'cryptopanic' && authToken.trim()) {
    config.auth_token = authToken.trim()
  }
  if (adapter === 'finnhub_calendar' && apiKey.trim()) {
    config.api_key = apiKey.trim()
  }

  return {
    type: adapter === 'rss_generic' ? 'rss' : 'api',
    adapter,
    url,
    enabled: true,
    interval_seconds: intervalSeconds,
    config,
  } satisfies NewsSourceConfig
}
