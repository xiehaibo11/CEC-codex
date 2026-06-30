import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Database,
  Lock,
  RefreshCw,
  Search,
  Table2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiRequest } from '@/lib/api'
import { CatalogPanel } from './coinglass-view/CatalogPanel'
import { ResultChart } from './coinglass-view/ResultChart'
import { ResultTable } from './coinglass-view/ResultTable'
import { SubscriptionKeyPanel } from './coinglass-view/SubscriptionKeyPanel'
import { EXCHANGES, INTERVALS } from './coinglass-view/constants'
import {
  chartRowsFor,
  columnsFor,
  endpointNeedsPlan,
  extractRows,
  numericKeysFor,
  preferredKeys,
  startupIntervalBlocked,
  timeKeyFor,
} from './coinglass-view/data-shaping'
import {
  categoryTitle,
  datasetTitle,
  displayError,
  displayPlan,
  endpointTitle,
  formatTime,
  keySourceLabel,
} from './coinglass-view/formatters'
import type {
  CoinGlassCatalog,
  CoinGlassEndpoint,
  CoinGlassSubscription,
  ParamOverrides,
} from './coinglass-view/types'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const endpoint = url.startsWith('/api/') ? url.slice(4) : url
  const response = await apiRequest(endpoint, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload?.detail || response.statusText
    throw new Error(Array.isArray(detail) ? detail.join(', ') : detail)
  }
  if (payload && typeof payload === 'object' && 'ok' in payload && payload.ok === false) {
    const detail = payload.reason || payload.msg || payload.payload?.msg || payload.payload?.message || 'CoinGlass request failed'
    throw new Error(displayError(detail))
  }
  return payload as T
}

export default function CoinGlassView() {
  const [catalog, setCatalog] = useState<CoinGlassCatalog | null>(null)
  const [subscription, setSubscription] = useState<CoinGlassSubscription | null>(null)
  const [selectedDatasetId, setSelectedDatasetId] = useState('pairs_markets')
  const [activeEndpoint, setActiveEndpoint] = useState<CoinGlassEndpoint | null>(null)
  const [viewMode, setViewMode] = useState<'data' | 'catalog'>('data')
  const [symbol, setSymbol] = useState('BTC')
  const [exchange, setExchange] = useState('Binance')
  const [exchangeList, setExchangeList] = useState('Binance')
  const [interval, setInterval] = useState('30m')
  const [limit, setLimit] = useState('120')
  const [range, setRange] = useState('1')
  const [minLiquidationAmount, setMinLiquidationAmount] = useState('10000')
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [savingKey, setSavingKey] = useState(false)
  const [catalogSearch, setCatalogSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const requestSeq = useRef(0)

  const datasets = catalog?.datasets || []
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) || datasets[0]
  const activeMeta = activeEndpoint || selectedDataset?.endpoint
  const rows = useMemo(() => extractRows(result?.data), [result])
  const rowTimeKey = useMemo(() => timeKeyFor(rows), [rows])
  const numericKeys = useMemo(() => numericKeysFor(rows), [rows])
  const chartKeys = useMemo(
    () => preferredKeys(numericKeys, selectedDataset?.focus),
    [numericKeys, selectedDataset?.focus],
  )
  const chartRows = useMemo(() => chartRowsFor(rows, rowTimeKey, chartKeys), [rows, rowTimeKey, chartKeys])
  const columns = useMemo(() => columnsFor(rows, chartKeys), [rows, chartKeys])

  const filteredEndpoints = useMemo(() => {
    const search = catalogSearch.trim().toLowerCase()
    return (catalog?.endpoints || []).filter((endpoint) => {
      const matchesCategory = categoryFilter === 'all' || endpoint.category === categoryFilter
      const matchesSearch = !search || [
        endpoint.title,
        endpointTitle(endpoint),
        endpoint.summary,
        endpoint.path,
        endpoint.category,
        categoryTitle(endpoint.category),
        endpoint.doc_path,
      ].some((value) => value?.toLowerCase().includes(search))
      return matchesCategory && matchesSearch
    })
  }, [catalog?.endpoints, catalogSearch, categoryFilter])
  const filteredDatasets = useMemo(() => {
    const search = catalogSearch.trim().toLowerCase()
    if (!search) return datasets
    return datasets.filter((dataset) => [
      dataset.label,
      datasetTitle(dataset),
      dataset.category,
      categoryTitle(dataset.category),
      dataset.path,
      dataset.endpoint?.summary,
    ].some((value) => value?.toLowerCase().includes(search)))
  }, [datasets, catalogSearch])

  const subscriptionLevel = subscription?.level || null
  const minPlanBlocked = endpointNeedsPlan(activeMeta, subscriptionLevel)
  const intervalBlocked = startupIntervalBlocked(activeMeta, subscriptionLevel, interval)
  const requiredPlan = activeMeta?.min_plan || null

  const buildParams = (overrides: ParamOverrides = {}) => {
    const valueFor = (key: keyof ParamOverrides, fallback: string) => {
      const value = overrides[key]
      return value === undefined || value === null ? fallback : String(value)
    }
    const params = new URLSearchParams()
    params.set('symbol', valueFor('symbol', symbol.trim()).trim())
    params.set('exchange', valueFor('exchange', exchange))
    params.set('exchange_list', valueFor('exchange_list', exchangeList.trim()).trim())
    params.set('interval', valueFor('interval', interval))
    params.set('limit', valueFor('limit', limit))
    params.set('range', valueFor('range', range))
    params.set('min_liquidation_amount', valueFor('min_liquidation_amount', minLiquidationAmount))
    return params
  }

  const applyDefaults = (defaults: Record<string, string> = {}) => {
    if (defaults.symbol) setSymbol(defaults.symbol)
    if (defaults.exchange) setExchange(defaults.exchange)
    if (defaults.exchange_list) setExchangeList(defaults.exchange_list)
    if (defaults.interval) setInterval(defaults.interval)
    if (defaults.limit) setLimit(String(defaults.limit))
    if (defaults.range) setRange(String(defaults.range))
    if (defaults.min_liquidation_amount) setMinLiquidationAmount(String(defaults.min_liquidation_amount))
  }

  const loadCatalog = async () => {
    const payload = await fetchJson<CoinGlassCatalog>('/api/coinglass/catalog')
    setCatalog(payload)
    if (payload.datasets.length && !payload.datasets.some((dataset) => dataset.id === selectedDatasetId)) {
      setSelectedDatasetId(payload.datasets[0].id)
    }
  }

  const loadSubscription = async () => {
    try {
      setSubscription(await fetchJson<CoinGlassSubscription>('/api/coinglass/subscription'))
    } catch (err) {
      setSubscription({
        configured: false,
        ok: false,
        status: 'invalid_key',
        reason: err instanceof Error ? err.message : 'CoinGlass API key is not available',
      })
    }
  }

  const saveApiKey = async () => {
    const apiKey = apiKeyInput.trim()
    if (!apiKey) {
      setError('请输入 CoinGlass API 密钥')
      return
    }

    setSavingKey(true)
    setError(null)
    try {
      const payload = await fetchJson<CoinGlassSubscription>('/api/coinglass/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      })
      setSubscription(payload)
      setApiKeyInput('')
      if (selectedDataset) await loadDataset(selectedDataset.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存 CoinGlass API 密钥失败')
    } finally {
      setSavingKey(false)
    }
  }

  const deleteApiKey = async () => {
    setSavingKey(true)
    setError(null)
    try {
      const payload = await fetchJson<CoinGlassSubscription>('/api/coinglass/key', { method: 'DELETE' })
      setSubscription(payload)
      if (selectedDataset) await loadDataset(selectedDataset.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除 CoinGlass API 密钥失败')
    } finally {
      setSavingKey(false)
    }
  }

  const loadDataset = async (datasetId = selectedDatasetId, paramOverrides: ParamOverrides = {}) => {
    const requestId = requestSeq.current + 1
    requestSeq.current = requestId
    setLoading(true)
    setError(null)
    setActiveEndpoint(null)
    setResult(null)
    try {
      const payload = await fetchJson<any>(`/api/coinglass/dataset/${datasetId}?${buildParams(paramOverrides).toString()}`)
      if (requestId !== requestSeq.current) return
      setResult(payload)
      setViewMode('data')
    } catch (err) {
      if (requestId !== requestSeq.current) return
      setError(err instanceof Error ? err.message : '加载 CoinGlass 数据失败')
      setResult(null)
    } finally {
      if (requestId === requestSeq.current) setLoading(false)
    }
  }

  const loadEndpoint = async (endpoint: CoinGlassEndpoint) => {
    const requestId = requestSeq.current + 1
    requestSeq.current = requestId
    setLoading(true)
    setError(null)
    setActiveEndpoint(endpoint)
    setResult(null)
    try {
      const payload = await fetchJson<any>(`/api/coinglass/endpoint/${endpoint.id}?${buildParams().toString()}`)
      if (requestId !== requestSeq.current) return
      setResult(payload)
      setViewMode('data')
    } catch (err) {
      if (requestId !== requestSeq.current) return
      setError(err instanceof Error ? err.message : '加载 CoinGlass 接口失败')
      setResult(null)
    } finally {
      if (requestId === requestSeq.current) setLoading(false)
    }
  }

  useEffect(() => {
    loadCatalog().catch((err) => setError(err instanceof Error ? err.message : '加载 CoinGlass 目录失败'))
    loadSubscription()
  }, [])

  useEffect(() => {
    if (!selectedDataset) return
    applyDefaults(selectedDataset.default_params)
  }, [selectedDatasetId, catalog?.datasets.length])

  useEffect(() => {
    if (catalog && selectedDataset && !result && !loading) {
      loadDataset(selectedDataset.id)
    }
  }, [catalog?.total, selectedDataset?.id])

  const displayedDatasetTitle = result?.endpoint
    ? endpointTitle(result.endpoint)
    : result?.dataset
      ? datasetTitle(result.dataset)
      : activeEndpoint
        ? endpointTitle(activeEndpoint)
        : datasetTitle(selectedDataset)

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto overflow-x-hidden pb-16 pr-1 md:pb-0">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            <h1 className="text-xl font-semibold">CoinGlass</h1>
            {subscription?.configured ? (
              <Badge variant={subscription?.expired ? 'destructive' : 'secondary'}>
                {subscription.level ? displayPlan(subscription.level) : '已配置'}
              </Badge>
            ) : subscription?.reason ? (
              <Badge variant="destructive">密钥无效</Badge>
            ) : (
              <Badge variant="outline">未配置</Badge>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{catalog?.total || 0} 个接口</span>
            {subscription?.key_source ? <span>密钥：{keySourceLabel(subscription.key_source)}{subscription.key_masked ? `（${subscription.key_masked}）` : ''}</span> : null}
            {subscription?.expire_time ? <span>到期：{new Date(subscription.expire_time).toLocaleDateString('zh-CN')}</span> : null}
            {result?.fetched_at ? <span>更新：{formatTime(result.fetched_at)}</span> : null}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={viewMode === 'data' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('data')}
          >
            <BarChart3 className="h-4 w-4" />
            数据
          </Button>
          <Button
            variant={viewMode === 'catalog' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('catalog')}
          >
            <Table2 className="h-4 w-4" />
            接口目录
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => (activeEndpoint ? loadEndpoint(activeEndpoint) : loadDataset())}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
      </div>

      <SubscriptionKeyPanel
        subscription={subscription}
        apiKeyInput={apiKeyInput}
        savingKey={savingKey}
        onApiKeyInputChange={setApiKeyInput}
        onSave={saveApiKey}
        onDelete={deleteApiKey}
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[290px_minmax(0,1fr)]">
        <Card className="min-h-[260px] overflow-hidden xl:sticky xl:top-0 xl:max-h-[calc(100vh-13rem)]">
          <CardHeader className="p-4 pb-3">
            <CardTitle className="text-sm">核心数据</CardTitle>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-3.5rem)] flex-col gap-3 overflow-hidden p-4 pt-0">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                value={catalogSearch}
                onChange={(event) => setCatalogSearch(event.target.value)}
                placeholder="搜索接口或数据集"
              />
            </div>
            <div className="space-y-1 overflow-y-auto pr-1">
              {filteredDatasets.map((dataset) => {
                const active = !activeEndpoint && selectedDatasetId === dataset.id
                const locked = endpointNeedsPlan(dataset.endpoint, subscriptionLevel)
                return (
                  <button
                    key={dataset.id}
                    className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                      active
                        ? 'border-primary/40 bg-primary/10 text-foreground'
                        : 'border-border bg-background hover:border-primary/30 hover:bg-muted/60'
                    }`}
                    onClick={() => {
                      setSelectedDatasetId(dataset.id)
                      setActiveEndpoint(null)
                      applyDefaults(dataset.default_params)
                      loadDataset(dataset.id, dataset.default_params)
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium">{datasetTitle(dataset)}</span>
                      {locked ? <Lock className="h-3.5 w-3.5 text-muted-foreground" /> : <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                      <span className="truncate">{categoryTitle(dataset.category)}</span>
                      <span className="truncate font-mono">{dataset.path.split('/').slice(-2).join('/')}</span>
                    </div>
                  </button>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <div className="flex min-h-0 flex-col gap-4">
          <Card className="flex-shrink-0">
            <CardContent className="p-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">交易对/币种</label>
                  <Input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">交易所</label>
                  <Select value={exchange} onValueChange={setExchange}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {EXCHANGES.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">交易所列表</label>
                  <Input value={exchangeList} onChange={(event) => setExchangeList(event.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">周期</label>
                  <Select value={interval} onValueChange={setInterval}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {INTERVALS.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">条数</label>
                  <Input type="number" min={1} max={1000} value={limit} onChange={(event) => setLimit(event.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">深度范围</label>
                  <Input value={range} onChange={(event) => setRange(event.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-muted-foreground">最小爆仓额</label>
                  <Input value={minLiquidationAmount} onChange={(event) => setMinLiquidationAmount(event.target.value)} />
                </div>
                <div className="flex items-end">
                  <Button className="w-full" disabled={loading} onClick={() => (activeEndpoint ? loadEndpoint(activeEndpoint) : loadDataset())}>
                    <Activity className="h-4 w-4" />
                    加载
                  </Button>
                </div>
              </div>

              {(error || minPlanBlocked || intervalBlocked || !subscription?.configured) && (
                <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <div className="space-y-1">
                    {!subscription?.configured ? <div>未配置 CoinGlass 密钥。可以在上方添加个人密钥。</div> : null}
                    {subscription?.reason ? <div>{displayError(subscription.reason)}</div> : null}
                    {minPlanBlocked ? <div>当前密钥等级 {displayPlan(subscriptionLevel)} 低于该接口要求的 {displayPlan(requiredPlan)}。</div> : null}
                    {intervalBlocked ? <div>当前密钥等级 {displayPlan(subscriptionLevel)} 查询该接口时要求周期不小于 30m。</div> : null}
                    {error ? <div>{displayError(error)}</div> : null}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {viewMode === 'catalog' ? (
            <CatalogPanel
              catalog={catalog}
              endpoints={filteredEndpoints}
              categoryFilter={categoryFilter}
              subscriptionLevel={subscriptionLevel}
              loading={loading}
              onCategoryFilterChange={setCategoryFilter}
              onLoadEndpoint={loadEndpoint}
            />
          ) : (
            <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
              <ResultChart
                rows={rows}
                numericKeys={numericKeys}
                chartRows={chartRows}
                chartKeys={chartKeys}
                displayedDatasetTitle={displayedDatasetTitle}
                loading={loading}
                result={result}
              />
              <ResultTable
                rows={rows}
                chartKeys={chartKeys}
                columns={columns}
                rowTimeKey={rowTimeKey}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
