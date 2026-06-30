import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  getHyperliquidAvailableSymbols,
  getHyperliquidWatchlist,
  updateHyperliquidWatchlist,
} from '@/lib/api'
import type { HyperliquidSymbolMeta } from '@/lib/api'
import { useTranslation } from 'react-i18next'
import GlobalSamplingForm from './strategy-panel/GlobalSamplingForm'
import StrategyConfigForm from './strategy-panel/StrategyConfigForm'
import WatchlistMovedNotice from './strategy-panel/WatchlistMovedNotice'
import type { GlobalSamplingConfig, SignalPool, StrategyConfig, StrategyPanelProps } from './strategy-panel/types'

export default function StrategyPanel({
  accountId,
  accountName,
  refreshKey,
  accounts,
  onAccountChange,
  accountsLoading = false,
}: StrategyPanelProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Trader-specific settings
  const [priceThreshold, setPriceThreshold] = useState<string>('1.0')
  const [triggerInterval, setTriggerInterval] = useState<string>('150')
  const [enabled, setEnabled] = useState<boolean>(true)
  const [scheduledTriggerEnabled, setScheduledTriggerEnabled] = useState<boolean>(true)
  const [lastTriggerAt, setLastTriggerAt] = useState<string | null>(null)
  const [signalPoolIds, setSignalPoolIds] = useState<number[]>([])
  const [signalPools, setSignalPools] = useState<SignalPool[]>([])
  const [exchange, setExchange] = useState<string>('binance')

  // Global settings
  const [samplingInterval, setSamplingInterval] = useState<string>('18')
  const [availableWatchlistSymbols, setAvailableWatchlistSymbols] = useState<HyperliquidSymbolMeta[]>([])
  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>([])
  const [watchlistLoading, setWatchlistLoading] = useState(true)
  const [watchlistSaving, setWatchlistSaving] = useState(false)
  const [watchlistError, setWatchlistError] = useState<string | null>(null)
  const [watchlistSuccess, setWatchlistSuccess] = useState<string | null>(null)
  const [maxWatchlistSymbols, setMaxWatchlistSymbols] = useState<number>(10)

  const resetMessages = useCallback(() => {
    setError(null)
    setSuccess(null)
  }, [])

  const resetWatchlistMessages = useCallback(() => {
    setWatchlistError(null)
    setWatchlistSuccess(null)
  }, [])

  const fetchStrategy = useCallback(async () => {
    setLoading(true)
    resetMessages()
    try {
      // Fetch trader-specific config and signal pools in parallel
      const [strategyResponse, signalsResponse, globalResponse] = await Promise.all([
        fetch(`/api/account/${accountId}/strategy`),
        fetch('/api/signals'),
        fetch('/api/config/global-sampling'),
      ])

      if (strategyResponse.ok) {
        const strategy: StrategyConfig = await strategyResponse.json()
        setPriceThreshold((strategy.price_threshold ?? 1.0).toString())
        setTriggerInterval((strategy.interval_seconds ?? 150).toString())
        setEnabled(strategy.enabled)
        setScheduledTriggerEnabled(strategy.scheduled_trigger_enabled ?? true)
        setLastTriggerAt(strategy.last_trigger_at ?? null)
        // Use new signal_pool_ids field, fallback to old signal_pool_id for compatibility
        const poolIds = strategy.signal_pool_ids ?? (strategy.signal_pool_id ? [strategy.signal_pool_id] : [])
        setSignalPoolIds(poolIds)
        setExchange('binance')
      }

      if (signalsResponse.ok) {
        const data = await signalsResponse.json()
        const pools: SignalPool[] = data.pools || []
        // Only show enabled signal pools
        setSignalPools(pools.filter((p) => p.enabled))
      }

      if (globalResponse.ok) {
        const globalConfig: GlobalSamplingConfig = await globalResponse.json()
        setSamplingInterval((globalConfig.sampling_interval ?? 18).toString())
      }
    } catch (err) {
      console.error('Failed to load strategy config', err)
      setError(err instanceof Error ? err.message : 'Unable to load strategy configuration.')
    } finally {
      setLoading(false)
    }
  }, [accountId, resetMessages])

  const fetchWatchlistConfig = useCallback(async () => {
    resetWatchlistMessages()
    setWatchlistLoading(true)
    try {
      const [available, watchlist] = await Promise.all([
        getHyperliquidAvailableSymbols(),
        getHyperliquidWatchlist(),
      ])
      setAvailableWatchlistSymbols(available.symbols || [])
      setMaxWatchlistSymbols(watchlist.max_symbols ?? available.max_symbols ?? 10)
      setWatchlistSymbols(watchlist.symbols || [])
    } catch (err) {
      console.error('Failed to load watchlist', err)
      setWatchlistError(err instanceof Error ? err.message : 'Unable to load watchlist.')
    } finally {
      setWatchlistLoading(false)
    }
  }, [resetWatchlistMessages])
  useEffect(() => {
    fetchStrategy()
  }, [fetchStrategy, refreshKey])

  useEffect(() => {
    fetchWatchlistConfig()
  }, [fetchWatchlistConfig, refreshKey])

  const accountOptions = useMemo(() => {
    if (!accounts || accounts.length === 0) return []
    return accounts.map((account) => ({
      value: account.id.toString(),
      label: `${account.name}${account.model ? ` (${account.model})` : ''}`,
    }))
  }, [accounts])

  const selectedAccountLabel = useMemo(() => {
    const match = accountOptions.find((option) => option.value === accountId.toString())
    return match?.label ?? accountName
  }, [accountOptions, accountId, accountName])

  const watchlistCount = watchlistSymbols.length

  useEffect(() => {
    resetMessages()
  }, [accountId, resetMessages])

  const toggleWatchlistSymbol = useCallback(
    (symbol: string) => {
      const symbolUpper = symbol.toUpperCase()
      resetWatchlistMessages()
      setWatchlistSymbols((prev) => {
        if (prev.includes(symbolUpper)) {
          return prev.filter((entry) => entry !== symbolUpper)
        }
        if (prev.length >= maxWatchlistSymbols) {
          setWatchlistError(`You can monitor up to ${maxWatchlistSymbols} symbols.`)
          return prev
        }
        return [...prev, symbolUpper]
      })
    },
    [maxWatchlistSymbols, resetWatchlistMessages]
  )

  const handleSaveWatchlist = useCallback(async () => {
    resetWatchlistMessages()
    if (watchlistSymbols.length < 1) {
      setWatchlistError('At least one symbol must be selected.')
      return
    }
    try {
      setWatchlistSaving(true)
      const response = await updateHyperliquidWatchlist(watchlistSymbols)
      setWatchlistSymbols(response.symbols || [])
      setMaxWatchlistSymbols(response.max_symbols ?? maxWatchlistSymbols)
      setWatchlistSuccess('Watchlist updated successfully.')
    } catch (err) {
      console.error('Failed to update watchlist', err)
      setWatchlistError(err instanceof Error ? err.message : 'Failed to update watchlist.')
    } finally {
      setWatchlistSaving(false)
    }
  }, [watchlistSymbols, maxWatchlistSymbols, resetWatchlistMessages])

  const handleSaveTrader = useCallback(async () => {
    resetMessages()

    const threshold = parseFloat(priceThreshold)
    const interval = parseInt(triggerInterval)

    if (!Number.isFinite(threshold) || threshold <= 0) {
      setError('Price threshold must be a positive number.')
      return
    }

    if (!Number.isInteger(interval) || interval <= 0) {
      setError('Trigger interval must be a positive integer.')
      return
    }

    try {
      setSaving(true)
      const payload = {
        price_threshold: threshold,
        interval_seconds: interval,
        enabled: enabled,
        scheduled_trigger_enabled: scheduledTriggerEnabled,
        trigger_mode: "unified",
        tick_batch_size: 1,
        signal_pool_ids: signalPoolIds.length > 0 ? signalPoolIds : null,
        exchange: exchange,
      }
      console.log('Frontend saving payload:', payload)
      const response = await fetch(`/api/account/${accountId}/strategy`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error('Failed to save trader configuration')
      }

      const result: StrategyConfig = await response.json()
      setPriceThreshold((result.price_threshold ?? 1.0).toString())
      setTriggerInterval((result.interval_seconds ?? 150).toString())
      setEnabled(result.enabled)
      setScheduledTriggerEnabled(result.scheduled_trigger_enabled ?? true)
      setLastTriggerAt(result.last_trigger_at ?? null)
      // Use new signal_pool_ids field
      const poolIds = result.signal_pool_ids ?? (result.signal_pool_id ? [result.signal_pool_id] : [])
      setSignalPoolIds(poolIds)
      setExchange('binance')

      setSuccess('Trader configuration saved successfully.')
    } catch (err) {
      console.error('Failed to update trader config', err)
      setError(err instanceof Error ? err.message : 'Failed to save trader configuration.')
    } finally {
      setSaving(false)
    }
  }, [accountId, priceThreshold, triggerInterval, enabled, scheduledTriggerEnabled, signalPoolIds, exchange, resetMessages])

  const handleSaveGlobal = useCallback(async () => {
    resetMessages()

    const interval = parseInt(samplingInterval)

    if (!Number.isInteger(interval) || interval <= 0) {
      setError('Sampling interval must be a positive integer.')
      return
    }

    try {
      setSaving(true)
      const response = await fetch('/api/config/global-sampling', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sampling_interval: interval,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to save global configuration')
      }

      const result: GlobalSamplingConfig = await response.json()
      setSamplingInterval((result.sampling_interval ?? 18).toString())

      setSuccess('Global configuration saved successfully.')
    } catch (err) {
      console.error('Failed to update global config', err)
      setError(err instanceof Error ? err.message : 'Failed to save global configuration.')
    } finally {
      setSaving(false)
    }
  }, [samplingInterval, resetMessages])

  return (
    <div className="h-full flex flex-col">
      <p className="text-sm text-muted-foreground mb-4">{t('strategy.description', 'Configure trigger parameters and watchlist')}</p>
      <Tabs defaultValue="strategy" className="flex flex-col h-full flex-1 overflow-hidden">
        <TabsList className="grid grid-cols-3 max-w-2xl mb-4">
          <TabsTrigger value="strategy">{t('strategy.aiStrategy', 'AI Strategy')}</TabsTrigger>
          <TabsTrigger value="watchlist">{t('strategy.symbolWatchlist', 'Symbol Watchlist')}</TabsTrigger>
          <TabsTrigger value="global">{t('strategy.globalConfig', 'Global Configuration')}</TabsTrigger>
        </TabsList>
        <TabsContent value="strategy" className="flex-1 overflow-y-auto space-y-6">
          {loading ? (
            <div className="text-sm text-muted-foreground">{t('strategy.loadingStrategy', 'Loading strategy…')}</div>
          ) : (
            <StrategyConfigForm
              accountId={accountId}
              accountName={accountName}
              accountOptions={accountOptions}
              accountsLoading={accountsLoading}
              selectedAccountLabel={selectedAccountLabel}
              error={error}
              success={success}
              exchange={exchange}
              signalPools={signalPools}
              signalPoolIds={signalPoolIds}
              triggerInterval={triggerInterval}
              scheduledTriggerEnabled={scheduledTriggerEnabled}
              enabled={enabled}
              lastTriggerAt={lastTriggerAt}
              saving={saving}
              onAccountChange={onAccountChange}
              onResetMessages={resetMessages}
              onExchangeChange={setExchange}
              onSignalPoolIdsChange={setSignalPoolIds}
              onTriggerIntervalChange={setTriggerInterval}
              onScheduledTriggerEnabledChange={(checked) => {
                setScheduledTriggerEnabled(checked)
                resetMessages()
              }}
              onEnabledChange={(checked) => {
                setEnabled(checked)
                resetMessages()
              }}
              onSaveTrader={handleSaveTrader}
            />
          )}
        </TabsContent>
        <TabsContent value="watchlist" className="flex-1 overflow-y-auto space-y-4">
          <WatchlistMovedNotice watchlistSymbols={watchlistSymbols} />
        </TabsContent>
        <TabsContent value="global" className="flex-1 overflow-y-auto space-y-4">
          <GlobalSamplingForm
            loading={loading}
            samplingInterval={samplingInterval}
            error={error}
            success={success}
            saving={saving}
            onSamplingIntervalChange={setSamplingInterval}
            onResetMessages={resetMessages}
            onSaveGlobal={handleSaveGlobal}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
