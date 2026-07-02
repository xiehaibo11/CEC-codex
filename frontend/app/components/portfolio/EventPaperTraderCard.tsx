import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  getEventPaperTraderBets,
  getEventPaperTraderStats,
  getEventPaperTraders,
  type EventPaperTrader,
  type EventPaperTraderBet,
  type EventPaperTraderStats,
} from '@/lib/eventContractApi'
import BetsTable from './event-paper-trader/BetsTable'
import StatsSummary from './event-paper-trader/StatsSummary'
import TraderSelector from './event-paper-trader/TraderSelector'

const POLL_MS = 5000
const BETS_LIMIT = 20
const BETS_DISPLAY_COUNT = 10

/** Live "follow the trader" dashboard card for the event-contract paper
 * traders running server-side (spec module 3). Polls bets + stats for the
 * selected trader every 5s; the trader list itself is refreshed on the same
 * cadence so newly created/enabled traders show up without a page reload. */
export default function EventPaperTraderCard() {
  const { t } = useTranslation()
  const [traders, setTraders] = useState<EventPaperTrader[]>([])
  const [tradersLoaded, setTradersLoaded] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [bets, setBets] = useState<EventPaperTraderBet[]>([])
  const [stats, setStats] = useState<EventPaperTraderStats | null>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())

  // Trader list - polled continuously so the selector reflects new traders.
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const data = await getEventPaperTraders()
        if (!cancelled) setTraders(data)
      } catch (error) {
        console.error('Failed to load event paper traders:', error)
      } finally {
        if (!cancelled) setTradersLoaded(true)
      }
    }
    load()
    const intervalId = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(intervalId)
    }
  }, [])

  // Keep the selection valid as the trader list changes.
  useEffect(() => {
    if (traders.length === 0) {
      setSelectedId(null)
      return
    }
    setSelectedId(prev => (prev != null && traders.some(trader => trader.id === prev) ? prev : traders[0].id))
  }, [traders])

  // Bets + stats for the selected trader - paused entirely when there is no
  // trader to follow.
  useEffect(() => {
    if (selectedId == null) {
      setBets([])
      setStats(null)
      return
    }
    let cancelled = false
    const load = async () => {
      try {
        const [betsResponse, statsResponse] = await Promise.all([
          getEventPaperTraderBets(selectedId, BETS_LIMIT, 0),
          getEventPaperTraderStats(selectedId),
        ])
        if (!cancelled) {
          setBets(betsResponse.bets)
          setStats(statsResponse)
        }
      } catch (error) {
        console.error('Failed to load event paper trader bets/stats:', error)
      }
    }
    load()
    const intervalId = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(intervalId)
    }
  }, [selectedId])

  // Client-side clock tick for the open-bet countdowns.
  useEffect(() => {
    const intervalId = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(intervalId)
  }, [])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="text-base">{t('eventPaperTrader.title', 'Live Paper Traders')}</CardTitle>
        {traders.length > 1 && selectedId != null && (
          <TraderSelector traders={traders} selectedId={selectedId} onChange={setSelectedId} />
        )}
      </CardHeader>
      <CardContent>
        {!tradersLoaded ? (
          <p className="text-sm text-muted-foreground">{t('common.loading', 'Loading...')}</p>
        ) : traders.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {t('eventPaperTrader.empty', 'No live event-contract paper traders yet')}
          </p>
        ) : (
          <div className="space-y-4">
            {stats && <StatsSummary stats={stats} />}
            <BetsTable bets={bets.slice(0, BETS_DISPLAY_COUNT)} nowMs={nowMs} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
