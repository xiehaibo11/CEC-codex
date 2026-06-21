import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Database,
  KeyRound,
  Lock,
  RefreshCw,
  Search,
  Table2,
  Trash2,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type PlanName = 'Hobbyist' | 'Startup' | 'Standard' | 'Professional' | 'Enterprise'

interface CoinGlassParam {
  name: string
  required: boolean
  type: string
  default?: string | number | null
  description?: string
}

interface CoinGlassEndpoint {
  id: string
  title: string
  category: string
  path: string
  method?: string
  summary: string
  params: CoinGlassParam[]
  required_params: string[]
  min_plan?: PlanName | null
  availability?: Record<string, boolean | null>
  interval_limit?: Record<string, string | null>
  doc_path: string
}

interface CoinGlassDataset {
  id: string
  label: string
  category: string
  path: string
  focus: string
  default_params: Record<string, string>
  endpoint?: CoinGlassEndpoint
}

interface CoinGlassCatalog {
  total: number
  categories: Array<{ name: string; count: number; startup_available: number; standard_plus: number }>
  endpoints: CoinGlassEndpoint[]
  datasets: CoinGlassDataset[]
}

interface CoinGlassSubscription {
  configured: boolean
  user_key_configured?: boolean
  server_key_configured?: boolean
  key_source?: 'user' | 'server' | 'none'
  key_masked?: string | null
  ok?: boolean
  level?: string | null
  expired?: boolean | null
  expire_time?: number | null
}

type ParamOverrides = Partial<Record<
  'symbol' | 'exchange' | 'exchange_list' | 'interval' | 'limit' | 'range' | 'min_liquidation_amount',
  string | number | null | undefined
>>

const PLAN_ORDER: PlanName[] = ['Hobbyist', 'Startup', 'Standard', 'Professional', 'Enterprise']
const INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '6h', '8h', '12h', '1d', '1w']
const EXCHANGES = ['Binance', 'OKX', 'Bybit', 'Bitget', 'Gate']
const PLAN_LABELS: Record<string, string> = {
  Hobbyist: '爱好者版',
  Startup: '创业版',
  Standard: '标准版',
  Professional: '专业版',
  Enterprise: '企业版',
}
const DATASET_LABELS: Record<string, string> = {
  pairs_markets: '交易对市场行情',
  price_history: '价格历史 K 线',
  aggregated_cvd: '聚合 CVD',
  pair_taker_volume: '交易对主动买卖量',
  coin_taker_volume: '币种主动买卖量',
  coin_netflow: '币种净流入',
  open_interest: '聚合持仓量',
  global_long_short: '全局账户多空比',
  funding_rate: '资金费率历史 K 线',
  pair_liquidation: '交易对爆仓历史',
  coin_liquidation: '币种爆仓历史',
  liquidation_orders: '爆仓订单',
  orderbook_depth: '订单簿买卖盘历史',
  fear_greed: '恐惧贪婪指数',
}
const CATEGORY_LABELS: Record<string, string> = {
  WebSocket: '实时订阅',
  '订单薄(L2)': '订单簿(L2)',
}
const CHART_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
]

const minutesByInterval: Record<string, number> = {
  '1m': 1,
  '3m': 3,
  '5m': 5,
  '15m': 15,
  '30m': 30,
  '1h': 60,
  '4h': 240,
  '6h': 360,
  '8h': 480,
  '12h': 720,
  '1d': 1440,
  '1w': 10080,
}

function planRank(plan?: string | null) {
  if (!plan) return -1
  const normalized = PLAN_ORDER.find((item) => item.toLowerCase() === plan.toLowerCase())
  return normalized ? PLAN_ORDER.indexOf(normalized) : -1
}

function displayPlan(plan?: string | null) {
  if (!plan) return '-'
  const normalized = PLAN_ORDER.find((item) => item.toLowerCase() === plan.toLowerCase())
  return normalized ? PLAN_LABELS[normalized] : plan
}

function keySourceLabel(source?: 'user' | 'server' | 'none') {
  if (source === 'user') return '个人'
  if (source === 'server') return '服务器'
  return '无'
}

function categoryTitle(category?: string | null) {
  if (!category) return '-'
  return CATEGORY_LABELS[category] || category
}

function datasetTitle(dataset?: CoinGlassDataset | null) {
  if (!dataset) return '-'
  return DATASET_LABELS[dataset.id] || dataset.label || '-'
}

function endpointTitle(endpoint?: CoinGlassEndpoint | null) {
  if (!endpoint) return '-'
  const fileName = endpoint.doc_path?.split('/').pop()?.replace(/\.md$/, '')
  return fileName || endpoint.title || endpoint.path
}

function statusTitle(loading: boolean, result: any) {
  if (loading) return '加载中'
  if (result?.ok) return '成功'
  if (result) return '已返回'
  return '-'
}

function displayError(message: string) {
  const normalized = message.toLowerCase()
  if (normalized.includes('api key') && normalized.includes('required')) return '请输入 CoinGlass API 密钥'
  if (normalized.includes('api key') && normalized.includes('not configured')) return '未配置 CoinGlass API 密钥'
  if (normalized.includes('failed to save')) return '保存 CoinGlass API 密钥失败'
  if (normalized.includes('failed to remove')) return '删除 CoinGlass API 密钥失败'
  if (normalized.includes('failed to load')) return '加载 CoinGlass 数据失败'
  if (normalized.includes('does not allow')) return '当前 CoinGlass 权限等级不支持该接口或参数'
  if (normalized.includes('forbidden') || normalized.includes('permission')) return '当前 CoinGlass 权限不足'
  if (normalized.includes('unauthorized') || normalized.includes('invalid')) return 'CoinGlass API 密钥无效或未授权'
  return message
}

function formatNumber(value: unknown) {
  const number = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(number)) return String(value ?? '-')
  const abs = Math.abs(number)
  if (abs >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`
  if (abs >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${(number / 1_000).toFixed(2)}K`
  if (abs > 0 && abs < 0.01) return number.toPrecision(3)
  return number.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
}

function formatTime(value: unknown) {
  const raw = Number(value)
  if (!Number.isFinite(raw)) return String(value ?? '-')
  const timestamp = raw < 10_000_000_000 ? raw * 1000 : raw
  return new Date(timestamp).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function toNumber(value: unknown) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function rowFromUnknown(item: unknown): Record<string, unknown> {
  if (Array.isArray(item)) {
    return item.reduce<Record<string, unknown>>((acc, value, index) => {
      acc[index === 0 ? 'time' : `value_${index}`] = value
      return acc
    }, {})
  }
  if (item && typeof item === 'object') return item as Record<string, unknown>
  return { value: item }
}

function extractRows(data: unknown): Record<string, unknown>[] {
  if (Array.isArray(data)) return data.map(rowFromUnknown)
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    const arrayKey = Object.keys(record).find((key) => Array.isArray(record[key]))
    if (arrayKey) return (record[arrayKey] as unknown[]).map(rowFromUnknown)
    return [record]
  }
  return []
}

function timeKeyFor(rows: Record<string, unknown>[]) {
  const keys = Object.keys(rows[0] || {})
  return keys.find((key) => ['time', 'timestamp', 'open_time', 'created_at', 'date'].includes(key)) || null
}

function numericKeysFor(rows: Record<string, unknown>[]) {
  const sample = rows.slice(0, 40)
  const keys = new Set<string>()
  sample.forEach((row) => {
    Object.entries(row).forEach(([key, value]) => {
      if (key === 'time' || key.endsWith('_time') || key === 'timestamp') return
      if (toNumber(value) !== null) keys.add(key)
    })
  })
  return Array.from(keys)
}

function preferredKeys(keys: string[], focus?: string) {
  const priority = [
    'close',
    'current_price',
    'volume_usd',
    'open_interest_usd',
    'open_interest',
    'long_volume_usd',
    'short_volume_usd',
    'agg_taker_buy_vol',
    'agg_taker_sell_vol',
    'cum_vol_delta',
    'long_liquidation_usd',
    'short_liquidation_usd',
    'aggregated_long_liquidation_usd',
    'aggregated_short_liquidation_usd',
    'long_short_ratio',
    'funding_rate',
    'value',
  ]
  const focusBoost = focus === 'ratio' ? ['long_short_ratio', 'long_account', 'short_account'] : []
  const ordered = [...focusBoost, ...priority]
    .map((key) => keys.find((candidate) => candidate === key || candidate.includes(key)))
    .filter(Boolean) as string[]
  const remaining = keys.filter((key) => !ordered.includes(key))
  return [...ordered, ...remaining].slice(0, 5)
}

function endpointNeedsPlan(endpoint?: CoinGlassEndpoint, currentPlan?: string | null) {
  if (!endpoint?.min_plan || !currentPlan) return false
  const current = planRank(currentPlan)
  const required = planRank(endpoint.min_plan)
  return current >= 0 && required >= 0 && current < required
}

function startupIntervalBlocked(endpoint: CoinGlassEndpoint | undefined, currentPlan: string | null | undefined, interval: string) {
  if (!endpoint || currentPlan?.toLowerCase() !== 'startup') return false
  const limit = endpoint.interval_limit?.Startup
  if (!limit || limit.includes('No Limit')) return false
  const required = limit.includes('>=30m') ? 30 : limit.includes('>=4h') ? 240 : 0
  return required > 0 && (minutesByInterval[interval] || required) < required
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload?.detail || response.statusText
    throw new Error(Array.isArray(detail) ? detail.join(', ') : detail)
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
  const chartRows = useMemo(() => {
    return rows.slice(-120).map((row, index) => {
      const next: Record<string, unknown> = {
        label: rowTimeKey ? formatTime(row[rowTimeKey]) : String(index + 1),
      }
      chartKeys.forEach((key) => {
        next[key] = toNumber(row[key])
      })
      return next
    })
  }, [rows, rowTimeKey, chartKeys])

  const columns = useMemo(() => {
    const keys = Object.keys(rows[0] || {})
    const priority = ['time', 'timestamp', 'exchange_name', 'symbol', 'instrument_id', ...chartKeys]
    return Array.from(new Set([...priority.filter((key) => keys.includes(key)), ...keys])).slice(0, 12)
  }, [rows, chartKeys])

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
      setSubscription({ configured: false })
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

      <Card className="flex-shrink-0">
        <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-primary" />
              <div className="text-sm font-medium">CoinGlass API 密钥</div>
              {subscription?.user_key_configured ? (
                <Badge variant="secondary">个人密钥</Badge>
              ) : subscription?.server_key_configured ? (
                <Badge variant="outline">服务器密钥</Badge>
              ) : (
                <Badge variant="destructive">未配置</Badge>
              )}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {subscription?.configured
                ? `正在使用${subscription.key_source === 'user' ? '个人密钥' : '服务器密钥'}${subscription.key_masked ? ` ${subscription.key_masked}` : ''}。当前等级：${subscription.level ? displayPlan(subscription.level) : '已配置'}`
                : '添加个人 CoinGlass 密钥后，将优先使用你的密钥查询付费接口。'}
            </div>
          </div>
          <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-[minmax(240px,420px)_auto_auto] lg:w-auto">
            <Input
              type="password"
              value={apiKeyInput}
              onChange={(event) => setApiKeyInput(event.target.value)}
              placeholder={subscription?.user_key_configured ? '输入新的密钥以替换当前个人密钥' : '粘贴你的 CoinGlass API 密钥'}
              autoComplete="off"
            />
            <Button onClick={saveApiKey} disabled={savingKey || !apiKeyInput.trim()}>
              <KeyRound className="h-4 w-4" />
              {savingKey ? '保存中' : '保存密钥'}
            </Button>
            <Button
              variant="outline"
              onClick={deleteApiKey}
              disabled={savingKey || !subscription?.user_key_configured}
            >
              <Trash2 className="h-4 w-4" />
              删除
            </Button>
          </div>
        </CardContent>
      </Card>

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
                    {minPlanBlocked ? <div>当前密钥等级 {displayPlan(subscriptionLevel)} 低于该接口要求的 {displayPlan(requiredPlan)}。</div> : null}
                    {intervalBlocked ? <div>当前密钥等级 {displayPlan(subscriptionLevel)} 查询该接口时要求周期不小于 30m。</div> : null}
                    {error ? <div>{displayError(error)}</div> : null}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {viewMode === 'catalog' ? (
            <Card className="min-h-[420px] overflow-hidden">
              <CardHeader className="flex-row items-center justify-between p-4 pb-3">
                <CardTitle className="text-sm">接口目录</CardTitle>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部分类</SelectItem>
                    {(catalog?.categories || []).map((category) => (
                      <SelectItem key={category.name} value={category.name}>{categoryTitle(category.name)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardHeader>
              <CardContent className="max-h-[calc(100vh-18rem)] min-h-[360px] overflow-auto p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-36">分类</TableHead>
                      <TableHead>接口</TableHead>
                      <TableHead className="w-20">方式</TableHead>
                      <TableHead className="w-28">等级</TableHead>
                      <TableHead className="w-52">必填参数</TableHead>
                      <TableHead className="w-24 text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredEndpoints.map((endpoint) => {
                      const runnable = (endpoint.method || 'GET') === 'GET' && endpoint.path.startsWith('/api/')
                      return (
                        <TableRow key={endpoint.id}>
                          <TableCell className="text-muted-foreground">{categoryTitle(endpoint.category)}</TableCell>
                          <TableCell>
                            <div className="font-medium">{endpointTitle(endpoint)}</div>
                            <div className="mt-1 font-mono text-[11px] text-muted-foreground">{endpoint.path}</div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{endpoint.method || 'GET'}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={endpointNeedsPlan(endpoint, subscriptionLevel) ? 'destructive' : 'secondary'}>
                              {endpoint.min_plan ? displayPlan(endpoint.min_plan) : '不限'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {endpoint.required_params.length ? endpoint.required_params.join(', ') : '-'}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="outline" size="sm" onClick={() => loadEndpoint(endpoint)} disabled={loading || !runnable}>
                              加载
                            </Button>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : (
            <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
              <div className="flex min-h-0 flex-col gap-4">
                <div className="grid flex-shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
                  <Card>
                    <CardContent className="p-4">
                      <div className="text-[11px] font-medium text-muted-foreground">数据行数</div>
                      <div className="mt-1 text-xl font-semibold">{rows.length}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="text-[11px] font-medium text-muted-foreground">数值字段</div>
                      <div className="mt-1 text-xl font-semibold">{numericKeys.length}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="text-[11px] font-medium text-muted-foreground">数据集</div>
                      <div className="mt-1 truncate text-sm font-semibold">{displayedDatasetTitle}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="text-[11px] font-medium text-muted-foreground">状态</div>
                      <div className="mt-1 truncate text-sm font-semibold">{statusTitle(loading, result)}</div>
                    </CardContent>
                  </Card>
                </div>

                <Card className="h-[clamp(260px,34vh,380px)] overflow-hidden">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle className="text-sm">时间序列</CardTitle>
                  </CardHeader>
                  <CardContent className="h-[calc(100%-3.25rem)] p-4 pt-0">
                    {chartRows.length && chartKeys.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartRows}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={28} />
                          <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} width={70} />
                          <RechartsTooltip formatter={(value) => formatNumber(value)} labelStyle={{ color: 'hsl(var(--foreground))' }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          {chartKeys.map((key, index) => (
                            <Line
                              key={key}
                              type="monotone"
                              dataKey={key}
                              stroke={CHART_COLORS[index % CHART_COLORS.length]}
                              dot={false}
                              strokeWidth={2}
                              connectNulls
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                        {loading ? '正在加载 CoinGlass 数据...' : '暂无可绘制的数据'}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="h-[clamp(220px,28vh,320px)] overflow-hidden">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle className="text-sm">数据分布</CardTitle>
                  </CardHeader>
                  <CardContent className="h-[calc(100%-3.25rem)] p-4 pt-0">
                    {chartRows.length && chartKeys.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartRows.slice(-50)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                          <XAxis dataKey="label" tick={{ fontSize: 10 }} minTickGap={32} />
                          <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} width={70} />
                          <RechartsTooltip formatter={(value) => formatNumber(value)} labelStyle={{ color: 'hsl(var(--foreground))' }} />
                          {chartKeys.slice(0, 3).map((key, index) => (
                            <Bar key={key} dataKey={key} fill={CHART_COLORS[index % CHART_COLORS.length]} radius={[3, 3, 0, 0]} />
                          ))}
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">暂无分布数据</div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="flex min-h-0 flex-col gap-4">
                <Card className="max-h-[280px] min-h-[180px] overflow-hidden">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle className="text-sm">最新数值</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 overflow-auto p-4 pt-0">
                    {chartKeys.length ? chartKeys.map((key, index) => {
                      const latest = rows[rows.length - 1]?.[key]
                      return (
                        <div key={key} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }} />
                            <span className="truncate text-xs text-muted-foreground">{key}</span>
                          </div>
                          <span className="font-mono text-xs font-semibold">{formatNumber(latest)}</span>
                        </div>
                      )
                    }) : (
                      <div className="text-sm text-muted-foreground">暂无数值字段</div>
                    )}
                  </CardContent>
                </Card>

                <Card className="min-h-[360px] flex-1 overflow-hidden">
                  <CardHeader className="p-4 pb-2">
                    <CardTitle className="text-sm">表格预览</CardTitle>
                  </CardHeader>
                  <CardContent className="max-h-[calc(100vh-33rem)] min-h-[300px] overflow-auto p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {columns.map((column) => <TableHead key={column}>{column}</TableHead>)}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rows.slice(-80).map((row, rowIndex) => (
                          <TableRow key={rowIndex}>
                            {columns.map((column) => {
                              const value = row[column]
                              return (
                                <TableCell key={column} className="max-w-44 truncate font-mono">
                                  {column === rowTimeKey ? formatTime(value) : typeof value === 'object' ? JSON.stringify(value) : formatNumber(value)}
                                </TableCell>
                              )
                            })}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {!rows.length ? <div className="p-4 text-sm text-muted-foreground">暂无加载的数据行</div> : null}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
