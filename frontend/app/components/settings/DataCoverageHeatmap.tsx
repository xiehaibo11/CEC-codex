import React, { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface CoverageItem {
  date: string
  pct: number
}

interface SymbolCoverage {
  symbol: string
  days: number
  coverage: CoverageItem[]
  exchange: string
  data_type: string
  period?: string | null
  summary?: CoverageSummary
}

interface CoverageSummary {
  window_start: string
  window_end: string
  covered_days: number
  missing_days: number
  min_pct: number
  max_pct: number
  avg_pct: number
  expected_records_per_day: number
  coverage_mode: string
  coverage_unit: string
}

interface DataCoverageHeatmapProps {
  exchange?: string
  dataType?: 'market_flow' | 'klines'
  title?: string
  periodOptions?: string[]
  defaultPeriod?: string
}

export default function DataCoverageHeatmap({
  exchange = 'hyperliquid',
  dataType = 'market_flow',
  title,
  periodOptions = [],
  defaultPeriod,
}: DataCoverageHeatmapProps) {
  const { t } = useTranslation()
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState(defaultPeriod || periodOptions[0] || '')
  const [coverage, setCoverage] = useState<CoverageItem[]>([])
  const [summary, setSummary] = useState<CoverageSummary | null>(null)
  const [symbolsLoading, setSymbolsLoading] = useState(true)
  const [coverageLoading, setCoverageLoading] = useState(false)
  const [days, setDays] = useState(365)
  const periodQuery = useMemo(() => {
    if (dataType !== 'klines' || !selectedPeriod) return ''
    return `&period=${encodeURIComponent(selectedPeriod)}`
  }, [dataType, selectedPeriod])

  useEffect(() => {
    if (periodOptions.length === 0) return
    const nextPeriod = defaultPeriod || periodOptions[0]
    if (!selectedPeriod || !periodOptions.includes(selectedPeriod)) {
      setSelectedPeriod(nextPeriod)
    }
  }, [defaultPeriod, periodOptions, selectedPeriod])

  // Fetch available symbols when exchange, dataType, or period changes
  useEffect(() => {
    const fetchSymbols = async () => {
      setSymbolsLoading(true)
      setSelectedSymbol(null)
      setCoverage([])
      setSummary(null)
      try {
        const res = await fetch(
          `/api/system/data-coverage?days=365&exchange=${exchange}&data_type=${dataType}${periodQuery}`
        )
        if (res.ok) {
          const data = await res.json()
          setSymbols(data.symbols || [])
          if (data.symbols?.length > 0) {
            setSelectedSymbol(data.symbols[0])
          }
        }
      } catch (err) {
        console.error('Failed to fetch symbols:', err)
      } finally {
        setSymbolsLoading(false)
      }
    }
    fetchSymbols()
  }, [exchange, dataType, periodQuery])

  // Fetch coverage when symbol changes
  useEffect(() => {
    if (!selectedSymbol) return
    const fetchCoverage = async () => {
      setCoverageLoading(true)
      try {
        const tzOffset = new Date().getTimezoneOffset()
        const res = await fetch(
          `/api/system/data-coverage?days=${days}&symbol=${selectedSymbol}&tz_offset=${tzOffset}&exchange=${exchange}&data_type=${dataType}${periodQuery}`
        )
        if (res.ok) {
          const data: SymbolCoverage = await res.json()
          setCoverage(data.coverage || [])
          setSummary(data.summary || null)
        }
      } catch (err) {
        console.error('Failed to fetch coverage:', err)
      } finally {
        setCoverageLoading(false)
      }
    }
    fetchCoverage()
  }, [selectedSymbol, days, exchange, dataType, periodQuery])

  const getCellColor = (pct: number) => {
    if (pct === 0) return 'bg-[#dbdbdb]'
    if (pct < 50) return 'bg-red-500/70'
    if (pct < 80) return 'bg-yellow-500/70'
    if (pct < 95) return 'bg-emerald-500/70'
    return 'bg-emerald-600'
  }

  const datasetLabel = dataType === 'klines'
    ? t('settings.coverageDatasetKline', 'K-line')
    : t('settings.coverageDatasetFlow', 'Market flow')
  const granularityLabel = dataType === 'klines'
    ? selectedPeriod
    : t('settings.coverageFlowGranularity', '1m taker flow')
  const coverageModeLabel = summary?.coverage_mode === 'period_span'
    ? t('settings.coverageModeSpan', 'period span')
    : summary?.coverage_mode === 'daily_expected_records'
      ? t('settings.coverageModeExpected', 'expected records')
      : t('settings.coverageModeHourly', 'hourly presence')

  if (symbolsLoading) {
    return <div className="text-sm text-muted-foreground">{t('common.loading', 'Loading...')}</div>
  }

  if (symbols.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        {t('settings.noDataCollected', 'No data collected yet')}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {title && <div className="text-sm font-medium">{title}</div>}
      {/* Symbol tabs + Days selector + Legend */}
      <div className="flex items-center gap-2 flex-wrap justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {periodOptions.length > 0 && (
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="border rounded px-2 py-1 text-sm bg-background"
              aria-label="K-line period"
            >
              {periodOptions.map((period) => (
                <option key={period} value={period}>{period}</option>
              ))}
            </select>
          )}
          {symbols.map((sym) => (
            <button
              key={sym}
              onClick={() => setSelectedSymbol(sym)}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                selectedSymbol === sym
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/80 text-muted-foreground'
              }`}
            >
              {sym}
            </button>
          ))}
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="border rounded px-2 py-1 text-sm bg-background ml-2"
          >
            <option value={30}>30 {t('settings.days', 'days')}</option>
            <option value={60}>60 {t('settings.days', 'days')}</option>
            <option value={90}>90 {t('settings.days', 'days')}</option>
            <option value={180}>180 {t('settings.days', 'days')}</option>
            <option value={365}>365 {t('settings.days', 'days')}</option>
            <option value={730}>730 {t('settings.days', 'days')}</option>
          </select>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-[#dbdbdb]" />
            <span>0%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-red-500/70" />
            <span>&lt;50%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-yellow-500/70" />
            <span>50-80%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-emerald-500/70" />
            <span>80-95%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-sm bg-emerald-600" />
            <span>&gt;95%</span>
          </div>
        </div>
      </div>

      {summary && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded border bg-muted/40 px-2 py-1">
            {datasetLabel}: <span className="font-medium text-foreground">{granularityLabel}</span>
          </span>
          <span className="rounded border bg-muted/40 px-2 py-1">
            {t('settings.coverageWindow', 'Window')}: {summary.window_start} - {summary.window_end}
          </span>
          <span className="rounded border bg-muted/40 px-2 py-1">
            {t('settings.coverageCoveredDays', 'Covered')}: {summary.covered_days}/{days}
          </span>
          <span className="rounded border bg-muted/40 px-2 py-1">
            {t('settings.coverageMissingDays', 'Missing')}: {summary.missing_days}
          </span>
          <span className="rounded border bg-muted/40 px-2 py-1">
            {t('settings.coverageMode', 'Mode')}: {coverageModeLabel}
          </span>
        </div>
      )}

      {/* Heatmap grid */}
      {coverageLoading ? (
        <div className="text-sm text-muted-foreground">{t('common.loading', 'Loading...')}</div>
      ) : (
        <div className="flex flex-wrap gap-[2px]">
          {coverage.map((item) => (
            <div
              key={item.date}
              className={`w-7 h-7 rounded-sm ${getCellColor(item.pct)} cursor-default
                hover:scale-125 hover:ring-2 hover:ring-foreground hover:z-10
                transition-transform relative group`}
            >
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1
                bg-popover text-popover-foreground text-xs rounded shadow-lg border
                opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-20">
                {item.date}: {item.pct}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
