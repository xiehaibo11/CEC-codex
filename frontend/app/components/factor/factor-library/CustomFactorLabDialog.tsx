import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { CheckCircle2, FlaskConical } from 'lucide-react'
import PacmanLoader from '@/components/ui/pacman-loader'
import { KLINE_PERIODS, FUNC_CATEGORIES, FUNC_TEMPLATES } from './constants'
import { icBadge, wrBadge } from './helpers'
import type { FactorLibraryController } from './useFactorLibrary'

export default function CustomFactorLabDialog({ ctrl }: { ctrl: FactorLibraryController }) {
  const {
    t, isZh, labDialogOpen, setLabDialogOpen, symbol, setSymbol, symbols, period, setPeriod,
    expression, setExpression, handleEvaluate, evaluating, evalError, funcCatTab, setFuncCatTab,
    insertFunction, evalResult, saveName, setSaveName, saveDesc, setSaveDesc, saving, handleSaveCustom,
  } = ctrl

  return (
    <Dialog open={labDialogOpen} onOpenChange={setLabDialogOpen}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            {t('factors.customLab')}
          </DialogTitle>
          <DialogDescription>{t('factors.customLabDesc')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Target: symbol + period */}
          <div className="flex gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">币种</label>
              <Select value={symbol} onValueChange={setSymbol}>
                <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {symbols.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">{t('factors.klinePeriodLabel')}</label>
              <Select value={period} onValueChange={setPeriod}>
                <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {KLINE_PERIODS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Expression input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">{t('factors.expression')}</label>
            <div className="flex gap-2">
              <Input
                className="font-mono text-sm flex-1"
                placeholder={t('factors.expressionPlaceholder')}
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleEvaluate()}
              />
              <Button disabled={evaluating || !expression.trim() || !symbol} onClick={handleEvaluate}>
                {evaluating
                  ? <><PacmanLoader className="w-5 h-4 mr-1.5" />{t('factors.evaluating')}</>
                  : t('factors.evaluate')}
              </Button>
            </div>
            {/* Error display */}
            {evalError && (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
                {evalError}
              </div>
            )}
          </div>

          {/* Function picker - tabbed panel */}
          <div className="rounded-md border overflow-hidden">
            <div className="flex border-b bg-muted/30">
              {FUNC_CATEGORIES.map(cat => (
                <button key={cat.key}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors border-b-2 -mb-px ${
                    funcCatTab === cat.key
                      ? 'border-primary text-foreground bg-background'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => setFuncCatTab(cat.key)}>
                  {isZh ? cat.zh : cat.en}
                </button>
              ))}
            </div>
            <div className="p-2 flex gap-1.5 flex-wrap">
              {(FUNC_CATEGORIES.find(c => c.key === funcCatTab)?.fns || []).map(fn => (
                <Tooltip key={fn}>
                  <TooltipTrigger asChild>
                    <button
                      className="px-2.5 py-1 rounded bg-muted hover:bg-primary/10 text-xs font-mono border border-transparent hover:border-primary/30 transition-colors"
                      onClick={() => insertFunction(fn)}
                    >{fn}</button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <p className="text-xs font-mono">{FUNC_TEMPLATES[fn]}</p>
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>

          {/* Evaluation results */}
          {evalResult && (
            <div className="space-y-3 border-t pt-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                <span className="text-sm font-medium">{evalResult.symbol}</span>
                <span className="text-xs text-muted-foreground">
                  {t('factors.latestValue')}: <span className="font-mono text-foreground">{evalResult.latest_value?.toFixed(6) ?? '—'}</span>
                </span>
                {evalResult.decay_half_life_hours != null && (
                  <span className="text-xs text-muted-foreground">
                    {t('factors.decay')}: {evalResult.decay_half_life_hours === -1
                      ? <span className="text-blue-400">{t('factors.persistent')}</span>
                      : <span className={`font-mono ${evalResult.decay_half_life_hours <= 4 ? 'text-red-400' : evalResult.decay_half_life_hours <= 12 ? 'text-yellow-500' : 'text-green-500'}`}>{evalResult.decay_half_life_hours}h</span>}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-4 gap-3">
                {Object.entries(evalResult.effectiveness as Record<string, any>).map(([fp, m]: [string, any]) => (
                  <div key={fp} className="rounded-lg border p-3 space-y-1.5">
                    <div className="font-medium text-sm text-center">{fp}</div>
                    <div className="flex justify-between text-xs"><span className="text-muted-foreground">IC</span>{icBadge(m.ic_mean)}</div>
                    <div className="flex justify-between text-xs"><span className="text-muted-foreground">ICIR</span><span className="font-mono">{m.icir?.toFixed(2)}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-muted-foreground">{t('factors.winRate')}</span>{wrBadge(m.win_rate)}</div>
                    <div className="flex justify-between text-xs"><span className="text-muted-foreground">N</span><span>{m.sample_count}</span></div>
                  </div>
                ))}
              </div>

              {/* Save form */}
              <div className="border-t pt-3 space-y-3">
                <label className="text-sm font-medium">{t('factors.saveToLibrary')}</label>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">{t('factors.factorName')}</label>
                    <Input className="text-sm" placeholder={t('factors.factorNamePlaceholder')}
                      value={saveName} onChange={e => setSaveName(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">{t('factors.description')}</label>
                    <Input className="text-sm" placeholder={t('factors.descriptionPlaceholder')}
                      value={saveDesc} onChange={e => setSaveDesc(e.target.value)} />
                  </div>
                </div>
                <Button disabled={saving || !saveName.trim()} onClick={handleSaveCustom} className="gap-1.5">
                  {saving ? t('factors.saving') : <><CheckCircle2 className="h-4 w-4" />{t('factors.saveToLibrary')}</>}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
