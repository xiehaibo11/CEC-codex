import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getEventContractAttribution } from './api'
import type { EventContractAttributionResponse, EventContractDimensionRow } from './types'

export default function EventContractTab() {
  const { t } = useTranslation()
  const [data, setData] = useState<EventContractAttributionResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getEventContractAttribution()
      .then(res => {
        if (!cancelled) setData(res)
      })
      .catch(error => {
        console.error('Failed to load event contract attribution:', error)
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <div className="text-center py-8 text-muted-foreground">Loading...</div>
  }

  if (!data || data.overview.n === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground text-center">
            {t('attribution.eventContract.noData', 'No settled event contract bets yet')}
          </p>
        </CardContent>
      </Card>
    )
  }

  const { overview } = data

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('attribution.eventContract.settled', 'Settled')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.n}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('attribution.eventContract.decidedWinRate', 'Decided Win Rate')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.decided_win_rate.toFixed(1)}%</div>
            <div className="text-xs text-muted-foreground">
              {t('attribution.eventContract.ci', '95% CI')}: {overview.win_rate_ci_low.toFixed(1)}% – {overview.win_rate_ci_high.toFixed(1)}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('attribution.eventContract.record', 'Wins / Losses / Draws')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {overview.wins} / {overview.losses} / {overview.draws}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('attribution.eventContract.totalPnl', 'Total PnL')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${overview.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ${overview.total_pnl.toFixed(2)}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <DimensionCard
          title={t('attribution.eventContract.byDirection', 'By Direction')}
          labelHeader={t('attribution.eventContract.direction', 'Direction')}
          rows={data.by_direction}
        />
        <DimensionCard
          title={t('attribution.eventContract.byMarketState', 'By Market State')}
          labelHeader={t('attribution.eventContract.marketState', 'Market State')}
          rows={data.by_market_state}
        />
        <DimensionCard
          title={t('attribution.eventContract.byHourBucket', 'By Hour Bucket')}
          labelHeader={t('attribution.eventContract.hourBucket', 'Hour (UTC)')}
          rows={data.by_hour_bucket}
        />
      </div>
    </div>
  )
}

interface DimensionCardProps {
  title: string
  labelHeader: string
  rows: EventContractDimensionRow[]
}

function DimensionCard({ title, labelHeader, rows }: DimensionCardProps) {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? (
          <div className="text-muted-foreground text-sm p-4">
            {t('attribution.eventContract.noData', 'No settled event contract bets yet')}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="text-left p-2 font-medium">{labelHeader}</th>
                <th className="text-right p-2 font-medium">{t('attribution.eventContract.n', 'N')}</th>
                <th className="text-right p-2 font-medium">{t('attribution.winRate', 'Win Rate')}</th>
                <th className="text-right p-2 font-medium">{t('attribution.eventContract.pnl', 'PnL')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.key} className="border-b last:border-0">
                  <td className="p-2 font-medium">{row.key}</td>
                  <td className="p-2 text-right">{row.n}</td>
                  <td className="p-2 text-right">{row.win_rate.toFixed(1)}%</td>
                  <td className={`p-2 text-right ${row.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${row.pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}
