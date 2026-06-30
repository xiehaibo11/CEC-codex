import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CHART_COLORS } from './constants'
import { formatNumber, formatTime } from './formatters'

interface ResultTableProps {
  rows: Record<string, unknown>[]
  chartKeys: string[]
  columns: string[]
  rowTimeKey: string | null
}

export function ResultTable({ rows, chartKeys, columns, rowTimeKey }: ResultTableProps) {
  return (
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
  )
}
