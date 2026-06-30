import type { Dispatch, SetStateAction } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import StrategyStatusCard from './StrategyStatusCard'
import type { AccountOption, SignalPool } from './types'

interface StrategyConfigFormProps {
  accountId: number
  accountName: string
  accountOptions: AccountOption[]
  accountsLoading: boolean
  selectedAccountLabel: string
  error: string | null
  success: string | null
  exchange: string
  signalPools: SignalPool[]
  signalPoolIds: number[]
  triggerInterval: string
  scheduledTriggerEnabled: boolean
  enabled: boolean
  lastTriggerAt: string | null
  saving: boolean
  onAccountChange?: (accountId: number) => void
  onResetMessages: () => void
  onExchangeChange: (value: string) => void
  onSignalPoolIdsChange: Dispatch<SetStateAction<number[]>>
  onTriggerIntervalChange: (value: string) => void
  onScheduledTriggerEnabledChange: (checked: boolean) => void
  onEnabledChange: (checked: boolean) => void
  onSaveTrader: () => void
}

export default function StrategyConfigForm({
  accountId,
  accountName,
  accountOptions,
  accountsLoading,
  selectedAccountLabel,
  error,
  success,
  exchange,
  signalPools,
  signalPoolIds,
  triggerInterval,
  scheduledTriggerEnabled,
  enabled,
  lastTriggerAt,
  saving,
  onAccountChange,
  onResetMessages,
  onExchangeChange,
  onSignalPoolIdsChange,
  onTriggerIntervalChange,
  onScheduledTriggerEnabledChange,
  onEnabledChange,
  onSaveTrader,
}: StrategyConfigFormProps) {
  const { t } = useTranslation()

  return (
    <>
      <section className="space-y-2">
        <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.selectTrader', 'Select Trader')}</div>
        {accountOptions.length > 0 ? (
          <Select
            value={accountId.toString()}
            onValueChange={(value) => {
              const nextId = Number(value)
              if (!Number.isFinite(nextId) || nextId === accountId) {
                return
              }
              onResetMessages()
              onAccountChange?.(nextId)
            }}
            disabled={accountsLoading}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={accountsLoading ? t('strategy.loadingTraders', 'Loading traders…') : t('strategy.selectAiTrader', 'Select AI trader')} />
            </SelectTrigger>
            <SelectContent>
              {accountOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <div className="text-sm text-muted-foreground">{accountName}</div>
        )}
      </section>

      <Card className="border-muted">
        <CardHeader className="pb-3">
          <div className="flex justify-between items-start">
            <div className="flex flex-col space-y-1.5">
              <CardTitle className="text-base">{t('strategy.traderConfig', 'Trader Configuration')}</CardTitle>
              <CardDescription className="text-xs">{t('strategy.settingsFor', 'Settings for')} {selectedAccountLabel}</CardDescription>
            </div>
            <div className="flex flex-col space-y-1">
              {error && <div className="text-sm text-destructive">{error}</div>}
              {success && <div className="text-sm text-green-500">{success}</div>}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <section className="space-y-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.exchange', 'Exchange')}</div>
            <Select
              value={exchange}
              onValueChange={(value) => {
                onExchangeChange(value)
                onResetMessages()
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t('strategy.selectExchange', 'Select exchange')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="binance">{t('strategy.exchangeBinance', 'Binance')}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{t('strategy.exchangeHint', 'Select exchange for market data and trade execution')}</p>
          </section>

          <section className="space-y-2">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.signalPools', 'Signal Pools')}</div>
            <div className="border rounded-md p-3 space-y-2 max-h-48 overflow-y-auto">
              {signalPools.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('strategy.noSignalPoolsAvailable', 'No signal pools available. Create one in the Signals tab.')}</p>
              ) : (
                signalPools.map((pool) => {
                  const isSelected = signalPoolIds.includes(pool.id)
                  return (
                    <label key={pool.id} className="flex items-center gap-2 cursor-pointer hover:bg-muted/50 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          onSignalPoolIdsChange((prev) =>
                            isSelected
                              ? prev.filter((id) => id !== pool.id)
                              : [...prev, pool.id]
                          )
                          onResetMessages()
                        }}
                        className="h-4 w-4"
                      />
                      <span className="text-sm">{pool.pool_name}</span>
                      <span className="text-xs text-muted-foreground">({pool.logic || 'OR'})</span>
                    </label>
                  )
                })
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {signalPoolIds.length > 0
                ? t('strategy.triggerWhenAnyMet', 'Trigger when ANY selected pool conditions are met (OR relationship)')
                : t('strategy.scheduledOnly', 'Only use scheduled interval trigger')}
            </p>
            {signalPoolIds.length > 1 && (
              <p className="text-xs text-yellow-600 dark:text-yellow-400">
                {t('strategy.multiPoolWarning', 'Note: If multiple pools trigger simultaneously, only the first will execute (others are ignored while running).')}
              </p>
            )}
          </section>

          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.triggerInterval', 'Trigger Interval (seconds)')}</div>
              <Switch checked={scheduledTriggerEnabled} onCheckedChange={onScheduledTriggerEnabledChange} />
            </div>
            <Input
              type="number"
              min={30}
              step={30}
              value={triggerInterval}
              disabled={!scheduledTriggerEnabled}
              onChange={(event) => {
                onTriggerIntervalChange(event.target.value)
                onResetMessages()
              }}
              className={!scheduledTriggerEnabled ? 'opacity-50' : ''}
            />
            <p className="text-xs text-muted-foreground">
              {scheduledTriggerEnabled
                ? t('strategy.triggerIntervalHint', 'Maximum time between triggers (default: 150s)')
                : t('strategy.scheduledTriggerDisabled', 'Scheduled trigger is disabled. AI will only run on signal pool triggers.')}
            </p>
          </section>

          <StrategyStatusCard
            enabled={enabled}
            scheduledTriggerEnabled={scheduledTriggerEnabled}
            signalPoolIds={signalPoolIds}
            lastTriggerAt={lastTriggerAt}
            onEnabledChange={onEnabledChange}
          />

          <Button onClick={onSaveTrader} disabled={saving} className="w-full">
            {saving ? t('strategy.saving', 'Saving…') : t('strategy.saveTraderConfig', 'Save Trader Config')}
          </Button>
        </CardContent>
      </Card>
    </>
  )
}
