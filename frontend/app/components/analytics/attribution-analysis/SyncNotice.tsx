import { useTranslation } from 'react-i18next'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface SyncNoticeProps {
  unsyncCount: number
  syncing: boolean
  onSync: () => void
}

export default function SyncNotice({ unsyncCount, syncing, onSync }: SyncNoticeProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-orange-500/60 bg-orange-500/15">
      <RefreshCw className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0" />
      <p className="flex-1 text-sm text-orange-700 dark:text-orange-300">
        {t('attribution.syncWarning', { count: unsyncCount })}
      </p>
      <Button
        size="sm"
        variant="outline"
        onClick={onSync}
        disabled={syncing}
        className="border-orange-500/60 text-orange-700 hover:bg-orange-500/20 dark:text-orange-300"
      >
        {syncing ? (
          <>
            <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
            {t('attribution.syncing', 'Syncing...')}
          </>
        ) : (
          t('attribution.syncPnl', 'Sync PnL Data')
        )}
      </Button>
    </div>
  )
}
