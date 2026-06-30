import type { HyperliquidBalance } from '@/lib/types/hyperliquid'
import type { AccountDetailTranslator } from './types'

interface AccountStatusSectionProps {
  balance: HyperliquidBalance
  isBinance: boolean
  t: AccountDetailTranslator
}

export default function AccountStatusSection({
  balance,
  isBinance,
  t,
}: AccountStatusSectionProps) {
  return (
    <div className="border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">{t('accountDetail.accountStatus', 'Account Status')}</h3>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.totalEquity', 'Total Equity')}</div>
          <div className="font-bold">${balance.totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.available', 'Available')}</div>
          <div className="font-medium text-green-600">${balance.availableBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">{t('accountDetail.usedMargin', 'Used Margin')}</div>
          <div className="font-medium">${balance.usedMargin.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
        </div>
      </div>
      {!isBinance && balance.walletAddress && (
        <div className="mt-3 pt-3 border-t">
          <div className="text-muted-foreground text-xs">{t('accountDetail.wallet', 'Wallet')}</div>
          <div className="font-mono text-xs">{balance.walletAddress}</div>
        </div>
      )}
    </div>
  )
}
