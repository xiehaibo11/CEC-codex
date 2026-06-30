import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  getBinanceAvailableSymbols,
  getBinanceWatchlist,
  updateBinanceWatchlist,
} from '@/lib/api'
import type { BinanceSymbolMeta } from '@/lib/api'
import ExchangeIcon from '@/components/exchange/ExchangeIcon'
import { BinanceDataSettingsTab } from './settings-page/BinanceDataSettingsTab'
import { NewsSourcesSettingsTab } from './settings-page/NewsSourcesSettingsTab'
import { WatchlistSettingsTab } from './settings-page/WatchlistSettingsTab'
import { useNewsSourcesSettings } from './settings-page/useNewsSourcesSettings'
import type { BackfillStatus, StorageStats } from './settings-page/types'

export default function SettingsPage() {
  const { t, i18n } = useTranslation()
  const [activeTab, setActiveTab] = useState('watchlist')

  // Language state
  const currentLang = i18n.language === 'zh' ? 'zh' : 'en'

  // Binance Watchlist state
  const [bnAvailableSymbols, setBnAvailableSymbols] = useState<BinanceSymbolMeta[]>([])
  const [bnWatchlistSymbols, setBnWatchlistSymbols] = useState<string[]>([])
  const [bnMaxSymbols, setBnMaxSymbols] = useState(10)
  const [bnLoading, setBnLoading] = useState(true)
  const [bnSaving, setBnSaving] = useState(false)
  const [bnError, setBnError] = useState<string | null>(null)
  const [bnSuccess, setBnSuccess] = useState<string | null>(null)
  const [bnSearchQuery, setBnSearchQuery] = useState('')

  // Storage stats state - per exchange
  const [storageStats, setStorageStats] = useState<Record<string, StorageStats>>({})
  const [storageLoading, setStorageLoading] = useState(false)
  const [retentionDays, setRetentionDays] = useState<Record<string, string>>({
    binance: '365',
  })
  const [retentionSaving, setRetentionSaving] = useState(false)
  const [retentionError, setRetentionError] = useState<string | null>(null)
  const [retentionSuccess, setRetentionSuccess] = useState<string | null>(null)

  // Backfill state - per exchange
  const [backfillStatus, setBackfillStatus] = useState<Record<string, BackfillStatus>>({})
  const [backfillStarting, setBackfillStarting] = useState<Record<string, boolean>>({})
  // Track if we just completed a backfill (for one-time success message)
  const [backfillJustCompleted, setBackfillJustCompleted] = useState<Record<string, boolean>>({})

  // Determine current exchange from active tab
  const currentExchange = activeTab === 'binance-data' ? 'binance' : null
  const newsSourcesSettings = useNewsSourcesSettings({ activeTab, currentLang, t })

  const toggleLanguage = (lang: 'en' | 'zh') => {
    i18n.changeLanguage(lang)
    // Sync language to backend for Bot integration
    fetch('/api/config/ui_language', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: lang }),
    }).catch(() => {})
  }

  const fetchWatchlist = useCallback(async () => {
    setBnLoading(true)
    setBnError(null)
    try {
      const [bnAvailable, bnWatchlist] = await Promise.all([
        getBinanceAvailableSymbols(),
        getBinanceWatchlist(),
      ])
      setBnAvailableSymbols(bnAvailable.symbols || [])
      setBnMaxSymbols(bnWatchlist.max_symbols ?? 10)
      setBnWatchlistSymbols(bnWatchlist.symbols || [])
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load watchlist'
      setBnError(errorMsg)
    } finally {
      setBnLoading(false)
    }
  }, [])

  const fetchStorageStats = useCallback(async (exchange: string) => {
    setStorageLoading(true)
    try {
      const res = await fetch(`/api/system/storage-stats?exchange=${exchange}`)
      if (res.ok) {
        const data: StorageStats = await res.json()
        setStorageStats((prev) => ({ ...prev, [exchange]: data }))
        setRetentionDays((prev) => ({ ...prev, [exchange]: data.retention_days.toString() }))
      }
    } catch (err) {
      console.error('Failed to fetch storage stats:', err)
    } finally {
      setStorageLoading(false)
    }
  }, [])

  // Load watchlist on mount
  useEffect(() => {
    fetchWatchlist()
  }, [fetchWatchlist])

  // Load storage stats when exchange data tab is active
  useEffect(() => {
    if (currentExchange && !storageStats[currentExchange]) {
      fetchStorageStats(currentExchange)
    }
  }, [currentExchange, storageStats, fetchStorageStats])

  // Fetch backfill status for an exchange
  const fetchBackfillStatus = useCallback(async (exchange: string) => {
    try {
      const res = await fetch(`/api/system/${exchange}/backfill/status`)
      if (res.ok) {
        const data = await res.json()
        setBackfillStatus(prev => {
          const prevStatus = prev[exchange]?.status
          // Track completion for one-time message
          if ((prevStatus === 'running' || prevStatus === 'pending') && data.status === 'completed') {
            setBackfillJustCompleted(p => ({ ...p, [exchange]: true }))
          }
          return { ...prev, [exchange]: data }
        })
      }
    } catch (err) {
      console.error(`Failed to fetch ${exchange} backfill status:`, err)
    }
  }, [])

  // Use ref to track if polling should continue
  const pollingRef = useRef<Record<string, boolean>>({})

  useEffect(() => {
    if (currentExchange) {
      // Initial fetch
      fetchBackfillStatus(currentExchange)
      pollingRef.current[currentExchange] = true

      // Poll while running - use functional update to get latest status
      const interval = setInterval(async () => {
        const res = await fetch(`/api/system/${currentExchange}/backfill/status`)
        if (res.ok) {
          const data = await res.json()
          setBackfillStatus(prev => {
            const prevStatus = prev[currentExchange]?.status
            // Track completion for one-time message
            if ((prevStatus === 'running' || prevStatus === 'pending') && data.status === 'completed') {
              setBackfillJustCompleted(p => ({ ...p, [currentExchange]: true }))
            }
            return { ...prev, [currentExchange]: data }
          })
          // Stop polling if completed or failed
          if (data.status !== 'running' && data.status !== 'pending') {
            pollingRef.current[currentExchange] = false
          }
        }
      }, 2000)

      return () => {
        clearInterval(interval)
        pollingRef.current[currentExchange] = false
      }
    }
  }, [activeTab, currentExchange, fetchBackfillStatus])

  const handleStartBackfill = async (exchange: string, force: boolean = false) => {
    setBackfillStarting(prev => ({ ...prev, [exchange]: true }))
    setBackfillJustCompleted(prev => ({ ...prev, [exchange]: false }))
    try {
      const url = force
        ? `/api/system/${exchange}/backfill?force=true`
        : `/api/system/${exchange}/backfill`
      const res = await fetch(url, { method: 'POST' })
      if (res.ok) {
        await fetchBackfillStatus(exchange)
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to start backfill')
      }
    } catch (err) {
      console.error('Failed to start backfill:', err)
    } finally {
      setBackfillStarting(prev => ({ ...prev, [exchange]: false }))
    }
  }

  const toggleBnWatchlistSymbol = (symbol: string) => {
    const symbolUpper = symbol.toUpperCase()
    setBnError(null)
    setBnSuccess(null)
    setBnWatchlistSymbols((prev) => {
      if (prev.includes(symbolUpper)) {
        return prev.filter((s) => s !== symbolUpper)
      }
      if (prev.length >= bnMaxSymbols) {
        setBnError(t('settings.maxSymbolsReached', `Maximum ${bnMaxSymbols} symbols`))
        return prev
      }
      return [...prev, symbolUpper]
    })
  }

  const handleSaveBnWatchlist = async () => {
    setBnSaving(true)
    setBnError(null)
    setBnSuccess(null)
    try {
      await updateBinanceWatchlist(bnWatchlistSymbols)
      setBnSuccess(t('settings.watchlistSaved', 'Watchlist saved'))
    } catch (err) {
      setBnError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setBnSaving(false)
    }
  }

  const handleSaveRetention = async () => {
    if (!currentExchange) return
    const days = parseInt(retentionDays[currentExchange], 10)
    if (isNaN(days) || days < 7 || days > 730) {
      setRetentionError(t('settings.retentionRange', 'Must be between 7 and 730 days'))
      return
    }
    setRetentionSaving(true)
    setRetentionError(null)
    setRetentionSuccess(null)
    try {
      const res = await fetch('/api/system/retention-days', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days, exchange: currentExchange }),
      })
      if (!res.ok) throw new Error('Failed to update')
      setRetentionSuccess(t('settings.retentionSaved', 'Retention updated'))
      const stats = storageStats[currentExchange]
      if (stats) {
        setStorageStats((prev) => ({
          ...prev,
          [currentExchange]: { ...stats, retention_days: days },
        }))
      }
    } catch (err) {
      setRetentionError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setRetentionSaving(false)
    }
  }

  return (
    <div className="p-6 h-[calc(100vh-64px)] flex flex-col overflow-hidden">
      {/* Language Settings - Compact row with border */}
      <div className="flex items-center gap-3 mb-6 shrink-0 p-4 border rounded-lg bg-card">
        <span className="text-sm font-medium">{t('settings.language', 'Language')}</span>
        <select
          value={currentLang}
          onChange={(e) => toggleLanguage(e.target.value as 'en' | 'zh')}
          className="border rounded px-2 py-1 text-sm bg-background"
        >
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </div>

      {/* Tabs: Watchlist | Binance Data | News Sources */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <TabsList className="grid w-full grid-cols-3 max-w-2xl shrink-0">
          <TabsTrigger value="watchlist">{t('settings.watchlist', 'Watchlist')}</TabsTrigger>
          <TabsTrigger value="binance-data" className="flex items-center gap-1.5">
            <ExchangeIcon exchangeId="binance" size={16} />
            Binance
          </TabsTrigger>
          <TabsTrigger value="news-sources">{t('settings.newsSources', 'News Sources')}</TabsTrigger>
        </TabsList>

        <TabsContent value="watchlist" className="mt-4 flex-1 min-h-0 flex flex-col overflow-auto">
          <WatchlistSettingsTab
            t={t}
            availableSymbols={bnAvailableSymbols}
            watchlistSymbols={bnWatchlistSymbols}
            maxSymbols={bnMaxSymbols}
            loading={bnLoading}
            saving={bnSaving}
            error={bnError}
            success={bnSuccess}
            searchQuery={bnSearchQuery}
            onSearchQueryChange={setBnSearchQuery}
            onToggleSymbol={toggleBnWatchlistSymbol}
            onSave={handleSaveBnWatchlist}
          />
        </TabsContent>

        <TabsContent value="binance-data" className="mt-4 flex-1 min-h-0 flex flex-col">
          <BinanceDataSettingsTab
            t={t}
            watchlistSymbols={bnWatchlistSymbols}
            storageStats={storageStats}
            storageLoading={storageLoading}
            retentionDays={retentionDays}
            setRetentionDays={setRetentionDays}
            retentionSaving={retentionSaving}
            retentionError={retentionError}
            retentionSuccess={retentionSuccess}
            backfillStatus={backfillStatus}
            backfillStarting={backfillStarting}
            backfillJustCompleted={backfillJustCompleted}
            onSaveRetention={handleSaveRetention}
            onStartBackfill={handleStartBackfill}
          />
        </TabsContent>

        <TabsContent value="news-sources" className="mt-4 flex-1 min-h-0 flex flex-col overflow-auto">
          <NewsSourcesSettingsTab {...newsSourcesSettings} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
