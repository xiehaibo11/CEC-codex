import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { RefreshCw, Info, FlaskConical, Plus } from 'lucide-react'
import { KLINE_PERIODS, FORWARD_PERIODS } from './constants'
import type { FactorLibraryController } from './useFactorLibrary'

export default function ControlsRow({ ctrl }: { ctrl: FactorLibraryController }) {
  const {
    t, symbols, symbol, setSymbol, period, setPeriod, forwardPeriod, setForwardPeriod,
    compatibleForwardPeriods, computing, handleComputeClick, openLabDialog,
    formatLastUpdate, countdown,
  } = ctrl

  return (
    <div className="flex items-end gap-3 flex-wrap">
      {symbols.length > 0 ? (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">币种</label>
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
            <SelectContent>
              {symbols.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <span className="text-sm text-muted-foreground pb-1">{t('factors.noSymbols')}</span>
      )}

      <div className="flex flex-col gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <label className="text-xs text-muted-foreground flex items-center gap-1 cursor-help">
              {t('factors.klinePeriodLabel')}
              <Info className="h-3 w-3" />
            </label>
          </TooltipTrigger>
          <TooltipContent><p className="text-xs max-w-[240px]">{t('factors.klinePeriodHint')}</p></TooltipContent>
        </Tooltip>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
          <SelectContent>
            {KLINE_PERIODS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <label className="text-xs text-muted-foreground flex items-center gap-1 cursor-help">
              {t('factors.forwardPeriodLabel')}
              <Info className="h-3 w-3" />
            </label>
          </TooltipTrigger>
          <TooltipContent><p className="text-xs max-w-[200px]">{t('factors.forwardPeriodHint')}</p></TooltipContent>
        </Tooltip>
        <Select value={forwardPeriod} onValueChange={setForwardPeriod} disabled={compatibleForwardPeriods.length === 0}>
          <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
          <SelectContent>
            {FORWARD_PERIODS.map(p => (
              <SelectItem key={p} value={p} disabled={!compatibleForwardPeriods.includes(p)}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <span className="text-xs text-muted-foreground self-end pb-1">
        {t('factors.predictionWindowsSummary', {
          windows: compatibleForwardPeriods.length > 0
            ? compatibleForwardPeriods.join(', ')
            : t('factors.noCompatibleWindows'),
        })}
      </span>

      <Button variant="outline" size="sm" className="self-end" disabled={computing || !symbol}
        onClick={handleComputeClick}>
        <RefreshCw className={`h-3.5 w-3.5 mr-1 ${computing ? 'animate-spin' : ''}`} />
        {computing ? t('factors.computing') : t('factors.manualCompute')}
      </Button>

      <Button size="sm" className="self-end gap-1" onClick={() => openLabDialog()}>
        <Plus className="h-3.5 w-3.5" />
        <FlaskConical className="h-3.5 w-3.5" />
        {t('factors.customLab')}
      </Button>

      <span className="text-xs text-muted-foreground ml-auto self-end pb-1">
        {t('factors.lastUpdate')}: {formatLastUpdate()}
        {countdown && ` | ${t('factors.nextCompute')}: ${countdown}`}
      </span>
    </div>
  )
}
