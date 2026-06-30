import { useTranslation } from 'react-i18next'
import { Switch } from '@/components/ui/switch'
import RecentExecutionsList from './RecentExecutionsList'

interface StrategyStatusCardProps {
  enabled: boolean
  scheduledTriggerEnabled: boolean
  signalPoolIds: number[]
  lastTriggerAt: string | null
  onEnabledChange: (checked: boolean) => void
}

export default function StrategyStatusCard({
  enabled,
  scheduledTriggerEnabled,
  signalPoolIds,
  lastTriggerAt,
  onEnabledChange,
}: StrategyStatusCardProps) {
  const { t } = useTranslation()

  return (
    <>
      {!scheduledTriggerEnabled && signalPoolIds.length === 0 && (
        <div className="rounded-md bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 p-3">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            {t('strategy.noTriggerWarning', 'Warning: This AI Trader has no active trigger method. It will not execute any trades until you enable scheduled trigger or bind a signal pool.')}
          </p>
        </div>
      )}

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.strategyStatus', 'Strategy Status')}</div>
            <p className="text-xs text-muted-foreground">
              {enabled
                ? t('strategy.enabledDesc', 'Enabled: strategy reacts to signals and scheduled triggers.')
                : t('strategy.disabledDesc', 'Disabled: strategy will not auto-trade.')}
            </p>
          </div>
          <Switch checked={enabled} onCheckedChange={onEnabledChange} />
        </div>
      </section>

      <RecentExecutionsList lastTriggerAt={lastTriggerAt} />
    </>
  )
}
