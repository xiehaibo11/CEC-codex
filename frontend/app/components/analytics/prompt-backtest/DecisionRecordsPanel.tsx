import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { RefreshCw, ChevronRight, Loader2 } from 'lucide-react'
import { formatTime, getOperationColor } from './formatters'
import type { ModelChatEntry } from './types'

interface DecisionRecordsPanelProps {
  filteredRecords: ModelChatEntry[]
  selectedIds: Set<number>
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  loadingSnapshots: boolean
  filterOperation: string
  setFilterOperation: (value: string) => void
  filterSymbol: string
  setFilterSymbol: (value: string) => void
  availableSymbols: string[]
  fetchRecords: () => void
  loadMore: () => void
  toggleSelect: (id: number) => void
  toggleSelectAll: () => void
  loadToWorkspace: () => void
}

export default function DecisionRecordsPanel({
  filteredRecords,
  selectedIds,
  loading,
  loadingMore,
  hasMore,
  loadingSnapshots,
  filterOperation,
  setFilterOperation,
  filterSymbol,
  setFilterSymbol,
  availableSymbols,
  fetchRecords,
  loadMore,
  toggleSelect,
  toggleSelectAll,
  loadToWorkspace,
}: DecisionRecordsPanelProps) {
  const { t } = useTranslation()

  return (
    <Card className="flex min-h-[360px] flex-col xl:min-h-0">
      <CardHeader className="pb-2 shrink-0">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="shrink-0 text-base">
            {t('promptBacktest.decisionRecords', 'Decision Records')}
          </CardTitle>
          <div className="grid w-full grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] gap-2 sm:flex sm:w-auto sm:items-center">
            {/* Filters */}
            <Select value={filterOperation} onValueChange={setFilterOperation}>
              <SelectTrigger className="h-8 w-full text-xs sm:w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('common.all', 'All')}</SelectItem>
                <SelectItem value="buy">做多</SelectItem>
                <SelectItem value="sell">做空</SelectItem>
                <SelectItem value="hold">持有</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterSymbol} onValueChange={setFilterSymbol}>
              <SelectTrigger className="h-8 w-full text-xs sm:w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('common.all', 'All')}</SelectItem>
                {availableSymbols.map(s => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fetchRecords()}
              disabled={loading}
              className="h-8 w-8 shrink-0 p-0"
              aria-label={t('common.refresh', 'Refresh')}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col pt-0">
        <div className="min-h-0 flex-1 overflow-auto rounded-md border">
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-8 sticky top-0 bg-background z-10">
                  <Checkbox
                    checked={selectedIds.size === filteredRecords.length && filteredRecords.length > 0}
                    onCheckedChange={toggleSelectAll}
                  />
                </TableHead>
                <TableHead className="sticky top-0 bg-background z-10 w-20">{t('promptBacktest.time', 'Time')}</TableHead>
                <TableHead className="sticky top-0 bg-background z-10 w-16">{t('promptBacktest.operation', 'Op')}</TableHead>
                <TableHead className="sticky top-0 bg-background z-10 w-16">{t('promptBacktest.symbol', 'Symbol')}</TableHead>
                <TableHead className="sticky top-0 bg-background z-10 w-16">P&L</TableHead>
                <TableHead className="sticky top-0 bg-background z-10">{t('promptBacktest.reason', 'Reason')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRecords.map(record => (
                <TableRow key={record.id} className="cursor-pointer hover:bg-muted/50">
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(record.id)}
                      onCheckedChange={() => toggleSelect(record.id)}
                    />
                  </TableCell>
                  <TableCell className="text-xs">{formatTime(record.decision_time)}</TableCell>
                  <TableCell>
                    <Badge variant={getOperationColor(record.operation)} className="text-xs">
                      {record.operation}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">{record.symbol || '-'}</TableCell>
                  <TableCell className={`text-xs ${record.realized_pnl && record.realized_pnl < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {record.realized_pnl != null ? `$${record.realized_pnl.toFixed(2)}` : '-'}
                  </TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate" title={record.reason}>
                    {record.reason || '-'}
                  </TableCell>
                </TableRow>
              ))}
              {filteredRecords.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    {loading ? t('common.loading', 'Loading...') : t('promptBacktest.noRecords', 'No records found')}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        {/* Load More & Add to Workspace */}
        <div className="mt-3 flex flex-col gap-2 border-t pt-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            {filteredRecords.length} {t('promptBacktest.records', 'records')}
            {selectedIds.size > 0 && ` · ${selectedIds.size} ${t('promptBacktest.selected', 'selected')}`}
          </div>
          <div className="flex flex-wrap gap-2">
            {hasMore && (
              <Button variant="outline" size="sm" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : t('common.loadMore', 'Load More')}
              </Button>
            )}
            <Button
              size="sm"
              onClick={loadToWorkspace}
              disabled={selectedIds.size === 0 || loadingSnapshots}
            >
              {loadingSnapshots ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <ChevronRight className="h-4 w-4 mr-1" />
              )}
              {t('promptBacktest.addToWorkspace', 'Add')} ({selectedIds.size})
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
