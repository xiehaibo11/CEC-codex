import { useTranslation } from 'react-i18next'
import { formatTimestamp } from './formatters'

interface RecentExecutionsListProps {
  lastTriggerAt: string | null
}

export default function RecentExecutionsList({ lastTriggerAt }: RecentExecutionsListProps) {
  const { t } = useTranslation()

  return (
    <section className="space-y-1 text-sm">
      <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.lastTrigger', 'Last Trigger')}</div>
      <div className="text-xs">{formatTimestamp(lastTriggerAt)}</div>
    </section>
  )
}
