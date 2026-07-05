import { Fragment } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Play, X, Loader2, History, Search, Check } from 'lucide-react'
import { formatTime, getOperationColor } from './formatters'
import type { SelectedRecord } from './types'

interface WorkspacePanelProps {
  workspace: SelectedRecord[]
  findText: string
  replaceText: string
  setReplaceText: (value: string) => void
  replaceCount: number | null
  searchMode: boolean
  isSubmitting: boolean
  handleFindTextChange: (value: string) => void
  searchPreview: () => void
  applyReplace: () => void
  clearSearch: () => void
  submitBacktest: () => void
  toggleWorkspaceSelect: (id: number) => void
  removeFromWorkspace: (id: number) => void
  onOpenHistory: () => void
  onEditRecord: (record: SelectedRecord) => void
}

export default function WorkspacePanel({
  workspace,
  findText,
  replaceText,
  setReplaceText,
  replaceCount,
  searchMode,
  isSubmitting,
  handleFindTextChange,
  searchPreview,
  applyReplace,
  clearSearch,
  submitBacktest,
  toggleWorkspaceSelect,
  removeFromWorkspace,
  onOpenHistory,
  onEditRecord,
}: WorkspacePanelProps) {
  const { t } = useTranslation()

  return (
    <Card className="flex min-h-[480px] flex-col xl:min-h-0">
      <CardHeader className="pb-2 shrink-0">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">
            {t('promptBacktest.workspace', 'Workspace')} ({workspace.length})
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={onOpenHistory}>
              <History className="h-4 w-4 mr-1" />
              {t('promptBacktest.history', 'History')}
            </Button>
            <Button size="sm" onClick={submitBacktest} disabled={workspace.length === 0 || isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-1" />
              )}
              {t('promptBacktest.runBacktest', 'Run')}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col space-y-3 pt-0">
        {/* Batch Replace */}
        <div className="flex shrink-0 flex-col gap-2 md:flex-row md:items-stretch">
          <Textarea
            placeholder={t('promptBacktest.findText', 'Find...')}
            value={findText}
            onChange={e => handleFindTextChange(e.target.value)}
            className="min-h-[68px] max-h-[100px] flex-1 resize-none text-xs font-mono"
          />
          <Textarea
            placeholder={t('promptBacktest.replaceWith', 'Replace...')}
            value={replaceText}
            onChange={e => setReplaceText(e.target.value)}
            className="min-h-[68px] max-h-[100px] flex-1 resize-none text-xs font-mono"
          />
          <div className="grid grid-cols-2 gap-2 md:flex md:flex-col md:gap-1">
            <Button variant="outline" size="sm" onClick={searchPreview} disabled={!findText} className="flex-1">
              <Search className="h-4 w-4 mr-1" />
              {t('promptBacktest.preview', 'Preview')}
            </Button>
            <Button
              size="sm"
              onClick={applyReplace}
              disabled={!findText || !searchMode || workspace.filter(r => r.isMatched && r.isSelected).length === 0}
              className="flex-1"
            >
              {t('promptBacktest.replace', 'Replace')}
            </Button>
          </div>
        </div>
        {/* Search/Replace Status */}
        {searchMode && (
          <div className="flex items-center justify-between text-xs shrink-0">
            <span className="text-muted-foreground">
              {t('promptBacktest.matchedCount', '{{matched}} matched, {{selected}} selected', {
                matched: workspace.filter(r => r.isMatched).length,
                selected: workspace.filter(r => r.isMatched && r.isSelected).length,
              })}
            </span>
            <Button variant="ghost" size="sm" onClick={clearSearch} className="h-6 px-2 text-xs">
              <X className="h-3 w-3 mr-1" />
              {t('promptBacktest.clearSearch', 'Clear')}
            </Button>
          </div>
        )}
        {replaceCount !== null && (
          <p className="text-xs text-muted-foreground shrink-0">
            {t('promptBacktest.replacedCount', 'Replaced in {{count}} records', { count: replaceCount })}
          </p>
        )}

        {/* Workspace Items */}
        <div className="min-h-0 flex-1 overflow-auto rounded-md border">
          {workspace.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm py-12">
              {t('promptBacktest.emptyWorkspace', 'Select records from the left and click Add')}
            </div>
          ) : (
            <Table className="min-w-[720px]">
              <TableHeader>
                <TableRow>
                  {searchMode && (
                    <TableHead className="sticky top-0 bg-background z-10 w-8"></TableHead>
                  )}
                  <TableHead className="sticky top-0 bg-background z-10">{t('promptBacktest.time', 'Time')}</TableHead>
                  <TableHead className="sticky top-0 bg-background z-10">{t('promptBacktest.operation', 'Op')}</TableHead>
                  <TableHead className="sticky top-0 bg-background z-10">{t('promptBacktest.symbol', 'Symbol')}</TableHead>
                  <TableHead className="sticky top-0 bg-background z-10 text-right">{t('promptBacktest.pnl', 'P&L')}</TableHead>
                  <TableHead className="sticky top-0 bg-background z-10">{t('promptBacktest.status', 'Status')}</TableHead>
                  <TableHead className="sticky top-0 bg-background z-10 w-24">{t('common.actions', 'Actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {workspace.map(record => (
                  <Fragment key={record.id}>
                    <TableRow
                      className={record.isMatched === false ? 'opacity-50' : ''}
                    >
                      {searchMode && (
                        <TableCell className="w-8">
                          {record.isMatched && (
                            <Checkbox
                              checked={record.isSelected}
                              onCheckedChange={() => toggleWorkspaceSelect(record.id)}
                            />
                          )}
                        </TableCell>
                      )}
                      <TableCell className="text-xs">{formatTime(record.decision_time)}</TableCell>
                      <TableCell>
                        <Badge variant={getOperationColor(record.operation)} className="text-xs">
                          {record.operation}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">{record.symbol || '-'}</TableCell>
                      <TableCell className="text-xs text-right">
                        {record.realized_pnl != null ? (
                          <span className={record.realized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}>
                            {record.realized_pnl >= 0 ? '+' : ''}{record.realized_pnl.toFixed(2)}
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-xs">
                        {record.isModified ? (
                          <Badge variant="default" className="text-xs bg-green-600">
                            <Check className="h-3 w-3 mr-1" />
                            {t('promptBacktest.modified', 'Modified')}
                          </Badge>
                        ) : record.isMatched === true ? (
                          <Badge variant="outline" className="text-xs border-blue-500 text-blue-600">
                            {t('promptBacktest.matched', 'Matched')}
                          </Badge>
                        ) : record.isMatched === false ? (
                          <span className="text-muted-foreground">{t('promptBacktest.noMatch', 'No match')}</span>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs"
                            onClick={() => onEditRecord(record)}
                          >
                            {t('common.edit', 'Edit')}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 text-destructive"
                            onClick={() => removeFromWorkspace(record.id)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Context row - show when matched */}
                    {record.isMatched && record.matchContext && (
                      <TableRow className="bg-muted/30">
                        <TableCell colSpan={searchMode ? 7 : 6} className="py-2">
                          <pre className="text-xs font-mono whitespace-pre-wrap text-muted-foreground max-h-[80px] overflow-auto">
                            {record.matchContext}
                          </pre>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
