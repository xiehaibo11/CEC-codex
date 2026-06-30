import { Plus, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { SignalTranslate, WalletTrackingRuntimeStatus } from './types'
import { formatWalletRuntimeTime, formatWalletTier } from './wallet-formatters'

interface WalletRuntimePanelProps {
  walletRuntime: WalletTrackingRuntimeStatus | null
  walletRuntimeLoading: boolean
  t: SignalTranslate
  onRefresh: () => void
  onCreateWalletPool: () => void
}

export function WalletRuntimePanel({
  walletRuntime,
  walletRuntimeLoading,
  t,
  onRefresh,
  onCreateWalletPool,
}: WalletRuntimePanelProps) {
  const connected = walletRuntime?.status === 'connected'
  const error = walletRuntime?.status === 'error'
  const configured = Boolean(walletRuntime?.configured)
  const syncedWalletCount = walletRuntime?.synced_addresses?.length || 0
  const statusClass = connected
    ? 'bg-emerald-500/10 text-emerald-600'
    : error
      ? 'bg-red-500/10 text-red-600'
      : configured
        ? 'bg-amber-500/10 text-amber-600'
        : 'bg-muted text-muted-foreground'
  const statusLabel = connected
    ? (syncedWalletCount > 0
      ? t('signals.walletTracking.connected', 'Connected')
      : t('signals.walletTracking.connectedNoWallets', 'Connected · No CoinGlass wallets'))
    : error
      ? t('signals.walletTracking.error', 'Error')
      : configured
        ? t('signals.walletTracking.connecting', 'Loading')
        : t('signals.walletTracking.notConfigured', 'CoinGlass key not configured')

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-lg border bg-muted/30 p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm font-medium">{t('signals.walletTracking.connectionStatus', 'Connection Status')}</div>
              <div className="text-xs text-muted-foreground">{t('signals.walletTracking.connectionHint', 'CoinGlass wallet tracking uses the CoinGlass key configured on the CoinGlass page and keeps available Hyperliquid wallet addresses ready for pool selection.')}</div>
            </div>
            <span className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${statusClass}`}>
              {connected ? (
                <Wifi className="w-3 h-3" />
              ) : error ? (
                <WifiOff className="w-3 h-3" />
              ) : configured ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <WifiOff className="w-3 h-3" />
              )}
              {statusLabel}
            </span>
          </div>
          <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
            <div>{t('signals.walletTracking.source', 'Source')}: <span className="text-foreground">CoinGlass</span></div>
            <div>{t('signals.walletTracking.tier', 'Plan')}: <span className="text-foreground">{formatWalletTier(t, walletRuntime?.tier)}</span></div>
            <div>{t('signals.walletTracking.syncedWalletCount', 'CoinGlass wallets')}: <span className="text-foreground">{syncedWalletCount}</span></div>
            <div>{t('signals.walletTracking.lastEventAt', 'Last event')}: <span className="text-foreground">{formatWalletRuntimeTime(walletRuntime?.last_event_at)}</span></div>
          </div>
          {walletRuntime?.last_error && (
            <div className="mt-3 text-xs text-red-500">
              {t('signals.walletTracking.lastError', 'Last error')}: {walletRuntime.last_error}
            </div>
          )}
        </div>

        <div className="rounded-lg border p-4 space-y-3">
          <div className="text-sm font-medium">{t('signals.walletTracking.syncedWallets', 'Synced Wallets')}</div>
          {walletRuntimeLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <RefreshCw className="w-4 h-4 animate-spin" />
              {t('signals.walletTracking.loading', 'Loading...')}
            </div>
          ) : syncedWalletCount ? (
            <div className="flex flex-wrap gap-2">
              {walletRuntime?.synced_addresses.map(address => (
                <span key={address} className="rounded-md border px-2 py-1 text-xs">
                  {address}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t('signals.walletTracking.noSyncedWallets', 'No CoinGlass wallet addresses are available yet. Configure a CoinGlass key or refresh later.')}
            </p>
          )}
        </div>
      </div>

      <div className="flex gap-2">
        <Button asChild variant="outline" size="sm">
          <a href="#coinglass">
            {t('signals.walletTracking.manageOnCoinGlass', 'Configure CoinGlass')}
          </a>
        </Button>
        <Button onClick={onRefresh} size="sm" variant="outline" disabled={walletRuntimeLoading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${walletRuntimeLoading ? 'animate-spin' : ''}`} />
          {t('signals.walletTracking.refresh', 'Refresh')}
        </Button>
        <Button onClick={onCreateWalletPool} size="sm">
          <Plus className="w-4 h-4 mr-2" />
          {t('signals.walletTracking.createWalletPool', 'Create Wallet Pool')}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        {t('signals.walletTracking.inlineHint', 'CoinGlass wallet addresses are pulled through the server-side CoinGlass API. Choose which addresses should enter HAA signal pools after they appear.')}
      </p>
    </>
  )
}
