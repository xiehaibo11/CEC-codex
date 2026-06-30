import { useTranslation } from 'react-i18next'
import WalletSelector from '../../hyperliquid/WalletSelector'
import type { PositionItem, WalletOption } from './types'

interface RiskPanelProps {
  symbol: string
  selectedWallet: WalletOption | null
  positions: PositionItem[]
  positionsLoading: boolean
  onSelectWallet: (wallet: WalletOption) => void
}

function PositionLoadingIndicator() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 38 38" stroke="currentColor" className="w-4 h-4 text-primary">
      <g fill="none" fillRule="evenodd">
        <g transform="translate(1 1)" strokeWidth="2">
          <circle strokeOpacity=".3" cx="18" cy="18" r="18" />
          <path d="M36 18c0-9.94-8.06-18-18-18">
            <animateTransform attributeName="transform" type="rotate" from="0 18 18" to="360 18 18" dur="0.8s" repeatCount="indefinite" />
          </path>
        </g>
      </g>
    </svg>
  )
}

export function RiskPanel({
  symbol,
  selectedWallet,
  positions,
  positionsLoading,
  onSelectWallet,
}: RiskPanelProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-2">
      <label className="text-xs text-muted-foreground block">{t('kline.analysis.tradingWallet', 'Trading Wallet (for positions context)')}</label>
      <WalletSelector
        selectedWalletId={selectedWallet?.wallet_id || null}
        onSelect={onSelectWallet}
        showLabel={false}
      />
      {selectedWallet && (
        <div className="rounded-md border p-3 space-y-2 bg-muted/40">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{t('kline.analysis.wallet', 'Wallet')}</span>
            <span className="font-medium">{selectedWallet.account_name} ({selectedWallet.environment})</span>
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {positionsLoading && (
              <div className="text-xs text-muted-foreground flex items-center gap-2">
                <PositionLoadingIndicator />
                {t('kline.analysis.loadingPositions', 'Loading positions...')}
              </div>
            )}
            {!positionsLoading && positions.length === 0 && (
              <div className="text-xs text-muted-foreground">{t('kline.analysis.noPositions', 'No open positions')}</div>
            )}
            {!positionsLoading && positions.length > 0 && positions.map((position, index) => {
              const fallbackSymbol = symbol || 'N/A'
              const displaySymbol = position.symbol || fallbackSymbol
              const side = (position.side || '').toUpperCase()
              const size = position.size ?? '-'
              const value = position.position_value ?? '-'
              const pnl = position.unrealized_pnl ?? '-'
              const pnlPct = position.pnl_percentage ?? null
              const leverage = position.leverage ?? null

              return (
                <div key={index} className="text-[11px] border-b last:border-b-0 py-1">
                  <div className="flex justify-between">
                    <span className="font-medium">{displaySymbol}</span>
                    <span className="text-muted-foreground">{side} {size}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>Value: {value}</span>
                    <span>{leverage ? `${leverage}x` : ''}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>PnL: {pnl}</span>
                    <span>{pnlPct !== null && pnlPct !== undefined ? `(${pnlPct}%)` : ''}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
