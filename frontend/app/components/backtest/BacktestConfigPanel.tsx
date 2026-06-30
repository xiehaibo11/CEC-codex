import { useTranslation } from 'react-i18next'

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
import type { CoinGlassEventContractCapability, EventContractSymbol, HyperAiProfile } from '@/lib/api'

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
}: Props) {
  const { t } = useTranslation()
  const coinGlassAvailable = coinglassCapability?.available === true
  const coinGlassDisabled = loadingCoinGlassCapability || !coinGlassAvailable

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

        <div className={`rounded-md border p-3 text-xs ${form.consensus_mode === 'ai_confirmed' ? 'bg-blue-500/5 text-blue-700 dark:text-blue-300' : 'bg-muted/30 text-muted-foreground'}`}>
          {form.consensus_mode === 'ai_confirmed'
            ? hyperAiProfile?.llm_configured
              ? t('backtestTool.aiModeReady', 'Real AI mode: candidate signals will be confirmed by {{model}} before trades are counted.', {
                model: hyperAiProfile.llm_model || hyperAiProfile.llm_provider || 'configured LLM',
              })
              : t('backtestTool.aiModeMissing', 'Real AI mode requires Hyper AI or an AI Trader with a valid LLM API key. No fake AI results will be generated.')
            : t('backtestTool.ruleModeNotice', 'Rule-only mode is fast, but it is not real AI participation. Results are labeled as rule prefilter output.')}
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
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.threshold', 'Consensus')}</Label>
            <Select value={String(form.consensus_threshold)} onValueChange={value => updateForm('consensus_threshold', Number(value))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {[30, 29, 28].map(value => (
                  <SelectItem key={value} value={String(value)}>{value}/30</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.feeRate', 'Fee Rate')}</Label>
            <Input type="number" step="0.0001" value={form.fee_rate} onChange={event => updateForm('fee_rate', Number(event.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t('backtestTool.slippage', 'Slippage bps')}</Label>
            <Input type="number" value={form.slippage_bps} onChange={event => updateForm('slippage_bps', Number(event.target.value))} />
          </div>
        </div>

        <div className="grid gap-2">
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
