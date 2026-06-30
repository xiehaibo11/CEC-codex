import { useTranslation } from 'react-i18next'
import { Download, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { AIAccount } from './types'

interface TraderImportExportActionsProps {
  account: AIAccount
  onExport: (account: AIAccount) => void
  onImportClick: (account: AIAccount) => void
}

export function TraderImportExportActions({
  account,
  onExport,
  onImportClick,
}: TraderImportExportActionsProps) {
  const { t } = useTranslation()

  return (
    <>
      <Button
        onClick={() => onExport(account)}
        variant="outline"
        size="sm"
        title={t('traderData.export')}
      >
        <Download className="h-4 w-4" />
      </Button>
      <Button
        onClick={() => onImportClick(account)}
        variant="outline"
        size="sm"
        title={t('traderData.import')}
      >
        <Upload className="h-4 w-4" />
      </Button>
    </>
  )
}
