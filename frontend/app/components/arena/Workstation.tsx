import { useEffect, useState, useMemo, useRef } from 'react'
import PixelCharacter from './PixelCharacter'
import { ACTIVITY_DWELL_MS, MOVE_DURATION_MS } from './workstation/helpers'
import { Monitor } from './workstation/Monitor'
import { MoodBubble } from './workstation/MoodBubble'
import type { CharacterDirection, CharacterState, WorkstationProps } from './workstation/types'

export default function Workstation({
  traderName, exchanges, avatarPresetId, state, animationMap, activitySignal,
}: WorkstationProps) {
  const isDual = exchanges.length >= 2
  const isOff = state === 'offline'

  // Data-driven: character stands at the exchange with more activity
  const targetIdx = useMemo(() => {
    if (!isDual || isOff) return 0
    const [a, b] = exchanges
    // Prefer exchange with open positions
    if (b.positionCount > 0 && a.positionCount === 0) return 1
    if (a.positionCount > 0 && b.positionCount === 0) return 0
    // Both have positions: prefer higher abs PnL
    if (a.positionCount > 0 && b.positionCount > 0) {
      return Math.abs(b.unrealizedPnl || 0) > Math.abs(a.unrealizedPnl || 0) ? 1 : 0
    }
    return 0
  }, [isDual, isOff, exchanges])

  const [displayIdx, setDisplayIdx] = useState(targetIdx)
  const [travelIdx, setTravelIdx] = useState<number | null>(null)
  const [isMoving, setIsMoving] = useState(false)
  const [dwellState, setDwellState] = useState<CharacterState | null>(null)
  const [charDir, setCharDir] = useState<CharacterDirection>(isOff ? 'down' : 'up')
  const timeoutRef = useRef<{ arrival: ReturnType<typeof setTimeout> | null; settle: ReturnType<typeof setTimeout> | null }>({
    arrival: null,
    settle: null,
  })
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const currentIdxRef = useRef(targetIdx)
  const lastDirectionRef = useRef<CharacterDirection>('up')

  const clearPulseTimeouts = () => {
    if (timeoutRef.current.arrival) {
      clearTimeout(timeoutRef.current.arrival)
      timeoutRef.current.arrival = null
    }
    if (timeoutRef.current.settle) {
      clearTimeout(timeoutRef.current.settle)
      timeoutRef.current.settle = null
    }
  }

  const clearPulseTimers = () => {
    clearPulseTimeouts()
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  useEffect(() => {
    if (!isDual || isOff) {
      setDisplayIdx(targetIdx)
      setTravelIdx(null)
      currentIdxRef.current = targetIdx
      setIsMoving(false)
      setDwellState(null)
      setCharDir(isOff ? 'down' : 'up')
      return
    }
    if (!isMoving && dwellState === null && displayIdx !== targetIdx) {
      const nextDir = targetIdx > displayIdx ? 'right' : 'left'
      lastDirectionRef.current = nextDir
      setCharDir(nextDir)
      setIsMoving(true)
      setTravelIdx(targetIdx)
      clearPulseTimeouts()
      timeoutRef.current.arrival = setTimeout(() => {
        setDisplayIdx(targetIdx)
        setTravelIdx(null)
        currentIdxRef.current = targetIdx
        setIsMoving(false)
        setCharDir('up')
      }, MOVE_DURATION_MS)
    }
  }, [isDual, isOff, targetIdx, displayIdx, isMoving, dwellState])

  const triggerPulse = (nextState: CharacterState, preferredIdx?: number) => {
    if (!isDual || isOff) return
    clearPulseTimeouts()

    const currentIdx = currentIdxRef.current
    const fallbackIdx = currentIdx === 0 ? 1 : 0
    const destinationIdx = preferredIdx === undefined
      ? fallbackIdx
      : preferredIdx === currentIdx
        ? fallbackIdx
        : preferredIdx
    const arrivalState = nextState === 'program_running' ? 'idle' : nextState

    setDwellState(null)

    if (destinationIdx === currentIdx) {
      setDisplayIdx(destinationIdx)
      setTravelIdx(null)
      setIsMoving(false)
      setCharDir('up')
      setDwellState(arrivalState)
      timeoutRef.current.settle = setTimeout(() => {
        setDwellState(null)
      }, ACTIVITY_DWELL_MS)
      return
    }

    const nextDir = destinationIdx > currentIdx ? 'right' : 'left'
    lastDirectionRef.current = nextDir
    setCharDir(nextDir)
    setIsMoving(true)
    setTravelIdx(destinationIdx)

    timeoutRef.current.arrival = setTimeout(() => {
      setDisplayIdx(destinationIdx)
      setTravelIdx(null)
      currentIdxRef.current = destinationIdx
      setIsMoving(false)
      setCharDir('up')
      setDwellState(arrivalState)
      timeoutRef.current.settle = setTimeout(() => {
        setDwellState(null)
      }, ACTIVITY_DWELL_MS)
    }, MOVE_DURATION_MS)
  }

  useEffect(() => {
    if (!activitySignal || !isDual || isOff) return
    const exchangeIdx = exchanges.findIndex(ex => ex.exchange === activitySignal.exchange)
    triggerPulse(activitySignal.state, exchangeIdx >= 0 ? exchangeIdx : undefined)
  }, [activitySignal?.seq])

  useEffect(() => {
    if (!isDual || isOff) return

    const startPulseLoop = () => {
      triggerPulse('idle')
    }

    const initialDelay = 20_000 + Math.random() * 20_000
    const initialTimer = setTimeout(() => {
      startPulseLoop()
      intervalRef.current = setInterval(() => {
        triggerPulse('idle')
      }, 60_000)
    }, initialDelay)

    return () => {
      clearTimeout(initialTimer)
      clearPulseTimers()
    }
  }, [isDual, isOff, targetIdx])

  useEffect(() => () => {
    clearPulseTimers()
  }, [])

  const charState = (() => {
    if (isOff) return 'offline' as const
    if (isMoving) return 'just_traded' as const
    if (dwellState) return dwellState
    if (!isDual) return state
    const ex = exchanges[displayIdx]
    if (ex?.unrealizedPnl && ex.unrealizedPnl > 0) return 'holding_profit' as const
    if (ex?.unrealizedPnl && ex.unrealizedPnl < 0) return 'holding_loss' as const
    return state
  })()

  // Layout: fixed monitor size, workstation width scales with monitor count
  const MON_W = 170
  const MON_H = 110
  const MON_GAP = 20
  const DESK_PAD = 40  // padding each side
  const monCount = Math.min(exchanges.length, 3)
  const monAreaW = monCount * MON_W + Math.max(0, monCount - 1) * MON_GAP
  const wWidth = monAreaW + DESK_PAD * 2

  const spread = monCount > 1 ? (MON_W + MON_GAP) / 2 : 0
  const visualIdx = travelIdx ?? displayIdx
  const charX = isDual && !isOff ? (visualIdx === 0 ? -spread : spread) : 0

  const monTop = 6
  const deskTop = monTop + MON_H + 7

  return (
    <div className="relative" style={{ width: wWidth, height: 260 }}>
      <div className="absolute left-0 right-0 rounded-lg" style={{
        top: 0, bottom: 0,
        background: 'rgba(18,20,26,0.55)',
        border: '1px solid rgba(42,45,56,0.4)',
      }}>
        {/* Monitors */}
        <div className="absolute" style={{
          top: monTop, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: monCount > 1 ? MON_GAP : 0, justifyContent: 'center',
        }}>
          {exchanges.slice(0, monCount).map((ex, i) => (
            <Monitor key={i} ex={ex} isOff={isOff}
              width={MON_W} height={MON_H} />
          ))}
          {exchanges.length === 0 && (
            <Monitor
              ex={{ exchange: 'hyperliquid', equity: null, unrealizedPnl: null, positionCount: 0, positions: [], equityHistory: [] }}
              isOff={isOff} width={MON_W} height={MON_H}
            />
          )}
        </div>

        {/* Desk — flush under monitors */}
        <div className="absolute" style={{
          top: deskTop, left: 8, right: 8, height: 12,
          background: 'linear-gradient(180deg, #5a4a38 0%, #4a3c2c 100%)',
          borderRadius: 3,
          borderTop: '1px solid #6a5a48',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        }} />

        {/* Nameplate */}
        <div className="absolute" style={{
          top: deskTop + 2, left: '50%', transform: 'translateX(-50%)',
          background: '#2a2420', border: '1px solid #4a3828',
          borderRadius: 2, padding: '1px 8px',
          fontSize: 9, fontFamily: 'monospace', color: '#c8a882',
          whiteSpace: 'nowrap', lineHeight: '13px', zIndex: 3,
          maxWidth: wWidth - 30,
          overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'center',
        }}>
          {traderName}
        </div>

        {/* Character */}
        <div className="absolute" style={{
          bottom: 10, left: '50%',
          transform: `translateX(calc(-50% + ${charX}px))`,
          transition: 'transform 1.1s ease-in-out',
          zIndex: 2,
        }}>
          <PixelCharacter
            presetId={avatarPresetId}
            state={charState}
            direction={charDir}
            scale={1.6}
            animationMap={animationMap}
          />
          {!isMoving && <MoodBubble state={charState} />}
        </div>
      </div>
    </div>
  )
}
