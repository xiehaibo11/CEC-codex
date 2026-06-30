import { useTranslation } from 'react-i18next'
import { AlertTriangle, X } from 'lucide-react'

interface NoticeCardProps {
  onDismiss: () => void
}

export default function NoticeCard({ onDismiss }: NoticeCardProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-start gap-2 p-3 rounded-lg border border-amber-600/60 bg-amber-600/15">
      <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
      <p className="flex-1 text-sm text-amber-700 dark:text-amber-400">
        {t('attribution.notice')}
      </p>
      <button onClick={onDismiss} className="text-amber-600 hover:text-amber-700 dark:text-amber-500 dark:hover:text-amber-400 p-0.5">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
