import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  getEventPaperTraderBets,
  getEventPaperTraderDailyStats,
  getEventPaperTraders,
} from '@/lib/eventContractApi'
import type {
  EventPaperTrader,
  EventPaperTraderBet,
  EventPaperTraderDailyStats,
} from '@/lib/eventContractApi'
import EventArrowChart from './EventArrowChart'
import type { ArrowKline } from './EventArrowChart'
import EventArrowStatsPanel from './EventArrowStatsPanel'

// The trading cycle is bar-boundary driven on the server. This page remains a
// lightweight display poll and labels itself as Paper/Live capability-gated;
// it is not an execution trigger.
const POLL_INTERVAL_MS = 30_000
const KLINE_COUNT = 500
const BETS_LIMIT = 200

/** Same market-data endpoint the signal preview chart uses (1m candles). */
async function fetchKlines(symbol: string, exchange: string): Promise<ArrowKline[]> {
  const res = await fetch(
    `/api/market/kline-with-indicators/${encodeURIComponent(symbol)}?market=${encodeURIComponent(exchange)}&period=1m&count=${KLINE_COUNT}`,
  )
  if (!res.ok) throw new Error('Failed to fetch K-line data')
  const data = await res.json()
  return (data.klines || []).map((k: any) => ({
    timestamp: k.timestamp,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  }))
}

/**
 * Intentionally bare page for 5/10-minute event contracts: a 1m candlestick
 * chart, permanent entry arrows (long = up arrow below bar, short = down
 * arrow above bar), and a floating daily-stats card. Nothing else.
 */
export default function EventArrowChartPage() {
  const { t } = useTranslation()
  const [traders, setTraders] = useState<EventPaperTrader[]>([])
  const [tradersLoaded, setTradersLoaded] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [klines, setKlines] = useState<ArrowKline[]>([])
  const [bets, setBets] = useState<EventPaperTraderBet[]>([])
  const [stats, setStats] = useState<EventPaperTraderDailyStats | null>(null)

  const selectedTrader = useMemo(
    () => traders.find(trader => trader.id === selectedId) ?? null,
    [traders, selectedId],
  )

  useEffect(() => {
    let cancelled = false
    getEventPaperTraders()
      .then(list => {
        if (cancelled) return
        const productionTraders = list.filter(trader => (
          trader.enabled
          && !trader.policy_error
          && trader.config.signal_mode === 'trend_follow'
          && [5, 10].includes(Number(trader.config.expiry_minutes))
        ))
        setTraders(productionTraders)
        setSelectedId(prev => (
          productionTraders.some(trader => trader.id === prev)
            ? prev
            : productionTraders.length > 0
              ? productionTraders[0].id
              : null
        ))
      })
      .catch(() => {
        /* keep the empty state; the page stays bare */
      })
      .finally(() => {
        if (!cancelled) setTradersLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedTrader) return
    let cancelled = false
    const traderId = selectedTrader.id
    const symbol = selectedTrader.symbol
    const exchange = selectedTrader.exchange
    const tzOffsetMinutes = -new Date().getTimezoneOffset()

    const refresh = () => {
      fetchKlines(symbol, exchange)
        .then(data => {
          if (!cancelled) setKlines(data)
        })
        .catch(() => {
          /* keep last candles on transient errors */
        })
      getEventPaperTraderBets(traderId, BETS_LIMIT)
        .then(data => {
          if (!cancelled) setBets(data.bets || [])
        })
        .catch(() => {
          /* keep last arrows on transient errors */
        })
      getEventPaperTraderDailyStats(traderId, tzOffsetMinutes)
        .then(data => {
          if (!cancelled) setStats(data)
        })
        .catch(() => {
          if (!cancelled) setStats(null) // panel degrades to "--"
        })
    }

    setKlines([])
    setBets([])
    setStats(null)
    refresh()
    const timer = setInterval(refresh, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [selectedTrader])

  return (
    <div className="flex flex-1 flex-col gap-2 min-h-0">
      <div className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
        {selectedTrader?.execution_mode === 'live'
          ? t('eventArrow.liveCapabilityNotice')
          : t('eventArrow.paperSimulationNotice')}
      </div>
      <div className="flex items-center gap-2">
        <select
          value={selectedId ?? ''}
          onChange={e => setSelectedId(Number(e.target.value))}
          disabled={traders.length === 0}
          className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
          aria-label={t('eventArrow.trader')}
        >
          {traders.length === 0 && <option value="">{t('eventArrow.noTraders')}</option>}
          {traders.map(trader => (
            <option key={trader.id} value={trader.id}>
              {trader.name} · {trader.symbol}
            </option>
          ))}
        </select>
        {selectedTrader && (
          <span className="text-xs text-muted-foreground">
            {selectedTrader.symbol} · {selectedTrader.exchange} · {Number(selectedTrader.config.expiry_minutes) || 5}m · {selectedTrader.config.signal_mode || 'trend_follow'}
          </span>
        )}
      </div>

      <div className="relative flex-1 min-h-0 overflow-hidden rounded-md border border-border">
        {selectedTrader ? (
          <>
            <EventArrowChart key={selectedTrader.id} klines={klines} bets={bets} />
            <EventArrowStatsPanel stats={stats} trader={selectedTrader} />
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {tradersLoaded ? t('eventArrow.noTraders') : t('eventArrow.loading')}
          </div>
        )}
      </div>
    </div>
  )
}
