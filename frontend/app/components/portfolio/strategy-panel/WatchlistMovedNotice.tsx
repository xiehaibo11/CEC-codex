import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

interface WatchlistMovedNoticeProps {
  watchlistSymbols: string[]
}

export default function WatchlistMovedNotice({ watchlistSymbols }: WatchlistMovedNoticeProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="text-muted-foreground mb-4">
        {t('strategy.watchlistMoved', 'Watchlist management has been moved to Settings.')}
      </div>
      <div className="text-sm text-muted-foreground mb-4">
        {t('strategy.currentWatchlist', 'Current watchlist')}: {watchlistSymbols.join(', ') || '—'}
      </div>
      <Button
        variant="outline"
        onClick={() => {
          window.location.hash = 'settings'
          window.location.reload()
        }}
      >
        {t('strategy.goToSettings', 'Go to Settings')}
      </Button>
    </div>
  )
}
