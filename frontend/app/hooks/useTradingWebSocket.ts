import { useCallback, useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { toast } from 'react-hot-toast'
import type { AIDecision } from '@/lib/api'
import type { Account, AppUser, Order, Overview, Position, Trade } from '@/AppShell'

let wsSingleton: WebSocket | null = null
let wsBootstrapped = false

const resolveWsUrl = () => {
  const configuredUrl = import.meta.env.VITE_WS_URL
  if (configuredUrl) {
    return configuredUrl
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  if (import.meta.env.DEV) {
    const backendPort = import.meta.env.VITE_BACKEND_PORT || '5611'
    return `${protocol}//${window.location.hostname}:${backendPort}/ws`
  }

  return `${protocol}//${window.location.host}/ws`
}

interface UseTradingWebSocketOptions {
  tradingMode: string
  account: Account | null
  refreshAccounts: () => void | Promise<void>
  setUser: Dispatch<SetStateAction<AppUser | null>>
  setAccount: Dispatch<SetStateAction<Account | null>>
  setOverview: Dispatch<SetStateAction<Overview | null>>
  setPositions: Dispatch<SetStateAction<Position[]>>
  setOrders: Dispatch<SetStateAction<Order[]>>
  setTrades: Dispatch<SetStateAction<Trade[]>>
  setAiDecisions: Dispatch<SetStateAction<AIDecision[]>>
  setAllAssetCurves: Dispatch<SetStateAction<any[]>>
  setHyperliquidRefreshKey: Dispatch<SetStateAction<number>>
}

const getLiveEnvironment = (tradingMode: string) => (
  tradingMode === 'testnet' || tradingMode === 'mainnet' ? tradingMode : undefined
)

export function useTradingWebSocket({
  tradingMode,
  account,
  refreshAccounts,
  setUser,
  setAccount,
  setOverview,
  setPositions,
  setOrders,
  setTrades,
  setAiDecisions,
  setAllAssetCurves,
  setHyperliquidRefreshKey,
}: UseTradingWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const tradingModeRef = useRef(tradingMode)
  const refreshAccountsRef = useRef(refreshAccounts)

  useEffect(() => {
    refreshAccountsRef.current = refreshAccounts
  }, [refreshAccounts])

  useEffect(() => {
    tradingModeRef.current = tradingMode
    if (tradingMode !== 'paper') {
      setHyperliquidRefreshKey(prev => prev + 1)
    }
  }, [setHyperliquidRefreshKey, tradingMode])

  const requestSnapshot = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false
    }

    wsRef.current.send(JSON.stringify({
      type: 'get_snapshot',
      trading_mode: tradingModeRef.current,
    }))
    return true
  }, [])

  const requestSnapshotAndAssetCurve = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false
    }

    const currentMode = tradingModeRef.current
    const env = getLiveEnvironment(currentMode)
    wsRef.current.send(JSON.stringify({
      type: 'get_snapshot',
      trading_mode: currentMode,
    }))
    wsRef.current.send(JSON.stringify({
      type: 'get_asset_curve',
      timeframe: '5m',
      trading_mode: currentMode,
      ...(env ? { environment: env } : {}),
    }))
    return true
  }, [])

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let listenerCleanup: (() => void) | null = null

    const connectWebSocket = () => {
      try {
        let ws = wsSingleton
        const shouldCreate = !ws || ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED
        if (shouldCreate) {
          ws = new WebSocket(resolveWsUrl())
          wsSingleton = ws
          wsBootstrapped = false
        }

        wsRef.current = ws

        const sendBootstrap = () => {
          if (!ws || ws.readyState !== WebSocket.OPEN || wsBootstrapped) return
          wsBootstrapped = true
          ws.send(JSON.stringify({
            type: 'bootstrap',
            username: 'default',
            initial_capital: 10000,
            trading_mode: tradingModeRef.current,
          }))
        }

        const handleOpen = () => {
          console.log('WebSocket connected')
          sendBootstrap()
        }

        const handleMessage = (e: MessageEvent) => {
          try {
            const msg = JSON.parse(e.data)
            if (msg.type === 'bootstrap_ok') {
              if (msg.user) setUser(msg.user)
              if (msg.account) {
                setAccount(msg.account)
                if (tradingModeRef.current === 'paper') {
                  requestSnapshot()
                }
              }
              refreshAccountsRef.current()
            } else if (msg.type === 'snapshot') {
              if (msg.overview) setOverview(msg.overview)
              if (msg.positions) setPositions(msg.positions)
              if (msg.orders) setOrders(msg.orders)
              if (msg.trades) setTrades(msg.trades)
              if (msg.ai_decisions) setAiDecisions(msg.ai_decisions)
              if (msg.all_asset_curves) setAllAssetCurves(msg.all_asset_curves)
              const currentMode = tradingModeRef.current
              const messageMode = msg.trading_mode as string | undefined
              if (currentMode !== 'paper' && (messageMode === undefined || messageMode === currentMode)) {
                setHyperliquidRefreshKey(prev => prev + 1)
              }
            } else if (msg.type === 'trades') {
              setTrades(msg.trades || [])
            } else if (msg.type === 'order_filled') {
              toast.success('Order filled')
              requestSnapshotAndAssetCurve()
            } else if (msg.type === 'order_pending') {
              toast('Order placed, waiting for fill', { icon: '⏳' })
              requestSnapshotAndAssetCurve()
            } else if (msg.type === 'user_switched') {
              setUser(msg.user)
            } else if (msg.type === 'account_switched') {
              setAccount(msg.account)
              refreshAccountsRef.current()
            } else if (msg.type === 'trade_update') {
              setTrades(prev => [msg.trade, ...prev].slice(0, 100))
              toast.success('New trade executed!', { duration: 2000 })
            } else if (msg.type === 'position_update') {
              setPositions(msg.positions || [])
            } else if (msg.type === 'model_chat_update') {
              setAiDecisions(prev => [msg.decision, ...prev].slice(0, 100))
            } else if (msg.type === 'asset_curve_update' || msg.type === 'asset_curve_data') {
              setAllAssetCurves(msg.data || [])
              const currentMode = tradingModeRef.current
              const messageMode = msg.trading_mode as string | undefined
              if (currentMode !== 'paper' && (messageMode === undefined || messageMode === currentMode)) {
                setHyperliquidRefreshKey(prev => prev + 1)
              }
            } else if (msg.type === 'error') {
              console.error(msg.message)
              toast.error(msg.message || 'Order error')
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err)
          }
        }

        const handleClose = (event: CloseEvent) => {
          console.log('WebSocket closed:', event.code, event.reason)
          wsBootstrapped = false
          if (wsSingleton === ws) wsSingleton = null
          if (wsRef.current === ws) wsRef.current = null

          if (event.code !== 1000 && event.code !== 1001) {
            reconnectTimer = setTimeout(() => {
              console.log('Attempting to reconnect WebSocket...')
              connectWebSocket()
            }, 3000)
          }
        }

        const handleError = (event: Event) => {
          console.error('WebSocket error:', event)
        }

        ws.addEventListener('open', handleOpen)
        ws.addEventListener('message', handleMessage)
        ws.addEventListener('close', handleClose)
        ws.addEventListener('error', handleError)

        listenerCleanup = () => {
          ws?.removeEventListener('open', handleOpen)
          ws?.removeEventListener('message', handleMessage)
          ws?.removeEventListener('close', handleClose)
          ws?.removeEventListener('error', handleError)
        }

        if (ws.readyState === WebSocket.OPEN) {
          sendBootstrap()
        }
      } catch (err) {
        console.error('Failed to create WebSocket:', err)
        reconnectTimer = setTimeout(connectWebSocket, 5000)
      }
    }

    connectWebSocket()

    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      listenerCleanup?.()
    }
  }, [
    requestSnapshot,
    requestSnapshotAndAssetCurve,
    setAccount,
    setAiDecisions,
    setAllAssetCurves,
    setHyperliquidRefreshKey,
    setOrders,
    setOverview,
    setPositions,
    setTrades,
    setUser,
  ])

  useEffect(() => {
    if (account) {
      requestSnapshotAndAssetCurve()
    }
  }, [account, requestSnapshotAndAssetCurve, tradingMode])

  useEffect(() => {
    const refreshInterval = setInterval(() => {
      if (account) {
        requestSnapshotAndAssetCurve()
      }
    }, 300000)

    return () => clearInterval(refreshInterval)
  }, [account, requestSnapshotAndAssetCurve])

  const placeOrder = useCallback((payload: any) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WS not connected, cannot place order')
      toast.error('Not connected to server')
      return
    }
    try {
      wsRef.current.send(JSON.stringify({ type: 'place_order', ...payload }))
      toast('Placing order...', { icon: '📝' })
    } catch (e) {
      console.error(e)
      toast.error('Failed to send order')
    }
  }, [])

  const switchUser = useCallback((username: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WS not connected, cannot switch user')
      toast.error('Not connected to server')
      return
    }
    try {
      wsRef.current.send(JSON.stringify({ type: 'switch_user', username }))
    } catch (e) {
      console.error(e)
      toast.error('Failed to switch user')
    }
  }, [])

  const switchAccount = useCallback((accountId: number) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WS not connected, cannot switch account')
      toast.error('Not connected to server')
      return
    }
    try {
      wsRef.current.send(JSON.stringify({ type: 'switch_account', account_id: accountId }))
    } catch (e) {
      console.error(e)
      toast.error('Failed to switch AI trader')
    }
  }, [])

  return {
    wsRef,
    placeOrder,
    switchUser,
    switchAccount,
    requestSnapshot,
  }
}
