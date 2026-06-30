import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { SummaryResponse } from './types'

interface SummaryCardsProps {
  summary: SummaryResponse | null
}

export default function SummaryCards({ summary }: SummaryCardsProps) {
  const { t } = useTranslation()

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t('attribution.grossPnl', 'Gross PnL')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${(summary?.overview.total_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            ${summary?.overview.total_pnl?.toFixed(2) || '0.00'}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t('attribution.totalFees', 'Total Fees')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-orange-500">
            ${summary?.overview.total_fee?.toFixed(2) || '0.00'}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t('attribution.netPnl', 'Net PnL')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${(summary?.overview.net_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            ${summary?.overview.net_pnl?.toFixed(2) || '0.00'}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t('attribution.aiWinRate', 'AI Win Rate')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{((summary?.overview.win_rate || 0) * 100).toFixed(1)}%</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">{t('attribution.tradeCount', 'Trades')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{summary?.overview.trade_count || 0}</div>
        </CardContent>
      </Card>
    </div>
  )
}
