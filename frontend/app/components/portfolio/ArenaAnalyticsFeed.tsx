import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ArenaAccountMeta,
  ArenaAnalyticsAccount,
  ArenaAnalyticsSummary,
  getArenaAnalytics,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import Leaderboard from './arena-analytics-feed/Leaderboard'
import OverallStats from './arena-analytics-feed/OverallStats'
import AdvancedAnalytics from './arena-analytics-feed/AdvancedAnalytics'
import { buildAccountsMeta, formatDate } from './arena-analytics-feed/formatters'
import {
  ANALYTICS_CACHE,
  AnalyticsCacheEntry,
  ArenaAnalyticsFeedProps,
  CACHE_STALE_MS,
  CacheKey,
  FeedTab,
} from './arena-analytics-feed/types'

export default function ArenaAnalyticsFeed({
  refreshKey,
  autoRefreshInterval = 60_000,
  selectedAccount: selectedAccountProp,
  onSelectedAccountChange,
}: ArenaAnalyticsFeedProps) {
  const [activeTab, setActiveTab] = useState<FeedTab>('leaderboard')
  const [analyticsAccounts, setAnalyticsAccounts] = useState<ArenaAnalyticsAccount[]>([])
  const [summary, setSummary] = useState<ArenaAnalyticsSummary | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)
  const [accountsMeta, setAccountsMeta] = useState<ArenaAccountMeta[]>([])
  const [allTraderOptions, setAllTraderOptions] = useState<ArenaAccountMeta[]>([])
  const [internalSelectedAccount, setInternalSelectedAccount] = useState<number | 'all'>(
    selectedAccountProp ?? 'all',
  )
  const [manualRefreshKey, setManualRefreshKey] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const prevManualRefreshKey = useRef(manualRefreshKey)
  const prevRefreshKey = useRef(refreshKey)

  useEffect(() => {
    if (selectedAccountProp !== undefined) {
      setInternalSelectedAccount(selectedAccountProp)
    }
  }, [selectedAccountProp])

  const activeAccount = selectedAccountProp ?? internalSelectedAccount
  const cacheKey: CacheKey = activeAccount === 'all' ? 'all' : String(activeAccount)

  const primeFromCache = useCallback(
    (key: CacheKey) => {
      const cached = ANALYTICS_CACHE.get(key)
      if (!cached) return false
      setAnalyticsAccounts(cached.accounts)
      setSummary(cached.summary)
      setGeneratedAt(cached.generatedAt)
      setAccountsMeta(cached.accountsMeta)
      setLoading(false)
      return true
    },
    [],
  )

  const writeCache = useCallback(
    (key: CacheKey, entry: Partial<AnalyticsCacheEntry>) => {
      const existing = ANALYTICS_CACHE.get(key)
      ANALYTICS_CACHE.set(key, {
        accounts: entry.accounts ?? existing?.accounts ?? [],
        summary: entry.summary ?? existing?.summary ?? null,
        generatedAt: entry.generatedAt ?? existing?.generatedAt ?? null,
        accountsMeta: entry.accountsMeta ?? existing?.accountsMeta ?? [],
        lastFetched: entry.lastFetched ?? Date.now(),
      })
    },
    [],
  )

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null
    let isMounted = true

    const shouldForce =
      manualRefreshKey !== prevManualRefreshKey.current ||
      refreshKey !== prevRefreshKey.current

    prevManualRefreshKey.current = manualRefreshKey
    prevRefreshKey.current = refreshKey

    const fetchAnalytics = async (forceReload: boolean) => {
      try {
        const cached = ANALYTICS_CACHE.get(cacheKey)
        const isFresh = cached ? Date.now() - cached.lastFetched < CACHE_STALE_MS : false
        if (!forceReload && isFresh) {
          setLoading(false)
          return
        }

        if (!cached) {
          setLoading(true)
        }
        setError(null)

        const accountId = activeAccount === 'all' ? undefined : activeAccount
        const analyticsRes = await getArenaAnalytics(
          accountId ? { account_id: accountId } : undefined,
        )

        if (!isMounted) return

        const nextAccounts = analyticsRes.accounts || []
        const nextSummary = analyticsRes.summary || null
        const nextGeneratedAt = analyticsRes.generated_at || null

        const incoming = nextAccounts.length ? buildAccountsMeta(nextAccounts) : []
        let mergedMeta: ArenaAccountMeta[] = []
        setAccountsMeta((prev) => {
          if (!incoming.length) {
            mergedMeta = prev
            return prev
          }
            const metaMap = new Map<number, ArenaAccountMeta>()
            prev.forEach((meta) => {
              metaMap.set(meta.account_id, meta)
            })
            incoming.forEach((meta) => {
              metaMap.set(meta.account_id, {
                account_id: meta.account_id,
                name: meta.name,
                model: meta.model ?? null,
              })
            })
            mergedMeta = Array.from(metaMap.values())
            return mergedMeta
        })

        // Update allTraderOptions only when viewing 'all' to preserve complete list
        if (activeAccount === 'all') {
          setAllTraderOptions((prev) => {
            const metaMap = new Map<number, ArenaAccountMeta>()
            prev.forEach((meta) => {
              metaMap.set(meta.account_id, meta)
            })
            mergedMeta.forEach((meta) => {
              metaMap.set(meta.account_id, meta)
            })
            return Array.from(metaMap.values())
          })
        }

        setAnalyticsAccounts(nextAccounts)
        setSummary(nextSummary)
        setGeneratedAt(nextGeneratedAt)

        writeCache(cacheKey, {
          accounts: nextAccounts,
          summary: nextSummary,
          generatedAt: nextGeneratedAt,
          accountsMeta: mergedMeta,
          lastFetched: Date.now(),
        })
      } catch (err) {
        console.error('Failed to load CEC-codex analytics:', err)
        const message = err instanceof Error ? err.message : 'Failed to load analytics data'
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    const hadCache = primeFromCache(cacheKey)
    if (!hadCache) {
      setLoading(true)
    }

    fetchAnalytics(shouldForce)

    if (autoRefreshInterval > 0) {
      intervalId = setInterval(() => fetchAnalytics(false), autoRefreshInterval)
    }

    return () => {
      if (intervalId) clearInterval(intervalId)
      isMounted = false
    }
  }, [
    activeAccount,
    refreshKey,
    autoRefreshInterval,
    manualRefreshKey,
    cacheKey,
    primeFromCache,
    writeCache,
  ])

  const accountOptions = useMemo(() => {
    return allTraderOptions.sort((a, b) => a.name.localeCompare(b.name))
  }, [allTraderOptions])

  const memoisedAggregates = useMemo(() => {
    const totals = analyticsAccounts.reduce(
      (acc, account) => {
        acc.tradeCount += account.trade_count || 0
        acc.decisionCount += account.decision_count || 0
        acc.executedDecisions += account.executed_decisions || 0
        return acc
      },
      { tradeCount: 0, decisionCount: 0, executedDecisions: 0 },
    )
    return totals
  }, [analyticsAccounts])

  const handleRefreshClick = () => {
    setManualRefreshKey((key) => key + 1)
  }

  const handleAccountFilterChange = (value: number | 'all') => {
    if (selectedAccountProp === undefined) {
      setInternalSelectedAccount(value)
    }
    onSelectedAccountChange?.(value)
  }

  const accountsForDisplay = analyticsAccounts

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Filter</span>
          <select
            value={activeAccount === 'all' ? '' : activeAccount}
            onChange={(e) => {
              const value = e.target.value
              handleAccountFilterChange(value ? Number(value) : 'all')
            }}
            className="h-8 rounded border border-border bg-muted px-2 text-xs uppercase tracking-wide text-foreground"
          >
            <option value="">全部交易员</option>
            {accountOptions.map((meta) => (
              <option key={meta.account_id} value={meta.account_id}>
                {meta.name}{meta.model ? ` (${meta.model})` : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            {activeAccount === 'all'
              ? `Tracking ${accountOptions.length} AI models`
              : 'Single model view'}
          </span>
          {generatedAt && <span className="text-muted-foreground/80">Updated {formatDate(generatedAt)}</span>}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={handleRefreshClick}
            disabled={loading}
          >
            Refresh
          </Button>
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value: FeedTab) => setActiveTab(value)}
        className="flex-1 flex flex-col min-h-0"
      >
        <TabsList className="grid grid-cols-3 gap-0 border border-border bg-muted text-foreground">
          <TabsTrigger
            value="leaderboard"
            className="data-[state=active]:bg-background data-[state=active]:text-foreground border-r border-border text-[10px] md:text-xs"
          >
            LEADERBOARD
          </TabsTrigger>
          <TabsTrigger
            value="summary"
            className="data-[state=active]:bg-background data-[state=active]:text-foreground border-r border-border text-[10px] md:text-xs"
          >
            OVERALL STATS
          </TabsTrigger>
          <TabsTrigger
            value="advanced"
            className="data-[state=active]:bg-background data-[state=active]:text-foreground text-[10px] md:text-xs"
          >
            ADVANCED ANALYTICS
          </TabsTrigger>
        </TabsList>

        <div className="flex-1 border border-t-0 border-border bg-card min-h-0 flex flex-col overflow-hidden">
          {error && <div className="p-4 text-sm text-red-500">{error}</div>}

          {!error && (
            <>
              <TabsContent value="leaderboard" className="flex-1 overflow-y-auto min-h-0 mt-0 p-4 space-y-4">
                <Leaderboard accounts={accountsForDisplay} loading={loading} />
              </TabsContent>

              <TabsContent value="summary" className="flex-1 overflow-y-auto min-h-0 mt-0 p-4">
                <OverallStats
                  summary={summary}
                  loading={loading}
                  modelsTracked={accountOptions.length}
                  aggregates={memoisedAggregates}
                />
              </TabsContent>

              <TabsContent value="advanced" className="flex-1 overflow-y-auto min-h-0 mt-0 p-4 space-y-4">
                <AdvancedAnalytics accounts={accountsForDisplay} loading={loading} />
              </TabsContent>
            </>
          )}
        </div>
      </Tabs>
    </div>
  )
}
