import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CheckCircle, Eye, EyeOff, RefreshCw, Trash2, Wallet } from 'lucide-react'
import type {
  BinanceWalletData,
  BinanceWalletEnvironment,
  MainnetQuota,
} from './types'

interface BinanceWalletBlockProps {
  platformName?: string
  apiKeyLabel?: string
  secretKeyLabel?: string
  credentialHint?: string
  positionModeHint?: string
  authenticationHint?: string
  environment: BinanceWalletEnvironment
  wallet: BinanceWalletData | null
  editing: boolean
  setEditing: (value: boolean) => void
  apiKey: string
  setApiKey: (value: string) => void
  secretKey: string
  setSecretKey: (value: string) => void
  maxLeverage: number
  setMaxLeverage: (value: number) => void
  defaultLeverage: number
  setDefaultLeverage: (value: number) => void
  showKey: boolean
  setShowKey: (value: boolean) => void
  saving: boolean
  testing: boolean
  quota?: MainnetQuota | null
  onSaveWallet: (environment: BinanceWalletEnvironment) => void
  onTestConnection: (environment: BinanceWalletEnvironment) => void
  onDeleteWallet: (environment: BinanceWalletEnvironment) => void
}

export function BinanceWalletBlock({
  platformName = 'Binance',
  apiKeyLabel = 'API Key',
  secretKeyLabel = 'Secret Key',
  credentialHint: customCredentialHint,
  positionModeHint,
  authenticationHint,
  environment,
  wallet,
  editing,
  setEditing,
  apiKey,
  setApiKey,
  secretKey,
  setSecretKey,
  maxLeverage,
  setMaxLeverage,
  defaultLeverage,
  setDefaultLeverage,
  showKey,
  setShowKey,
  saving,
  testing,
  quota,
  onSaveWallet,
  onTestConnection,
  onDeleteWallet,
}: BinanceWalletBlockProps) {
  const { t } = useTranslation()
  const envName = environment === 'testnet' ? 'Testnet' : 'Mainnet'
  const badgeVariant = environment === 'testnet' ? 'default' : 'destructive'
  const credentialHint =
    customCredentialHint ||
    (environment === 'testnet'
      ? 'Use Binance Futures Demo Trading API keys here. Mainnet, Spot Testnet, and old Mock Trading keys will be rejected.'
      : 'Use Binance USD-M Futures Mainnet API keys here. Enable Futures read/trading permission; if IP-restricted, whitelist this server IP.')
  const positionHint = positionModeHint ?? t(
    'binance.positionModeHint',
    'Requires One-way Position Mode. Go to Binance App → Futures → Settings → Position Mode → One-way Mode',
  )
  const authHint = authenticationHint ?? 'CEX uses API credentials for authentication. The key must match this environment.'

  return (
    <div className="p-4 border rounded-lg space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-muted-foreground" />
          <Badge variant={badgeVariant} className="text-xs">
            {environment === 'testnet' ? 'TESTNET' : 'MAINNET'}
          </Badge>
          {environment === 'mainnet' && quota && (
            <span
              className="text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded-full"
              title={t('binance.continueLimitedDescription')}
            >
              {t('quota.executionQuota', 'Quota')}: {quota.remaining}/{quota.limit}
            </span>
          )}
        </div>
        {wallet && !editing && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              {t('common.edit', 'Edit')}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => onDeleteWallet(environment)}
              disabled={saving}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>

      {wallet && !editing ? (
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">API Key</label>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-2 py-1 bg-muted rounded text-xs overflow-hidden">
                {wallet.apiKeyMasked || '****'}
              </code>
              <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
            </div>
          </div>

          {wallet.balance && (
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-muted-foreground">{t('wallet.balance', 'Balance')}</div>
                <div className="font-medium">${wallet.balance.total_equity?.toFixed(2) || '0.00'}</div>
              </div>
              <div>
                <div className="text-muted-foreground">{t('wallet.available', 'Available')}</div>
                <div className="font-medium">${wallet.balance.available_balance?.toFixed(2) || '0.00'}</div>
              </div>
              <div>
                <div className="text-muted-foreground">PnL</div>
                <div
                  className={`font-medium ${
                    (wallet.balance.unrealized_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  ${wallet.balance.unrealized_pnl?.toFixed(2) || '0.00'}
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-muted-foreground">{t('wallet.maxLeverage', 'Max Leverage')}</div>
              <div className="font-medium">{wallet.maxLeverage}x</div>
            </div>
            <div>
              <div className="text-muted-foreground">
                {t('wallet.defaultLeverage', 'Default Leverage')}
              </div>
              <div className="font-medium">{wallet.defaultLeverage}x</div>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onTestConnection(environment)}
            disabled={testing}
            className="w-full"
          >
            {testing ? (
              <>
                <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                {t('wallet.testing', 'Testing...')}
              </>
            ) : (
              t('wallet.testConnection', 'Test Connection')
            )}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {!wallet && (
            <div className="p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded text-xs">
              <p className="text-yellow-800 dark:text-yellow-200">
                ⚠️ No {envName.toLowerCase()} API configured.
              </p>
            </div>
          )}

          <div className="p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded text-xs">
            <p className="text-blue-800 dark:text-blue-200 mb-1">{credentialHint}</p>
            <p className="text-blue-800 dark:text-blue-200">
              {positionHint}
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">{apiKeyLabel}</label>
            <Input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={`Enter your ${platformName} ${apiKeyLabel}`}
              className="font-mono text-xs h-8"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">{secretKeyLabel}</label>
            <div className="flex gap-2">
              <Input
                type={showKey ? 'text' : 'password'}
                value={secretKey}
                onChange={(event) => setSecretKey(event.target.value)}
                placeholder={`Enter your ${platformName} ${secretKeyLabel}`}
                className="font-mono text-xs h-8"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowKey(!showKey)}
                className="h-8 px-2"
              >
                {showKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {authHint}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t('wallet.maxLeverage', 'Max Leverage')}
              </label>
              <Input
                type="number"
                value={maxLeverage}
                onChange={(event) => setMaxLeverage(Number(event.target.value))}
                min={1}
                max={125}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t('wallet.defaultLeverage', 'Default Leverage')}
              </label>
              <Input
                type="number"
                value={defaultLeverage}
                onChange={(event) => setDefaultLeverage(Number(event.target.value))}
                min={1}
                max={maxLeverage}
                className="h-8 text-xs"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={() => onSaveWallet(environment)}
              disabled={saving}
              size="sm"
              className="flex-1 h-8 text-xs"
            >
              {saving ? (
                <>
                  <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                  {t('wallet.saving', 'Saving...')}
                </>
              ) : (
                t('wallet.saveWallet', 'Save Wallet')
              )}
            </Button>
            {editing && (
              <Button
                variant="outline"
                onClick={() => {
                  setEditing(false)
                  setApiKey('')
                  setSecretKey('')
                }}
                size="sm"
                className="h-8 text-xs"
              >
                {t('common.cancel', 'Cancel')}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
