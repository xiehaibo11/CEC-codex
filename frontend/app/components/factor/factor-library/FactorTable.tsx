import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Info, ArrowUpDown, Trash2, Pencil, BarChart3 } from 'lucide-react'
import { icBadge, wrBadge } from './helpers'
import type { FactorLibraryController } from './useFactorLibrary'

export default function FactorTable({ ctrl }: { ctrl: FactorLibraryController }) {
  const {
    t, isZh, period, sortCol, toggleSort, mergedRows, getCatLabel, getFactorDesc,
    openLabDialog, handleDeleteCustom, setAnalysisFactor, setAnalysisOpen,
  } = ctrl

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <Table>
        <TableHeader className="sticky top-0 bg-background z-10">
          <TableRow>
            <TableHead>{t('factors.name')}</TableHead>
            <TableHead>{t('factors.category')}</TableHead>
            <TableHead className="text-right">{t('factors.value')} ({t('factors.baseKline')}: {period})</TableHead>
            <TableHead className="text-right">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort('ic_mean')}>
                    IC {sortCol === 'ic_mean' && <ArrowUpDown className="h-3 w-3" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[220px]"><p className="text-xs">{t('factors.icTooltip')}</p></TooltipContent>
              </Tooltip>
            </TableHead>
            <TableHead className="text-right">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort('icir')}>
                    ICIR {sortCol === 'icir' && <ArrowUpDown className="h-3 w-3" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[220px]"><p className="text-xs">{t('factors.icirTooltip')}</p></TooltipContent>
              </Tooltip>
            </TableHead>
            <TableHead className="text-right">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => toggleSort('win_rate')}>
                    {t('factors.winRate')} {sortCol === 'win_rate' && <ArrowUpDown className="h-3 w-3" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[220px]"><p className="text-xs">{t('factors.winRateTooltip')}</p></TooltipContent>
              </Tooltip>
            </TableHead>
            <TableHead className="text-right">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex items-center gap-1 cursor-help">
                    {t('factors.decay')} <Info className="h-3 w-3" />
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[240px]"><p className="text-xs">{t('factors.decayTooltip')}</p></TooltipContent>
              </Tooltip>
            </TableHead>
            <TableHead className="text-right">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex items-center gap-1 cursor-help">
                    {t('factors.icTrend')} <Info className="h-3 w-3" />
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-[280px]"><p className="text-xs">{t('factors.icTrendTooltip')}</p></TooltipContent>
              </Tooltip>
            </TableHead>
            <TableHead className="text-right">{t('factors.samples')}</TableHead>
            <TableHead className="w-24"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {mergedRows.map((row: any) => (
            <TableRow key={row._isCustom ? `custom-${row._customId}` : row.name}>
              <TableCell>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="font-medium cursor-help flex items-center gap-1">
                      {row._isCustom ? row.name : row.display_name}
                      <Info className="h-3 w-3 text-muted-foreground" />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs">
                    {row._isCustom ? (
                      <p className="text-xs font-mono">{row._expression}</p>
                    ) : (
                      <>
                        {isZh && row.display_name_zh && <p className="text-xs font-medium mb-1">{row.display_name_zh}</p>}
                        <p className="text-xs">{getFactorDesc(row)}</p>
                        {row.value_range && (
                          <p className="text-xs text-muted-foreground mt-1">{t('factors.range')}: {row.value_range} {row.unit || ''}</p>
                        )}
                      </>
                    )}
                  </TooltipContent>
                </Tooltip>
              </TableCell>
              <TableCell>
                {row._isCustom ? (
                  <Badge variant="outline" className="text-xs bg-purple-500/10 text-purple-400 border-purple-500/30">
                    {t('factors.customTag')}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-xs">{getCatLabel(row.category)}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {row.value != null ? row.value.toFixed(4) : '—'}
              </TableCell>
              <TableCell className="text-right">{icBadge(row.ic_mean)}</TableCell>
              <TableCell className="text-right font-mono text-sm">
                {row.icir != null ? row.icir.toFixed(2) : '—'}
              </TableCell>
              <TableCell className="text-right">{wrBadge(row.win_rate)}</TableCell>
              <TableCell className="text-right text-sm">
                {row.decay_half_life != null ? (
                  row.decay_half_life === -1
                    ? <span className="text-blue-400 text-xs">{t('factors.persistent')}</span>
                    : <span className={`font-mono ${row.decay_half_life <= 4 ? 'text-red-400' : row.decay_half_life <= 12 ? 'text-yellow-500' : 'text-green-500'}`}>{row.decay_half_life}h</span>
                ) : <span className="text-muted-foreground">—</span>}
              </TableCell>
              <TableCell className="text-right text-sm">
                {row.ic_trend != null ? (
                  <span className={`font-mono ${row.ic_trend >= 1.2 ? 'text-green-500' : row.ic_trend >= 0.8 ? 'text-yellow-500' : 'text-red-400'}`}>
                    {row.ic_trend.toFixed(2)}x
                  </span>
                ) : <span className="text-muted-foreground">—</span>}
              </TableCell>
              <TableCell className="text-right text-sm">{row.sample_count ?? '—'}</TableCell>
              <TableCell className="text-right">
                <div className="flex gap-0.5 justify-end">
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0" title={t('factors.analysis.title')}
                    onClick={() => { setAnalysisFactor({ name: row._isCustom ? row.name : row.name, displayName: row._isCustom ? row.name : (isZh && row.display_name_zh ? row.display_name_zh : row.display_name) }); setAnalysisOpen(true) }}>
                    <BarChart3 className="h-3 w-3" />
                  </Button>
                  {row._isCustom && (
                    <>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0"
                        onClick={() => openLabDialog(row._customId)}>
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500"
                        onClick={() => handleDeleteCustom(row._customId)}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
