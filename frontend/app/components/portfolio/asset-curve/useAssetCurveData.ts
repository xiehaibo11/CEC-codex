import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  AssetCurveData,
  Timeframe,
  TimeframeCacheEntry,
} from './types'
import { CACHE_STALE_MS } from './types'

interface UseAssetCurveDataOptions {
  initialData?: AssetCurveData[]
  wsRef?: React.MutableRefObject<WebSocket | null>
  timeframe: Timeframe
  tradingMode: string
}

export function useAssetCurveData({
  initialData,
  wsRef,
  timeframe,
  tradingMode,
}: UseAssetCurveDataOptions) {
  const prevTradingMode = useRef(tradingMode)
  const cacheRef = useRef(new Map<string, TimeframeCacheEntry>())
  const [data, setData] = useState<AssetCurveData[]>(initialData || [])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)
  const [liveAccountTotals, setLiveAccountTotals] = useState<Map<number, number>>(new Map())
  const [logoPulseMap, setLogoPulseMap] = useState<Map<number, number>>(new Map())

  const storeCache = useCallback(
    (tf: Timeframe, nextData: AssetCurveData[]) => {
      const cacheKey = `${tf}_${tradingMode}`
      cacheRef.current.set(cacheKey, {
        data: nextData,
        lastFetched: Date.now(),
        initialized: true,
      })
    },
    [tradingMode],
  )

  const primeFromCache = useCallback(
    (tf: Timeframe) => {
      const cacheKey = `${tf}_${tradingMode}`
      const cached = cacheRef.current.get(cacheKey)
      if (!cached) return false
      setData(cached.data)
      setLoading(false)
      setError(null)
      setIsInitialized((prev) => prev || cached.initialized)
      return true
    },
    [tradingMode],
  )

  useEffect(() => {
    const socket = wsRef?.current
    if (!socket) return

    const handleMessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg?.type === 'arena_asset_update' && msg.accounts) {
          const accountsToPulse: number[] = []
          setLiveAccountTotals((prev) => {
            const next = new Map(prev)
            ;(msg.accounts as Array<{ account_id: number; total_assets?: number }>).forEach(
              (account) => {
                if (account?.account_id == null) return

                const nextValue = Number(account.total_assets ?? 0)
                const previousValue = prev.get(account.account_id)
                if (previousValue !== undefined && previousValue !== nextValue) {
                  accountsToPulse.push(account.account_id)
                }
                next.set(account.account_id, nextValue)
              },
            )
            return next
          })
          if (accountsToPulse.length) {
            setLogoPulseMap((prev) => {
              const updated = new Map(prev)
              accountsToPulse.forEach((accountId) => {
                const current = updated.get(accountId) ?? 0
                updated.set(accountId, current + 1)
              })
              return updated
            })
          }
        }

        if (msg.type === 'asset_curve_data' || msg.type === 'asset_curve_update') {
          const nextTimeframe = (msg.timeframe as Timeframe) ?? timeframe
          const nextData = msg.data || []
          storeCache(nextTimeframe, nextData)
          if (nextTimeframe === timeframe) {
            setData(nextData)
            if (msg.type === 'asset_curve_data') {
              setLoading(false)
              setError(null)
            }
            setIsInitialized(true)
          }
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    socket.addEventListener('message', handleMessage)
    return () => {
      socket.removeEventListener('message', handleMessage)
    }
  }, [wsRef, timeframe, storeCache])

  useEffect(() => {
    if (prevTradingMode.current !== null && prevTradingMode.current !== tradingMode) {
      setData([])
      setLiveAccountTotals(new Map())
      cacheRef.current.clear()
    }
    prevTradingMode.current = tradingMode
  }, [tradingMode])

  useEffect(() => {
    const cacheKey = `${timeframe}_${tradingMode}`
    const cached = cacheRef.current.get(cacheKey)
    const isFresh = cached ? Date.now() - cached.lastFetched < CACHE_STALE_MS : false
    const hadCache = primeFromCache(timeframe)

    if (isFresh) return

    const socket = wsRef?.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      if (!hadCache) setLoading(true)
      setError(null)
      socket.send(
        JSON.stringify({
          type: 'get_asset_curve',
          timeframe,
          trading_mode: tradingMode,
        }),
      )
    } else if (!hadCache && initialData && !isInitialized) {
      setData(initialData)
      setIsInitialized(true)
      storeCache(timeframe, initialData)
    }
  }, [
    timeframe,
    tradingMode,
    wsRef,
    initialData,
    isInitialized,
    primeFromCache,
    storeCache,
  ])

  return {
    data,
    loading,
    error,
    isInitialized,
    liveAccountTotals,
    logoPulseMap,
  }
}
