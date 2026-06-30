import { useCallback, useEffect, useMemo, useState } from 'react'
import type { TFunction } from 'i18next'
import {
  getNewsSources,
  getNewsStats,
  testNewsSource,
  updateNewsSources,
} from '@/lib/api'
import type {
  NewsSourceConfig,
  NewsStatsResponse,
  TestNewsSourceResponse,
} from '@/lib/api'
import {
  buildNewsSourceConfig,
  extractDomain,
  formatDateTime,
  getNewsCountsByDomain,
} from './helpers'
import type { NewsSourceAdapter, NewsSourcesSettingsTabProps } from './types'

interface UseNewsSourcesSettingsOptions {
  activeTab: string
  currentLang: 'en' | 'zh'
  t: TFunction
}

export function useNewsSourcesSettings({
  activeTab,
  currentLang,
  t,
}: UseNewsSourcesSettingsOptions): NewsSourcesSettingsTabProps {
  const [newsSources, setNewsSources] = useState<NewsSourceConfig[]>([])
  const [newsSourcesSnapshot, setNewsSourcesSnapshot] = useState('[]')
  const [newsStats, setNewsStats] = useState<NewsStatsResponse | null>(null)
  const [newsLoading, setNewsLoading] = useState(false)
  const [newsSaving, setNewsSaving] = useState(false)
  const [newsError, setNewsError] = useState<string | null>(null)
  const [newsSuccess, setNewsSuccess] = useState<string | null>(null)
  const [newsFormAdapter, setNewsFormAdapter] = useState<NewsSourceAdapter>('rss_generic')
  const [newsTestUrl, setNewsTestUrl] = useState('')
  const [newsFormInterval, setNewsFormInterval] = useState('300')
  const [newsFormAuthToken, setNewsFormAuthToken] = useState('')
  const [newsFormApiKey, setNewsFormApiKey] = useState('')
  const [newsTesting, setNewsTesting] = useState(false)
  const [newsTestError, setNewsTestError] = useState<string | null>(null)
  const [newsTestResult, setNewsTestResult] = useState<TestNewsSourceResponse | null>(null)

  const fetchNewsSourcesData = useCallback(async () => {
    setNewsLoading(true)
    setNewsError(null)
    try {
      const [sourcesRes, statsRes] = await Promise.all([
        getNewsSources(),
        getNewsStats(),
      ])
      const nextSources = sourcesRes.sources || []
      setNewsSources(nextSources)
      setNewsSourcesSnapshot(JSON.stringify(nextSources))
      setNewsStats(statsRes)
    } catch (err) {
      setNewsError(err instanceof Error ? err.message : 'Failed to load news sources')
    } finally {
      setNewsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'news-sources' && !newsLoading && !newsStats && newsSources.length === 0) {
      fetchNewsSourcesData()
    }
  }, [activeTab, newsLoading, newsStats, newsSources.length, fetchNewsSourcesData])

  const enabledNewsSourceCount = useMemo(
    () => newsSources.filter((source) => source.enabled).length,
    [newsSources]
  )

  const hasUnsavedNewsSources = useMemo(
    () => JSON.stringify(newsSources) !== newsSourcesSnapshot,
    [newsSources, newsSourcesSnapshot]
  )

  const newsCountsByDomain = useMemo(() => getNewsCountsByDomain(newsStats), [newsStats])

  const getCurrentNewsSourceConfig = (url: string) => buildNewsSourceConfig({
    adapter: newsFormAdapter,
    url,
    intervalValue: newsFormInterval,
    authToken: newsFormAuthToken,
    apiKey: newsFormApiKey,
  })

  const resetNewsTestState = () => {
    setNewsTestResult(null)
    setNewsTestError(null)
  }

  const handleToggleNewsSource = (index: number, enabled: boolean) => {
    setNewsError(null)
    setNewsSuccess(null)
    setNewsSources((prev) => prev.map((source, sourceIndex) => (
      sourceIndex === index ? { ...source, enabled } : source
    )))
  }

  const handleSaveNewsSources = async () => {
    setNewsSaving(true)
    setNewsError(null)
    setNewsSuccess(null)
    try {
      const result = await updateNewsSources(newsSources)
      setNewsSources(result.sources || [])
      setNewsSourcesSnapshot(JSON.stringify(result.sources || []))
      setNewsSuccess(t('settings.newsSourcesSaved', 'News sources saved'))
      const stats = await getNewsStats()
      setNewsStats(stats)
    } catch (err) {
      setNewsError(err instanceof Error ? err.message : 'Failed to save news sources')
    } finally {
      setNewsSaving(false)
    }
  }

  const handleTestNewsSource = async () => {
    const trimmedUrl = newsTestUrl.trim()
    if (!trimmedUrl) {
      setNewsTestError(t('settings.newsSourceUrlRequired', 'Please enter a source URL'))
      setNewsTestResult(null)
      return
    }

    try {
      new URL(trimmedUrl)
    } catch {
      setNewsTestError(t('settings.newsSourceUrlInvalid', 'Please enter a valid URL'))
      setNewsTestResult(null)
      return
    }

    const interval = parseInt(newsFormInterval, 10)
    if (!Number.isFinite(interval) || interval < 10) {
      setNewsTestError(t('settings.newsSourceIntervalInvalid', 'Interval must be at least 10 seconds'))
      setNewsTestResult(null)
      return
    }

    if (newsFormAdapter === 'cryptopanic' && !newsFormAuthToken.trim()) {
      setNewsTestError(t('settings.newsSourceAuthTokenRequired', 'Please enter a CryptoPanic auth token'))
      setNewsTestResult(null)
      return
    }

    if (newsFormAdapter === 'finnhub_calendar' && !newsFormApiKey.trim()) {
      setNewsTestError(t('settings.newsSourceApiKeyRequired', 'Please enter a Finnhub API key'))
      setNewsTestResult(null)
      return
    }

    setNewsTesting(true)
    setNewsTestError(null)
    setNewsTestResult(null)
    setNewsSuccess(null)

    try {
      const sourceConfig = getCurrentNewsSourceConfig(trimmedUrl)
      const result = await testNewsSource({
        url: trimmedUrl,
        adapter: newsFormAdapter,
        config: sourceConfig.config || {},
      })
      setNewsTestResult(result)
      if (!result.success) {
        setNewsTestError(result.error || t('settings.newsSourceTestFailed', 'Test failed'))
      }
    } catch (err) {
      setNewsTestError(err instanceof Error ? err.message : 'Failed to test source')
    } finally {
      setNewsTesting(false)
    }
  }

  const handleAddNewsSource = () => {
    const trimmedUrl = newsTestUrl.trim()
    if (!newsTestResult?.success || !trimmedUrl) {
      return
    }

    if (newsSources.some((source) => source.url === trimmedUrl)) {
      setNewsTestError(t('settings.newsSourceDuplicate', 'This source already exists'))
      return
    }

    const nextSources = [...newsSources, getCurrentNewsSourceConfig(trimmedUrl)]

    setNewsSources(nextSources)
    setNewsFormAdapter('rss_generic')
    setNewsTestUrl('')
    setNewsFormInterval('300')
    setNewsFormAuthToken('')
    setNewsFormApiKey('')
    setNewsTestError(null)
    setNewsTestResult(null)
    setNewsSuccess(t('settings.newsSourceAdded', 'Source added to the list. Save to apply.'))
  }

  const handleNewsSourceIntervalChange = (index: number, value: string) => {
    setNewsError(null)
    setNewsSuccess(null)
    setNewsSources((prev) => prev.map((source, sourceIndex) => {
      if (sourceIndex !== index) return source
      const parsed = parseInt(value, 10)
      return {
        ...source,
        interval_seconds: Number.isFinite(parsed) && parsed > 0 ? parsed : source.interval_seconds,
      }
    }))
  }

  return {
    t,
    newsSources,
    newsStats,
    newsLoading,
    newsSaving,
    newsError,
    newsSuccess,
    enabledNewsSourceCount,
    hasUnsavedNewsSources,
    newsCountsByDomain,
    newsFormAdapter,
    newsTestUrl,
    newsFormInterval,
    newsFormAuthToken,
    newsFormApiKey,
    newsTesting,
    newsTestError,
    newsTestResult,
    formatDateTime: (value) => formatDateTime(value, currentLang, t),
    extractDomain,
    onToggleNewsSource: handleToggleNewsSource,
    onSaveNewsSources: handleSaveNewsSources,
    onRefreshNewsSources: fetchNewsSourcesData,
    onNewsSourceIntervalChange: handleNewsSourceIntervalChange,
    onNewsFormAdapterChange: (value) => {
      setNewsFormAdapter(value)
      resetNewsTestState()
    },
    onNewsFormIntervalChange: (value) => {
      setNewsFormInterval(value)
      resetNewsTestState()
    },
    onNewsFormAuthTokenChange: (value) => {
      setNewsFormAuthToken(value)
      resetNewsTestState()
    },
    onNewsFormApiKeyChange: (value) => {
      setNewsFormApiKey(value)
      resetNewsTestState()
    },
    onNewsTestUrlChange: (value) => {
      setNewsTestUrl(value)
      setNewsTestError(null)
      setNewsTestResult(null)
    },
    onTestNewsSource: handleTestNewsSource,
    onAddNewsSource: handleAddNewsSource,
  }
}
