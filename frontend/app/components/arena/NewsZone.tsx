import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import PixelCharacter from './PixelCharacter'
import { AVATAR_PRESETS } from './pixelData/palettes'
import { CharMoodBubble } from './news-zone/CharMoodBubble'
import {
  CHAR_RENDER_SIZE,
  CHAR_SCALE,
  CHAR_ZONE_DEPTH,
  SCREEN_BORDER,
  SCREEN_GAP,
  SCREEN_H,
  SCREEN_Y,
  SSE_BASE,
  WATCHLIST_API,
  ZONE_PAD,
} from './news-zone/constants'
import { FlowScreen } from './news-zone/FlowScreen'
import { advanceCharacters, assignWatchTargets, createInitialCharacters } from './news-zone/movement'
import { NewsScreen } from './news-zone/NewsScreen'
import type { IdleCharacter, NewsZoneProps, SSEFlowSummary, SSENewsItem, WatchType } from './news-zone/types'

export default function NewsZone({
  areaW, areaH, scale, boundTraderPresetIds, animationMap,
}: NewsZoneProps) {
  const [newsItems, setNewsItems] = useState<SSENewsItem[]>([])
  const [flowItems, setFlowItems] = useState<SSEFlowSummary[]>([])
  const [characters, setCharacters] = useState<IdleCharacter[]>([])
  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>([])
  const [newsScrollIdx, setNewsScrollIdx] = useState(0)
  const animFrameRef = useRef<number>(0)
  const lastTickRef = useRef(Date.now())
  const prevNewsIdRef = useRef<number | null>(null)
  const prevFlowSigRef = useRef<string>('')
  const sseRef = useRef<EventSource | null>(null)

  const availablePresets = useMemo(() =>
    AVATAR_PRESETS.filter(p => !boundTraderPresetIds.has(p.id)).map(p => p.id),
    [boundTraderPresetIds],
  )

  const innerW = areaW / scale
  const innerH = areaH / scale
  const screenW = Math.floor((innerW - SCREEN_GAP - SCREEN_BORDER * 4 - ZONE_PAD * 2) / 2)
  const screenBottom = SCREEN_Y + SCREEN_H + SCREEN_BORDER * 2
  const charZoneTop = screenBottom + 10
  const charZoneBottom = Math.min(charZoneTop + CHAR_ZONE_DEPTH, innerH - CHAR_RENDER_SIZE - ZONE_PAD)
  const screenTotalW = screenW * 2 + SCREEN_GAP + SCREEN_BORDER * 4
  const charZoneLeft = Math.max(ZONE_PAD, (innerW - screenTotalW) / 2 - 10)
  const charZoneRight = Math.min(innerW - CHAR_RENDER_SIZE - ZONE_PAD, (innerW + screenTotalW) / 2 + 10 - CHAR_RENDER_SIZE)
  const characterBounds = useMemo(() => ({
    left: charZoneLeft,
    right: charZoneRight,
    top: charZoneTop,
    bottom: charZoneBottom,
  }), [charZoneLeft, charZoneRight, charZoneTop, charZoneBottom])

  // Fetch watchlist symbols
  useEffect(() => {
    fetch(WATCHLIST_API).then(r => r.json()).then(data => {
      const syms = (data?.symbols || data || []) as string[]
      setWatchlistSymbols(syms.length > 0 ? syms : ['BTC', 'ETH'])
    }).catch(() => setWatchlistSymbols(['BTC', 'ETH']))
  }, [])

  // SSE connection
  useEffect(() => {
    if (watchlistSymbols.length === 0) return
    const symbolsParam = watchlistSymbols.join(',')
    const url = `${SSE_BASE}?symbols=${encodeURIComponent(symbolsParam)}&exchange=hyperliquid&timeframe=15m&window=4h`
    const es = new EventSource(url)
    sseRef.current = es

    const handleData = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data)
        const news: SSENewsItem[] = data.news_items || []
        const summaries: SSEFlowSummary[] = data.summaries || []
        if (news.length > 0) setNewsItems(news)
        if (summaries.length > 0) setFlowItems(summaries)
      } catch { /* ignore parse errors */ }
    }
    es.addEventListener('snapshot', handleData)
    es.addEventListener('update', handleData)
    es.onerror = () => {
      es.close()
      setTimeout(() => sseRef.current === es && setWatchlistSymbols(prev => [...prev]), 5000)
    }
    return () => { es.close(); sseRef.current = null }
  }, [watchlistSymbols])

  // Initialize characters — default sit/idle, face up
  useEffect(() => {
    setCharacters(createInitialCharacters(availablePresets, characterBounds))
  }, [availablePresets.length, innerW, innerH])

  // React to new news — scroll to top and trigger characters
  useEffect(() => {
    if (newsItems.length === 0) return
    const topId = newsItems[0]?.id
    if (prevNewsIdRef.current !== null && topId !== prevNewsIdRef.current) {
      setNewsScrollIdx(0)
      triggerWatch('news')
    }
    prevNewsIdRef.current = topId
  }, [newsItems])

  // Auto-cycle news every 12s when no new push
  useEffect(() => {
    if (newsItems.length <= 1) return
    const maxIdx = Math.min(newsItems.length, 10) - 1
    const t = setInterval(() => {
      setNewsScrollIdx(prev => prev >= maxIdx ? 0 : prev + 1)
    }, 12000)
    return () => clearInterval(t)
  }, [newsItems.length])

  // React to flow changes
  useEffect(() => {
    const sig = flowItems.map(f => `${f.symbol}:${f.net_inflow}`).join('|')
    if (prevFlowSigRef.current && sig !== prevFlowSigRef.current) {
      triggerWatch('flow')
    }
    prevFlowSigRef.current = sig
  }, [flowItems])

  // Animation loop — only move walking/watching chars, idle stay frozen
  useEffect(() => {
    const tick = () => {
      const now = Date.now()
      const dt = now - lastTickRef.current
      lastTickRef.current = now
      setCharacters(prev => advanceCharacters(prev, dt, characterBounds))
      animFrameRef.current = requestAnimationFrame(tick)
    }
    animFrameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(animFrameRef.current)
  }, [innerW, innerH, characterBounds])

  // Trigger characters on data update — walk to screen, spread out in front
  const triggerWatch = useCallback((type: WatchType) => {
    setCharacters(prev => assignWatchTargets(prev, type, innerW, screenW, characterBounds))
  }, [innerW, screenW, characterBounds])

  // --- Render ---

  if (availablePresets.length === 0) return null

  const sTotal = screenW * 2 + SCREEN_GAP + SCREEN_BORDER * 4
  const sStartX = (innerW - sTotal) / 2

  return (
    <div style={{
      width: innerW, height: innerH, position: 'relative', overflow: 'hidden',
    }}>
      <NewsScreen
        x={sStartX}
        y={SCREEN_Y}
        w={screenW}
        newsItems={newsItems}
        newsScrollIdx={newsScrollIdx}
      />

      <FlowScreen
        x={sStartX + screenW + SCREEN_BORDER * 2 + SCREEN_GAP}
        y={SCREEN_Y}
        w={screenW}
        flowItems={flowItems}
      />

      {/* Floor area — visible tile pattern */}
      <div style={{
        position: 'absolute',
        left: ZONE_PAD, top: screenBottom + 4,
        width: innerW - ZONE_PAD * 2,
        height: innerH - screenBottom - 4 - ZONE_PAD,
        background: '#b89a6e',
        zIndex: 0,
      }}>
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.15,
          backgroundImage: `
            repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,0,0,0.3) 39px, rgba(0,0,0,0.3) 40px),
            repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,0,0,0.3) 39px, rgba(0,0,0,0.3) 40px)
          `,
        }} />
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 0, height: 16,
          background: 'linear-gradient(180deg, rgba(0,0,0,0.15), transparent)',
        }} />
      </div>

      {/* Idle characters */}
      {characters.map(c => (
        <div key={c.presetId} style={{
          position: 'absolute', left: c.x, top: c.y, zIndex: 10,
        }}>
          {c.mood && <CharMoodBubble mood={c.mood} />}
          <PixelCharacter
            presetId={c.presetId}
            state={c.state}
            direction={c.direction}
            scale={CHAR_SCALE}
            animationMap={animationMap}
          />
        </div>
      ))}
    </div>
  )
}
