import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CheckCircle, Eye, EyeOff, RefreshCw, Trash2, Wallet } from 'lucide-react'
import { copyToClipboard } from '@/lib/utils'
import { detectInputType, formatPrivateKey } from './privateKeyInput'
import type { WalletData, WalletEnvironment } from './types'

interface HyperliquidWalletBlockProps {
  environment: WalletEnvironment
  wallet: WalletData | null
  editing: boolean
  setEditing: (value: boolean) => void
  privateKey: string
  setPrivateKey: (value: string) => void
  maxLeverage: number
  setMaxLeverage: (value: number) => void
  defaultLeverage: number
  setDefaultLeverage: (value: number) => void
  showKey: boolean
  setShowKey: (value: boolean) => void
  testing: boolean
  loading: boolean
  inputWarning: string | null
  setInputWarning: (value: string | null) => void
  onSaveWallet: (environment: WalletEnvironment) => void
  onTestConnection: (environment: WalletEnvironment) => void
  onDeleteWallet: (environment: WalletEnvironment) => void
}

export function HyperliquidWalletBlock({
  environment,
  wallet,
  editing,
  setEditing,
  privateKey,
  setPrivateKey,
  maxLeverage,
  setMaxLeverage,
  defaultLeverage,
  setDefaultLeverage,
  showKey,
  setShowKey,
  testing,
  loading,
  inputWarning,
  setInputWarning,
  onSaveWallet,
  onTestConnection,
  onDeleteWallet,
}: HyperliquidWalletBlockProps) {
  const { t } = useTranslation()
  const envName = environment === 'testnet' ? 'Testnet' : 'Mainnet'
  const badgeVariant = environment === 'testnet' ? 'default' : 'destructive'

  return (
    <div className="p-4 border rounded-lg space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-muted-foreground" />
          <Badge variant={badgeVariant} className="text-xs">
            {environment === 'testnet' ? 'TESTNET' : 'MAINNET'}
          </Badge>
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
              disabled={loading}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>

      {wallet && !editing ? (
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">
              {t('wallet.walletAddress', 'Wallet Address')}
            </label>
            <div className="flex items-center gap-2">
              <code
                className="flex-1 px-2 py-1 bg-muted rounded text-xs"
                style={{ maxWidth: '100%', overflow: 'hidden' }}
              >
                {wallet.walletAddress}
              </code>
              <button
                onClick={async () => {
                  const success = await copyToClipboard(wallet.walletAddress || '')
                  if (success) {
                    toast.success(t('wallet.addressCopied', 'Wallet address copied to clipboard'))
                  } else {
                    toast.error(t('wallet.copyFailed', 'Failed to copy'))
                  }
                }}
                className="cursor-pointer"
                title={t('wallet.copyAddress', 'Copy wallet address')}
              >
                <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
              </button>
            </div>
          </div>

          {wallet.balance && (
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <div className="text-muted-foreground">{t('wallet.balance', 'Balance')}</div>
                <div className="font-medium">${wallet.balance.totalEquity.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">{t('wallet.available', 'Available')}</div>
                <div className="font-medium">${wallet.balance.availableBalance.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-muted-foreground">{t('wallet.margin', 'Margin')}</div>
                <div className="font-medium">{wallet.balance.marginUsagePercent.toFixed(1)}%</div>
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
            <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs">
              <p className="text-yellow-800">
                ⚠️{' '}
                {t('wallet.noWalletConfigured', 'No {{env}} wallet configured.', {
                  env: envName.toLowerCase(),
                })}
              </p>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">
              {t('wallet.privateKey', 'Private Key')}
            </label>
            <div className="flex gap-2">
              <Input
                type={showKey ? 'text' : 'password'}
                value={privateKey}
                onChange={(event) => {
                  const value = event.target.value
                  setPrivateKey(value)
                  const inputType = detectInputType(value)
                  if (inputType === 'wallet_address') {
                    setInputWarning(
                      t(
                        'wallet.addressWarning',
                        'This looks like a wallet ADDRESS (40 chars), not a private key (64 chars).',
                      ),
                    )
                  } else if (inputType === 'invalid' && value.trim()) {
                    setInputWarning(
                      t('wallet.invalidFormat', 'Invalid format. Private key must be 64 hex characters.'),
                    )
                  } else {
                    setInputWarning(null)
                  }
                }}
                onBlur={(event) => {
                  const formatted = formatPrivateKey(event.target.value)
                  if (formatted !== privateKey && detectInputType(formatted) === 'valid_key') {
                    setPrivateKey(formatted)
                    toast.success(t('wallet.prefixAdded', 'Added 0x prefix automatically'))
                  }
                }}
                placeholder={t('wallet.privateKeyPlaceholder', '0x... or paste without 0x prefix')}
                className={`font-mono text-xs h-8 ${inputWarning ? 'border-red-500' : ''}`}
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
            {inputWarning && <p className="text-xs text-red-500">{inputWarning}</p>}
            <p className="text-xs text-muted-foreground">
              {t(
                'wallet.privateKeyHint',
                '64 hex chars (0x auto-added). DEX needs private key to sign on-chain transactions.',
              )}
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
                max={50}
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
              disabled={loading}
              size="sm"
              className="flex-1 h-8 text-xs"
            >
              {loading ? (
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
                  setPrivateKey('')
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
