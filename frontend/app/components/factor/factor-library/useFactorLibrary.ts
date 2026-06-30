import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { apiRequest, getHyperliquidWatchlist } from '@/lib/api'
import { FUNC_CATEGORIES, FUNC_TEMPLATES } from './constants'
import { getCompatibleForwardPeriods, translateError } from './helpers'
import type { AnalysisFactor, DialogStep, FactorLibraryData } from './types'

export function useFactorLibrary() {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language?.startsWith('zh')

  const exchange = 'hyperliquid'
  const [symbol, setSymbol] = useState('')
  const [symbols, setSymbols] = useState<string[]>([])
  const [period, setPeriod] = useState('1h')
  const [forwardPeriod, setForwardPeriod] = useState('4h')
  const [computeAllPeriods, setComputeAllPeriods] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [library, setLibrary] = useState<FactorLibraryData>()
  const [values, setValues] = useState<any[]>([])
  const [effectiveness, setEffectiveness] = useState<any[]>([])
  const [lastComputeTime, setLastComputeTime] = useState<number | null>(null)
  const [computing, setComputing] = useState(false)
  const [computeDialogOpen, setComputeDialogOpen] = useState(false)
  const [computeResult, setComputeResult] = useState<any>(null)
  const [computeEstimate, setComputeEstimate] = useState<any>(null)
  const [computeProgress, setComputeProgress] = useState<any>(null)
  const [dialogStep, setDialogStep] = useState<DialogStep>('confirm')
  const [countdown, setCountdown] = useState('')
  const [loading, setLoading] = useState(true)
  const [sortCol, setSortCol] = useState<string>('icir')
  const [sortDesc, setSortDesc] = useState(true)

  // Custom Factor Lab state
  const [labDialogOpen, setLabDialogOpen] = useState(false)
  const [editingFactorId, setEditingFactorId] = useState<number | null>(null)
  const [expression, setExpression] = useState('')
  const [evalResult, setEvalResult] = useState<any>(null)
  const [evalError, setEvalError] = useState('')
  const [evaluating, setEvaluating] = useState(false)
  const [funcCatTab, setFuncCatTab] = useState(FUNC_CATEGORIES[0].key)
  const [saveName, setSaveName] = useState('')
  const [saveDesc, setSaveDesc] = useState('')
  const [saving, setSaving] = useState(false)
  const [customFactors, setCustomFactors] = useState<any[]>([])

  // Factor Analysis Dialog state
  const [analysisOpen, setAnalysisOpen] = useState(false)
  const [analysisFactor, setAnalysisFactor] = useState<AnalysisFactor>({ name: '', displayName: '' })

  useEffect(() => {
    apiRequest('/factors/library').then(r => r.json()).then(setLibrary).catch(() => {})
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getHyperliquidWatchlist()
        const syms = data.symbols || []
        setSymbols(syms)
        if (syms.length > 0 && !syms.includes(symbol)) setSymbol(syms[0])
      } catch { setSymbols([]) }
    }
    load()
  }, [exchange])

  const loadData = useCallback(async () => {
    if (!symbol) return
    setLoading(true)
    try {
      const [valRes, effRes, statusRes] = await Promise.all([
        apiRequest(`/factors/values?symbol=${symbol}&period=${period}&exchange=${exchange}`).then(r => r.json()).catch(() => ({ values: [] })),
        apiRequest(`/factors/effectiveness?symbol=${symbol}&period=${period}&forward_period=${forwardPeriod}&exchange=${exchange}`).then(r => r.json()).catch(() => ({ items: [] })),
        apiRequest('/factors/status').then(r => r.json()).catch(() => null),
      ])
      setValues(valRes.values || [])
      setEffectiveness(effRes.items || [])
      if (statusRes?.last_compute_time) {
        setLastComputeTime(statusRes.last_compute_time[exchange] || null)
      }
    } finally { setLoading(false) }
  }, [symbol, period, exchange, forwardPeriod])

  useEffect(() => { loadData() }, [loadData])

  const compatibleForwardPeriods = useMemo(() => getCompatibleForwardPeriods(period), [period])

  useEffect(() => {
    if (compatibleForwardPeriods.length > 0 && !compatibleForwardPeriods.includes(forwardPeriod)) {
      setForwardPeriod(compatibleForwardPeriods[0])
    }
  }, [compatibleForwardPeriods, forwardPeriod])

  const loadCustomFactors = useCallback(async () => {
    try {
      const res = await apiRequest('/factors/custom').then(r => r.json())
      setCustomFactors(res.items || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadCustomFactors() }, [loadCustomFactors])

  // Custom Factor Lab handlers
  const openLabDialog = (factorId?: number) => {
    if (factorId) {
      const cf = customFactors.find(f => f.id === factorId)
      if (cf) {
        setEditingFactorId(factorId)
        setExpression(cf.expression)
        setSaveName(cf.name)
        setSaveDesc(cf.description || '')
      }
    } else {
      setEditingFactorId(null)
      setExpression('')
      setSaveName('')
      setSaveDesc('')
    }
    setEvalResult(null)
    setEvalError('')
    setLabDialogOpen(true)
  }

  const handleEvaluate = async () => {
    if (!expression.trim() || !symbol) return
    setEvaluating(true)
    setEvalResult(null)
    setEvalError('')
    try {
      const res = await apiRequest('/factors/evaluate', {
        method: 'POST',
        body: JSON.stringify({ expression: expression.trim(), symbol, exchange, period }),
      }).then(r => r.json())
      if (res.status === 'error') setEvalError(translateError(res.error, isZh ? 'zh' : 'en'))
      else setEvalResult(res)
    } catch (e: any) {
      setEvalError(e.message || 'Unknown error')
    } finally {
      setEvaluating(false)
    }
  }

  const handleSaveCustom = async () => {
    if (!saveName.trim() || !expression.trim()) return
    setSaving(true)
    setEvalError('')
    try {
      if (editingFactorId) {
        await apiRequest(`/factors/custom/${editingFactorId}`, { method: 'DELETE' })
      }
      const res = await apiRequest('/factors/custom', {
        method: 'POST',
        body: JSON.stringify({
          name: saveName.trim(), expression: expression.trim(),
          description: saveDesc.trim(), category: 'custom', source: 'manual',
        }),
      }).then(r => r.json())
      if (res.status === 'ok') {
        setLabDialogOpen(false)
        await loadCustomFactors()
      } else {
        setEvalError(translateError(res.error || 'Save failed', isZh ? 'zh' : 'en'))
      }
    } catch (e: any) {
      setEvalError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCustom = async (id: number) => {
    if (!confirm(t('factors.deleteConfirm'))) return
    try {
      await apiRequest(`/factors/custom/${id}`, { method: 'DELETE' })
      await loadCustomFactors()
    } catch { /* ignore */ }
  }

  const insertFunction = (funcName: string) => {
    const template = FUNC_TEMPLATES[funcName] || funcName + '('
    setExpression(prev => {
      if (!prev.trim()) return template
      return prev + ' ' + template
    })
  }

  // Compute handlers (unchanged)
  useEffect(() => {
    if (!lastComputeTime) { setCountdown(''); return }
    const update = () => {
      const nextTs = lastComputeTime + 3600
      const remaining = nextTs - Date.now() / 1000
      if (remaining <= 0) { setCountdown(''); return }
      const m = Math.floor(remaining / 60)
      const s = Math.floor(remaining % 60)
      setCountdown(`${m}:${s.toString().padStart(2, '0')}`)
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [lastComputeTime])

  const loadComputeEstimate = useCallback(async (allPeriods: boolean = computeAllPeriods) => {
    const params = new URLSearchParams({ exchange, period })
    if (allPeriods) params.set('all_periods', 'true')
    const est = await apiRequest(`/factors/compute/estimate?${params.toString()}`).then(r => r.json())
    setComputeEstimate(est)
  }, [exchange, period, computeAllPeriods])

  const handleComputeClick = async () => {
    setComputeDialogOpen(true)
    setDialogStep('confirm')
    setComputeResult(null)
    setComputeProgress(null)
    setComputeEstimate(null)
    try {
      await loadComputeEstimate(computeAllPeriods)
    } catch { /* ignore */ }
  }

  const handleComputeAllPeriodsChange = async (checked: boolean | 'indeterminate') => {
    const next = checked === true
    setComputeAllPeriods(next)
    setComputeEstimate(null)
    try {
      await loadComputeEstimate(next)
    } catch { /* ignore */ }
  }

  const handleComputeConfirm = async () => {
    setDialogStep('progress')
    setComputing(true)
    setComputeProgress(null)
    try {
      const startRes = await apiRequest('/factors/compute', {
        method: 'POST', body: JSON.stringify({ exchange, period, all_periods: computeAllPeriods }),
      }).then(r => r.json())
      if (startRes.status === 'already_running') {
        setComputeResult({ error: t('factors.alreadyRunning') })
        setDialogStep('done'); setComputing(false); return
      }
      const poll = setInterval(async () => {
        try {
          const prog = await apiRequest('/factors/compute/progress').then(r => r.json())
          setComputeProgress(prog)
          if (prog.status === 'done' || prog.status === 'error' || prog.status === 'idle') {
            clearInterval(poll); setComputeResult(prog)
            setDialogStep('done'); setComputing(false); await loadData()
          }
        } catch { /* ignore */ }
      }, 1500)
    } catch (e: any) {
      setComputeResult({ error: e.message || 'Unknown error' })
      setDialogStep('done'); setComputing(false)
    }
  }

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDesc(!sortDesc)
    else { setSortCol(col); setSortDesc(true) }
  }

  // Merge library (builtin + custom) with values and effectiveness data
  const mergedRows = useMemo(() => {
    if (!library) return []
    const valMap = new Map(values.map(v => [v.factor_name, v]))
    const effMap = new Map(effectiveness.map(e => [e.factor_name, e]))

    const rows = library.factors
      .filter((f: any) => categoryFilter === 'all' || f.category === categoryFilter)
      .map((f: any) => {
        const v = valMap.get(f.name)
        const e = effMap.get(f.name)
        const isCustom = f.source !== 'builtin' && f.source !== 'builtin_expression'
        return {
          ...f, value: v?.value ?? null, timestamp: v?.timestamp, ...e,
          _isCustom: isCustom, _customId: f.custom_id ?? null, _expression: f.expression ?? null,
        }
      })

    if (['ic_mean', 'icir', 'win_rate'].includes(sortCol)) {
      rows.sort((a: any, b: any) => {
        const av = Math.abs(a[sortCol] ?? 0)
        const bv = Math.abs(b[sortCol] ?? 0)
        return sortDesc ? bv - av : av - bv
      })
    }
    return rows
  }, [library, values, effectiveness, categoryFilter, sortCol, sortDesc])

  const categories = library?.categories || []
  const catLabels = library?.category_labels || {}
  const getCatLabel = (cat: string) => {
    if (cat === 'custom') return t('factors.customTag')
    const l = catLabels[cat]
    return l ? (isZh ? l.zh : l.en) : cat
  }
  const getFactorDesc = (f: any) => isZh ? (f.description_zh || f.description) : f.description
  const formatLastUpdate = () => {
    if (!lastComputeTime) return '--'
    return new Date(lastComputeTime * 1000).toLocaleString()
  }

  return {
    t, isZh, exchange,
    symbol, setSymbol, symbols,
    period, setPeriod,
    forwardPeriod, setForwardPeriod,
    computeAllPeriods,
    categoryFilter, setCategoryFilter,
    library,
    computing,
    computeDialogOpen, setComputeDialogOpen,
    computeResult, computeEstimate, computeProgress,
    dialogStep,
    countdown,
    loading,
    sortCol,
    labDialogOpen, setLabDialogOpen,
    expression, setExpression,
    evalResult, evalError, evaluating,
    funcCatTab, setFuncCatTab,
    saveName, setSaveName,
    saveDesc, setSaveDesc,
    saving,
    customFactors,
    analysisOpen, setAnalysisOpen,
    analysisFactor, setAnalysisFactor,
    compatibleForwardPeriods,
    openLabDialog,
    handleEvaluate,
    handleSaveCustom,
    handleDeleteCustom,
    insertFunction,
    handleComputeClick,
    handleComputeAllPeriodsChange,
    handleComputeConfirm,
    toggleSort,
    mergedRows,
    categories,
    getCatLabel,
    getFactorDesc,
    formatLastUpdate,
  }
}

export type FactorLibraryController = ReturnType<typeof useFactorLibrary>
