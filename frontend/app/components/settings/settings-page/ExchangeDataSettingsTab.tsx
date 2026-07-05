import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ExchangeIcon from '@/components/exchange/ExchangeIcon'
import DataCoverageHeatmap from '../DataCoverageHeatmap'
import type { ExchangeDataSettingsTabProps } from './types'

/** Data-collection panel shared by every exchange tab: storage stats,
 * retention, K-line backfill launcher with progress, plus market-flow and
 * per-period K-line coverage heatmaps. */
export function ExchangeDataSettingsTab({
  t,
  exchange,
  klinePeriods,
  backfillDescription,
  supportsBackfill = true,
  storageStats,
  storageLoading,
  retentionDays,
  setRetentionDays,
  retentionSaving,
  retentionError,
  retentionSuccess,
  backfillStatus,
  backfillStarting,
  backfillJustCompleted,
  onSaveRetention,
  onStartBackfill,
}: ExchangeDataSettingsTabProps) {
  const status = backfillStatus[exchange]
  const retention = retentionDays[exchange] || '365'
  const stats = storageStats[exchange] ?? {
    exchange,
    total_size_mb: 0,
    tables: {},
    retention_days: parseInt(retention, 10) || 365,
    symbol_count: 0,
    estimated_per_symbol_per_day_mb: 0,
  }

  return (
    <Card className="flex flex-col flex-1 min-h-0">
      <CardHeader className="shrink-0">
        <CardTitle className="flex items-center gap-2">
          <ExchangeIcon exchangeId={exchange} size={24} />
          {t('settings.dataCollection', 'Data Collection')}
        </CardTitle>
        <CardDescription>
          {t('settings.dataCollectionDesc', 'Market flow data storage statistics')}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0 space-y-6">
        {storageLoading ? (
          <div className="text-muted-foreground">{t('common.loading', 'Loading...')}</div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.currentStorage', 'Current Storage')}
                </div>
                <div className="text-xl font-semibold">{stats.total_size_mb} MB</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.collectedSymbols', 'Collected Symbols')}
                </div>
                <div className="text-xl font-semibold">{stats.symbol_count}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.retentionDays', 'Retention Days')}
                </div>
                <div className="text-xl font-semibold">{stats.retention_days}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.maxStorageEstimate', 'Max Storage Estimate')}
                </div>
                <div className="text-xl font-semibold">
                  {(Math.max(stats.symbol_count, 1) * parseInt(retention, 10) * stats.estimated_per_symbol_per_day_mb).toFixed(1)} MB
                </div>
              </div>
            </div>
            <div className="pt-4 border-t">
              <div className="text-sm font-medium mb-2">
                {t('settings.setRetention', 'Set Retention Period')}
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  value={retention}
                  onChange={(e) => setRetentionDays((prev) => ({ ...prev, [exchange]: e.target.value }))}
                  className="w-24"
                  min={7}
                  max={730}
                />
                <span className="text-sm text-muted-foreground">{t('settings.days', 'days')}</span>
                <Button onClick={onSaveRetention} disabled={retentionSaving} size="sm">
                  {retentionSaving ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
                </Button>
              </div>
              {retentionError && <div className="text-red-500 text-sm mt-2">{retentionError}</div>}
              {retentionSuccess && <div className="text-green-500 text-sm mt-2">{retentionSuccess}</div>}
              <div className="text-xs text-muted-foreground mt-1">
                {t('settings.retentionHint', 'Data older than this will be automatically cleaned up (7-730 days)')}
              </div>
            </div>
            {/* Backfill Section */}
            {supportsBackfill && (
            <div className="pt-4 border-t">
              <div className="text-sm font-medium mb-2">
                {t('settings.backfillHistory', 'Backfill Historical Data')}
              </div>
              <div className="text-xs text-muted-foreground mb-3">
                {backfillDescription}
              </div>
              <div className="text-xs text-amber-600 dark:text-amber-400 mb-3">
                {t('settings.flowNotBackfillable', 'Market flow (taker/orderbook) is collected live only and cannot be backfilled — coverage grows while the backend keeps running.')}
              </div>
              {status?.status === 'running' || status?.status === 'pending' ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-300"
                        style={{ width: `${status?.progress || 0}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium">{status?.progress || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                      {t('settings.backfillRunning', 'Backfilling')} {status?.symbols?.join(', ')}...
                    </div>
                    <Button
                      onClick={() => onStartBackfill(exchange, true)}
                      disabled={backfillStarting[exchange]}
                      size="sm"
                      variant="ghost"
                      className="h-6 px-2 text-xs"
                    >
                      {t('settings.restartBackfill', 'Restart')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <Button
                    onClick={() => onStartBackfill(exchange)}
                    disabled={backfillStarting[exchange]}
                    size="sm"
                    variant="outline"
                  >
                    {backfillStarting[exchange] ? t('common.loading', 'Loading...') : t('settings.startBackfill', 'Start Backfill')}
                  </Button>
                  {backfillJustCompleted[exchange] && (
                    <div className="text-xs text-green-500">
                      {t('settings.backfillCompleted', 'Last backfill completed successfully')}
                    </div>
                  )}
                  {status?.status === 'failed' && status?.task_id && (
                    <div className="text-xs text-red-500">
                      {t('settings.backfillFailed', 'Last backfill failed')}: {status?.error_message}
                    </div>
                  )}
                </div>
              )}
            </div>
            )}
          </div>
        )}
        <div className="pt-4 border-t">
          <div className="text-sm font-medium mb-3">{t('settings.marketFlowCoverage', 'Market Flow Coverage')}</div>
          <DataCoverageHeatmap exchange={exchange} dataType="market_flow" />
        </div>
        <div className="pt-4 border-t">
          <div className="text-sm font-medium mb-1">{t('settings.klineCoverage', 'K-line Coverage')}</div>
          <div className="text-xs text-muted-foreground mb-3">
            {klinePeriods.join(', ')}
          </div>
          <DataCoverageHeatmap
            exchange={exchange}
            dataType="klines"
            periodOptions={klinePeriods}
            defaultPeriod="1m"
          />
        </div>
      </CardContent>
    </Card>
  )
}
