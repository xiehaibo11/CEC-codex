import { useTranslation } from 'react-i18next'
import { Loader2, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import ExchangeWalletsPanel from '@/components/trader/ExchangeWalletsPanel'
import { TraderAccountForm } from './TraderAccountForm'
import { TraderImportExportActions } from './TraderImportExportActions'
import type { AIAccount, AIAccountCreate } from './types'

interface TraderAccountCardProps {
  account: AIAccount
  isEditing: boolean
  editAccount: AIAccountCreate
  onEditAccountChange: (account: AIAccountCreate) => void
  onSaveEdit: () => void
  onCancelEdit: () => void
  loading: boolean
  testing: boolean
  testResult: string | null
  toggleLoadingId: number | null
  onToggleAutoTrading: (account: AIAccount, nextValue: boolean) => void
  onExport: (account: AIAccount) => void
  onImportClick: (account: AIAccount) => void
  onStartEdit: (account: AIAccount) => void
  onDeleteTrader: (account: AIAccount) => void
  onWalletConfigured: () => void
}

export function TraderAccountCard({
  account,
  isEditing,
  editAccount,
  onEditAccountChange,
  onSaveEdit,
  onCancelEdit,
  loading,
  testing,
  testResult,
  toggleLoadingId,
  onToggleAutoTrading,
  onExport,
  onImportClick,
  onStartEdit,
  onDeleteTrader,
  onWalletConfigured,
}: TraderAccountCardProps) {
  const { t } = useTranslation()

  return (
    <div className="border rounded-lg p-4 space-y-4">
      {isEditing ? (
        <TraderAccountForm
          mode="edit"
          account={editAccount}
          onAccountChange={onEditAccountChange}
          onSubmit={onSaveEdit}
          onCancel={onCancelEdit}
          loading={loading}
          testing={testing}
          testResult={testResult}
        />
      ) : (
        <>
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1 flex-1">
              <div className="font-medium">{account.name}</div>
              <div className="text-xs text-muted-foreground">
                {account.model ? `模型: ${account.model}` : '未配置模型'}
              </div>
              {account.base_url && (
                <div className="text-xs text-muted-foreground truncate">
                  基础URL: {account.base_url}
                </div>
              )}
              {account.api_key && (
                <div className="text-xs text-muted-foreground truncate max-w-full">
                  API密钥: {'*'.repeat(Math.min(20, Math.max(0, (account.api_key?.length || 0) - 4)))}{account.api_key?.slice(-4) || '****'}
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <div className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap">
                {toggleLoadingId === account.id && (
                  <Loader2 className="h-3 w-3 animate-spin" />
                )}
                <span>启动交易</span>
                <Switch
                  checked={account.auto_trading_enabled ?? true}
                  disabled={toggleLoadingId === account.id || loading}
                  onCheckedChange={(checked) => onToggleAutoTrading(account, checked)}
                />
              </div>
              <div className="flex items-center gap-1">
                <TraderImportExportActions
                  account={account}
                  onExport={onExport}
                  onImportClick={onImportClick}
                />
                <Button
                  onClick={() => onStartEdit(account)}
                  variant="outline"
                  size="sm"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  onClick={() => onDeleteTrader(account)}
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  title={t('trader.deleteTrader')}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          <ExchangeWalletsPanel
            accountId={account.id}
            accountName={account.name}
            onWalletConfigured={onWalletConfigured}
          />
        </>
      )}
    </div>
  )
}
