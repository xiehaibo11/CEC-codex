import { useTranslation } from 'react-i18next'
import { Loader2, ShieldCheck } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type {
  CoinGlassEventContractCapability,
  DataQualityPreview,
  EventContractSymbol,
  HyperAiProfile,
} from '@/lib/api'

import { ToggleRow } from './shared'
import type { FormState } from './types'

type Props = {
  form: FormState
  symbolOptions: string[]
  periodOptions: string[]
  selectedSymbolMeta?: EventContractSymbol
  hyperAiProfile: HyperAiProfile | null
  coinglassCapability: CoinGlassEventContractCapability | null
  loadingCoinGlassCapability: boolean
  loadingSymbols: boolean
  updateForm: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  qualityPreview: DataQualityPreview | null
  checkingQuality: boolean
  onCheckDataQuality: () => void
}

export function BacktestConfigPanel({
  form,
  symbolOptions,
  periodOptions,
  selectedSymbolMeta,
  hyperAiProfile,
  coinglassCapability,
  loadingCoinGlassCapability,
  loadingSymbols,
  updateForm,
  qualityPreview,
  checkingQuality,
  onCheckDataQuality,
}: Props) {
  const { t } = useTranslation()
  const coinGlassAvailable = coinglassCapability?.available === true
  const coinGlassDisabled = loadingCoinGlassCapability || !coinGlassAvailable
  const professionalMode = form.decision_policy === 'professional_v1'

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t('backtestTool.config', 'Configuration')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.exchange', 'Exchange')}</Label>
            <Select value={form.exchange} onValueChange={value => updateForm('exchange', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="binance">Binance</SelectItem>
                <SelectItem value="hyperliquid">Hyperliquid</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.symbol', 'Symbol')}</Label>
            <Select value={form.symbol} onValueChange={value => updateForm('symbol', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {(symbolOptions.length ? symbolOptions : ['BTC']).map(symbol => (
                  <SelectItem key={symbol} value={symbol}>{symbol}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.mainPeriod', 'Main Period')}</Label>
            <Select value={form.period} onValueChange={value => updateForm('period', value)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {periodOptions.map(period => (
                  <SelectItem key={period} value={period}>{period}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.expiry', 'Expiry')}</Label>
            <Select value={String(form.expiry_minutes)} onValueChange={value => updateForm('expiry_minutes', Number(value))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {[1, 3, 5, 10, 15].map(value => (
                  <SelectItem key={value} value={String(value)}>{value}m</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {professionalMode ? (
            <div className="space-y-1">
              <Label className="text-xs">{t('backtestTool.executionMode', 'Execution Mode')}</Label>
              <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm font-medium">
                {t('backtestTool.professionalNoSharedVote', 'No shared AI vote gate')}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <Label className="text-xs">{t('backtestTool.consensusMode', 'Consensus Mode')}</Label>
              <Select value={form.consensus_mode} onValueChange={value => updateForm('consensus_mode', value as FormState['consensus_mode'])}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="ai_confirmed">{t('backtestTool.aiConfirmed', 'Real AI confirmation')}</SelectItem>
                  <SelectItem value="rule_only">{t('backtestTool.ruleOnly', 'Rule prefilter only')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.decisionPolicy', 'Decision Policy')}</Label>
            <Select value={form.decision_policy} onValueChange={value => updateForm('decision_policy', value as FormState['decision_policy'])}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="professional_v1">{t('backtestTool.professionalPolicy', 'Professional workflow')}</SelectItem>
                <SelectItem value="legacy_vote">{t('backtestTool.legacyVotePolicy', 'Legacy vote gate')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {professionalMode ? (
            <div className="space-y-1">
              <Label className="text-xs">{t('backtestTool.independentAiTraders', 'Independent AI Traders')}</Label>
              <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm font-medium">
                {t('backtestTool.independentAiTraderCount', '30 traders')}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <Label className="text-xs">{t('backtestTool.maxAiEvaluations', 'Max AI Checks')}</Label>
              <Input
                type="number"
                min={1}
                max={200}
                value={form.max_ai_evaluations}
                disabled={form.consensus_mode === 'rule_only'}
                onChange={event => updateForm('max_ai_evaluations', Number(event.target.value))}
              />
            </div>
          )}
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.targetWinRate', 'Target Win Rate')}</Label>
            <Input
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={form.target_win_rate}
              disabled={!form.enable_edge_quality_gate}
              onChange={event => updateForm('target_win_rate', Number(event.target.value))}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.maxRangeRisk', 'Max Range Risk')}</Label>
            <Input
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={form.max_trade_range_risk}
              disabled={!form.enable_edge_quality_gate}
              onChange={event => updateForm('max_trade_range_risk', Number(event.target.value))}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.l2Coverage', 'L2 Min Coverage')}</Label>
            <Input
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={form.min_l2_coverage_pct}
              disabled={!form.enable_l2_features}
              onChange={event => updateForm('min_l2_coverage_pct', Number(event.target.value))}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.coinglassCoverage', 'CoinGlass Min Coverage')}</Label>
            <Input
              type="number"
              min={0}
              max={100}
              step={0.1}
              value={form.min_coinglass_coverage_pct}
              disabled={!form.enable_coinglass_features || !coinGlassAvailable}
              onChange={event => updateForm('min_coinglass_coverage_pct', Number(event.target.value))}
            />
          </div>
        </div>

        <div className={`rounded-md border p-3 text-xs ${!professionalMode && form.consensus_mode === 'ai_confirmed' ? 'bg-blue-500/5 text-blue-700 dark:text-blue-300' : professionalMode ? 'bg-green-500/5 text-green-700 dark:text-green-300' : 'bg-muted/30 text-muted-foreground'}`}>
          <div>
            {professionalMode
              ? t('backtestTool.professionalPolicyNotice', 'Professional workflow: score signal edge first; only objective risk thresholds can veto; execution feasibility is audited before a trade is counted.')
              : t('backtestTool.legacyVotePolicyNotice', 'Legacy vote gate: trades must reach the configured reviewer vote threshold. Use only for old-run comparison.')}
          </div>
          <div className="mt-1">
            {professionalMode
              ? t('backtestTool.professionalIndependentDeskNotice', 'Professional mode does not wait for all AIs to agree: the main strategy trades by desk policy, while 30 AI traders run independent paper portfolios and are ranked in Research Mode.')
              : form.consensus_mode === 'ai_confirmed'
                ? hyperAiProfile?.llm_configured
                  ? t('backtestTool.aiModeReady', 'Real AI mode: candidate signals will be confirmed by {{model}} before trades are counted.', {
                    model: hyperAiProfile.llm_model || hyperAiProfile.llm_provider || 'configured LLM',
                  })
                  : t('backtestTool.aiModeMissing', 'Real AI mode requires Hyper AI or an AI Trader with a valid LLM API key. No fake AI results will be generated.')
                : t('backtestTool.ruleModeNotice', 'Rule-only mode is fast, but it is not real AI participation. Results are labeled as rule prefilter output.')}
          </div>
        </div>

        <div className="rounded-md border p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 text-xs font-medium">
              <ShieldCheck className="h-3.5 w-3.5" />
              {t('backtestTool.dataQualityTitle', 'Data Quality Precheck')}
            </div>
            <Button size="sm" variant="outline" className="h-7 text-xs" disabled={checkingQuality} onClick={onCheckDataQuality}>
              {checkingQuality && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
              {t('backtestTool.checkDataQuality', 'Check Coverage')}
            </Button>
          </div>
          {qualityPreview ? (
            <div className="space-y-1.5 text-xs">
              {([
                ['kline', t('backtestTool.klineCoverage', 'K-line'), qualityPreview.kline],
                ['l2', t('backtestTool.l2Source', 'L2 Orderbook'), qualityPreview.l2],
                ['coinglass', 'CoinGlass', qualityPreview.coinglass],
              ] as const).map(([source, label, audit]) => {
                if (!audit) return null
                const blocked = qualityPreview.would_block.some(item => item.source === source)
                const warned = (audit.warnings || []).length > 0
                const tone = blocked ? 'text-red-600' : warned ? 'text-amber-600' : 'text-green-600'
                return (
                  <div key={source} className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">{label}</span>
                    <span className={`font-medium ${tone}`}>
                      {audit.coverage_pct.toFixed(2)}%
                      {audit.min_required_coverage_pct != null && ` / ≥${audit.min_required_coverage_pct}%`}
                      {blocked
                        ? ` · ${t('backtestTool.qualityWouldBlock', 'will abort run')}`
                        : warned
                          ? ` · ${t('backtestTool.qualityWarning', 'warning')}`
                          : ` · ${t('backtestTool.qualityPass', 'OK')}`}
                    </span>
                  </div>
                )
              })}
              {(() => {
                const sanitize = qualityPreview.kline?.sanitize
                if (!sanitize || (sanitize.dropped_invalid_bars === 0 && sanitize.dropped_duplicate_bars === 0)) return null
                return (
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">{t('backtestTool.sanitizeLabel', 'Cleaning')}</span>
                    <span className={sanitize.dropped_invalid_bars > 0 ? 'font-medium text-amber-600' : 'text-muted-foreground'}>
                      {t('backtestTool.sanitizeSummary', 'deduped {{dups}} · dropped {{invalid}} corrupt bars', {
                        dups: sanitize.dropped_duplicate_bars,
                        invalid: sanitize.dropped_invalid_bars,
                      })}
                    </span>
                  </div>
                )
              })()}
              {!qualityPreview.ok && (
                <p className="text-amber-700 dark:text-amber-400">
                  {t('backtestTool.qualitySuggestion', 'Options: pick a window with better coverage, lower the min coverage threshold, or turn off strict quality mode (results will be labeled lower-credibility).')}
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              {t('backtestTool.dataQualityHint', 'Checks kline/L2/CoinGlass coverage for the selected window before you run, so strict quality gates do not abort the run mid-flight.')}
            </p>
          )}
        </div>

        <div className="space-y-1">
          <Label className="text-xs">{t('backtestTool.startTime', 'Start Time')}</Label>
          <Input type="datetime-local" value={form.start_time} onChange={event => updateForm('start_time', event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">{t('backtestTool.endTime', 'End Time')}</Label>
          <Input type="datetime-local" value={form.end_time} onChange={event => updateForm('end_time', event.target.value)} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1 col-span-2">
            <Label className="text-xs">{t('backtestTool.platform', 'Target Platform')}</Label>
            <Select value={form.platform} onValueChange={value => updateForm('platform', value as FormState['platform'])}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="custom">{t('backtestTool.platformCustom', 'Custom rules')}</SelectItem>
                <SelectItem value="hibt">{t('backtestTool.platformHibt', 'HIBT event contract')}</SelectItem>
                <SelectItem value="binance_event">{t('backtestTool.platformBinance', 'Binance Event Contracts')}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              {form.platform === 'binance_event'
                ? t('backtestTool.platformBinanceHint', 'Payout 0.8, draw refunds stake, min 5 USDT, 10k daily loss cap.')
                : form.platform === 'hibt'
                  ? t('backtestTool.platformHibtHint', 'Payout 0.8, no fee, min 3 USDT, one entry per minute.')
                  : t('backtestTool.platformCustomHint', 'All economics editable below.')}
            </p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.initialBalance', 'Initial Balance')}</Label>
            <Input type="number" value={form.initial_balance} onChange={event => updateForm('initial_balance', Number(event.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.stake', 'Stake')}</Label>
            <Input type="number" value={form.stake_amount} onChange={event => updateForm('stake_amount', Number(event.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.payout', 'Win Payout')}</Label>
            <Input type="number" step="0.01" value={form.win_payout_ratio} onChange={event => updateForm('win_payout_ratio', Number(event.target.value))} />
          </div>
          {!professionalMode && (
            <>
              <div className="space-y-1">
                <Label className="text-xs">{t('backtestTool.threshold', 'Required Votes')}</Label>
                <Input
                  type="number"
                  min={1}
                  max={form.reviewer_panel_size}
                  value={form.consensus_threshold}
                  onChange={event => updateForm('consensus_threshold', Number(event.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t('backtestTool.reviewerPanelSize', 'Panel Size')}</Label>
                <Input
                  type="number"
                  min={5}
                  max={31}
                  value={form.reviewer_panel_size}
                  onChange={event => {
                    const panelSize = Number(event.target.value)
                    updateForm('reviewer_panel_size', panelSize)
                    if (form.consensus_threshold > panelSize) {
                      updateForm('consensus_threshold', panelSize)
                    }
                  }}
                />
              </div>
            </>
          )}
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.feeRate', 'Fee Rate')}</Label>
            <Input type="number" step="0.0001" value={form.fee_rate} onChange={event => updateForm('fee_rate', Number(event.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.slippage', 'Slippage bps')}</Label>
            <Input type="number" value={form.slippage_bps} onChange={event => updateForm('slippage_bps', Number(event.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.impactCost', 'Impact bps')}</Label>
            <Input type="number" step="0.5" value={form.impact_cost_bps} onChange={event => updateForm('impact_cost_bps', Number(event.target.value))} />
          </div>
        </div>

        {(Number(form.fee_rate) <= 0 || Number(form.slippage_bps) < 2 || Number(form.impact_cost_bps) < 0.5) && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            {t('backtestTool.costFloorHint', 'Execution-cost floors are enforced at run time: fee ≥ 0.1%, slippage ≥ 2 bps, impact ≥ 0.5 bps, delay ≥ 3s. Values below the floor are raised automatically.')}
          </p>
        )}

        <div className="grid gap-2">
          <ToggleRow label={t('backtestTool.nonOverlapping', 'One bet at a time (independent samples)')} checked={form.non_overlapping_only} onChange={value => updateForm('non_overlapping_only', value)} />
          <ToggleRow label={t('backtestTool.edgeQualityGate', '75% edge quality gate')} checked={form.enable_edge_quality_gate} onChange={value => updateForm('enable_edge_quality_gate', value)} />
          <ToggleRow
            label={t('backtestTool.allowPullbackTrades', 'Allow pullback trades')}
            checked={form.allow_pullback_trades}
            disabled={!form.enable_edge_quality_gate}
            onChange={value => updateForm('allow_pullback_trades', value)}
          />
          <ToggleRow label={t('backtestTool.fakeFilter', 'Fake breakout filter')} checked={form.enable_fake_breakout_filter} onChange={value => updateForm('enable_fake_breakout_filter', value)} />
          <ToggleRow label={t('backtestTool.trapFilter', 'Bull/Bear trap filter')} checked={form.enable_trap_filter} onChange={value => updateForm('enable_trap_filter', value)} />
          <ToggleRow label={t('backtestTool.rangeFilter', 'Range middle no-trade filter')} checked={form.enable_range_filter} onChange={value => updateForm('enable_range_filter', value)} />
          <ToggleRow label={t('backtestTool.mtfFilter', 'Multi-timeframe conflict filter')} checked={form.enable_multi_timeframe_filter} onChange={value => updateForm('enable_multi_timeframe_filter', value)} />
          <ToggleRow label={t('backtestTool.volumeFilter', 'Volume confirmation filter')} checked={form.enable_volume_filter} onChange={value => updateForm('enable_volume_filter', value)} />
          <ToggleRow label={t('backtestTool.l2Features', 'Local L2 orderbook factors')} checked={form.enable_l2_features} onChange={value => updateForm('enable_l2_features', value)} />
          <ToggleRow label={t('backtestTool.strictL2', 'Strict L2 coverage')} checked={form.strict_l2_quality} onChange={value => updateForm('strict_l2_quality', value)} />
          <ToggleRow
            label={t('backtestTool.coinglassFeatures', 'CoinGlass historical factors')}
            checked={form.enable_coinglass_features && coinGlassAvailable}
            disabled={coinGlassDisabled}
            onChange={value => updateForm('enable_coinglass_features', value)}
          />
          <ToggleRow
            label={t('backtestTool.strictCoinGlass', 'Strict CoinGlass coverage')}
            checked={form.strict_coinglass_quality}
            disabled={coinGlassDisabled || !form.enable_coinglass_features}
            onChange={value => updateForm('strict_coinglass_quality', value)}
          />
          <ToggleRow
            label={t('backtestTool.noFutureLeak', 'No-future-leak alignment')}
            checked={form.coinglass_no_future_leakage}
            disabled={coinGlassDisabled || !form.enable_coinglass_features}
            onChange={value => updateForm('coinglass_no_future_leakage', value)}
          />
          <ToggleRow
            label={t('backtestTool.cvdFilter', 'CVD confirmation filter')}
            checked={form.enable_cvd_filter}
            disabled={form.enable_coinglass_features && !coinGlassAvailable}
            onChange={value => updateForm('enable_cvd_filter', value)}
          />
        </div>

        <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
          {loadingSymbols
            ? t('backtestTool.loadingSymbols', 'Loading K-line coverage...')
            : selectedSymbolMeta
              ? t('backtestTool.coverage', 'Coverage: {{records}} records, periods {{periods}}', {
                records: selectedSymbolMeta.records.toLocaleString(),
                periods: selectedSymbolMeta.periods.join(', '),
              })
              : t('backtestTool.noCoverage', 'No K-line coverage found for this selection.')}
          <div className="mt-1">
            {form.enable_l2_features
              ? t('backtestTool.l2Enabled', 'Local L2 orderbook enabled, min coverage {{coverage}}%.', { coverage: form.min_l2_coverage_pct })
              : t('backtestTool.l2Disabled', 'Local L2 orderbook disabled.')}
          </div>
          <div className="mt-1">
            {loadingCoinGlassCapability
              ? t('backtestTool.coinglassChecking', 'Checking CoinGlass plan...')
              : coinGlassAvailable
                ? form.enable_coinglass_features
                  ? t('backtestTool.coinglassEnabled', 'CoinGlass factors enabled, min coverage {{coverage}}%.', { coverage: form.min_coinglass_coverage_pct })
                  : t('backtestTool.coinglassAvailable', 'CoinGlass plan supports this event-contract period.')
                : t('backtestTool.coinglassUnavailable', 'CoinGlass unavailable for this period: {{reason}}', {
                  reason: coinglassCapability?.reason || t('backtestTool.coinglassNotConfigured', 'not configured or not upgraded'),
                })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
