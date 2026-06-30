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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CHART_COLORS } from './constants'
import { formatNumber, statusTitle } from './formatters'

interface ResultChartProps {
  rows: Record<string, unknown>[]
  numericKeys: string[]
  chartRows: Record<string, unknown>[]
  chartKeys: string[]
  displayedDatasetTitle: string
  loading: boolean
  result: any
}

export function ResultChart({
  rows,
  numericKeys,
  chartRows,
  chartKeys,
  displayedDatasetTitle,
  loading,
  result,
}: ResultChartProps) {
  return (
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
  )
}
