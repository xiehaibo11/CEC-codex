import { Badge } from '@/components/ui/badge'
import { FORWARD_PERIODS, KLINE_PERIOD_SECONDS, FORWARD_PERIOD_SECONDS } from './constants'

export function getCompatibleForwardPeriods(period: string) {
  const periodSeconds = KLINE_PERIOD_SECONDS[period]
  if (!periodSeconds) return FORWARD_PERIODS
  return FORWARD_PERIODS.filter((fp) => {
    const forwardSeconds = FORWARD_PERIOD_SECONDS[fp]
    return forwardSeconds >= periodSeconds && forwardSeconds % periodSeconds === 0
  })
}

// Translate backend error messages to Chinese
export function translateError(err: string, lang: string): string {
  if (lang !== 'zh') return err
  if (err.startsWith('Syntax error')) return err.replace('Syntax error', '语法错误')
  if (err.startsWith('Parse error')) return err.replace('Parse error', '解析错误')
  if (err.startsWith('Execution error')) return err.replace('Execution error', '执行错误')
  if (err.startsWith('Evaluation error')) return err.replace('Evaluation error', '求值错误')
  if (err === 'Expression is empty') return '表达式为空'
  if (err === 'Expression too long (max 500 chars)') return '表达式过长（最多500字符）'
  if (err === 'Expression returned None') return '表达式返回空值'
  if (err.startsWith('Insufficient K-line data')) return 'K线数据不足'
  if (err.startsWith('Not enough aligned data')) return '对齐数据不足，无法计算IC'
  if (err.includes("already exists")) return `因子名称 '${err.match(/'([^']+)'/)?.[1] || ''}' 已存在`
  return err
}

export function icBadge(ic: number | null | undefined) {
  if (ic == null) return <span className="text-muted-foreground">—</span>
  const abs = Math.abs(ic)
  const text = ic.toFixed(4)
  if (abs >= 0.05) return <Badge variant="default" className="bg-green-600 text-xs">{text}</Badge>
  if (abs >= 0.02) return <Badge variant="outline" className="text-yellow-500 text-xs">{text}</Badge>
  return <span className="text-muted-foreground text-xs">{text}</span>
}

export function wrBadge(wr: number | null | undefined) {
  if (wr == null) return <span className="text-muted-foreground">—</span>
  const pct = (wr * 100).toFixed(1) + '%'
  if (wr >= 0.55) return <span className="text-green-500 text-sm">{pct}</span>
  if (wr >= 0.45) return <span className="text-yellow-500 text-sm">{pct}</span>
  return <span className="text-red-500 text-sm">{pct}</span>
}
