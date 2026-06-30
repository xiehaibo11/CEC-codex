import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { endpointNeedsPlan } from './data-shaping'
import { categoryTitle, displayPlan, endpointTitle } from './formatters'
import type { CoinGlassCatalog, CoinGlassEndpoint } from './types'

interface CatalogPanelProps {
  catalog: CoinGlassCatalog | null
  endpoints: CoinGlassEndpoint[]
  categoryFilter: string
  subscriptionLevel: string | null
  loading: boolean
  onCategoryFilterChange: (value: string) => void
  onLoadEndpoint: (endpoint: CoinGlassEndpoint) => void
}

export function CatalogPanel({
  catalog,
  endpoints,
  categoryFilter,
  subscriptionLevel,
  loading,
  onCategoryFilterChange,
  onLoadEndpoint,
}: CatalogPanelProps) {
  return (
    <Card className="min-h-[420px] overflow-hidden">
      <CardHeader className="flex-row items-center justify-between p-4 pb-3">
        <CardTitle className="text-sm">接口目录</CardTitle>
        <Select value={categoryFilter} onValueChange={onCategoryFilterChange}>
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
            {endpoints.map((endpoint) => {
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
                    <Button variant="outline" size="sm" onClick={() => onLoadEndpoint(endpoint)} disabled={loading || !runnable}>
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
  )
}
