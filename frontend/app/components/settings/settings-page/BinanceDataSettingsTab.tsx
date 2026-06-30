import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ExchangeIcon from '@/components/exchange/ExchangeIcon'
import DataCoverageHeatmap from '../DataCoverageHeatmap'
import { BINANCE_KLINE_PERIODS } from './constants'
import type { BinanceDataSettingsTabProps } from './types'

export function BinanceDataSettingsTab({
  t,
  watchlistSymbols,
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
}: BinanceDataSettingsTabProps) {
  return (
    <Card className="flex flex-col flex-1 min-h-0">
      <CardHeader className="shrink-0">
        <CardTitle className="flex items-center gap-2">
          <ExchangeIcon exchangeId="binance" size={24} />
          {t('settings.dataCollection', 'Data Collection')}
        </CardTitle>
        <CardDescription>
          {t('settings.dataCollectionDesc', 'Market flow data storage statistics')}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0 space-y-6">
        {storageLoading ? (
          <div className="text-muted-foreground">{t('common.loading', 'Loading...')}</div>
        ) : storageStats['binance'] ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.currentStorage', 'Current Storage')}
                </div>
                <div className="text-xl font-semibold">{storageStats['binance'].total_size_mb} MB</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.collectedSymbols', 'Collected Symbols')}
                </div>
                <div className="text-xl font-semibold">{storageStats['binance'].symbol_count}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.retentionDays', 'Retention Days')}
                </div>
                <div className="text-xl font-semibold">{storageStats['binance'].retention_days}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">
                  {t('settings.maxStorageEstimate', 'Max Storage Estimate')}
                </div>
                <div className="text-xl font-semibold">
                  {(watchlistSymbols.length * parseInt(retentionDays['binance'] || '365', 10) * storageStats['binance'].estimated_per_symbol_per_day_mb).toFixed(1)} MB
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
                  value={retentionDays['binance'] || '365'}
                  onChange={(e) => setRetentionDays((prev) => ({ ...prev, binance: e.target.value }))}
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
            <div className="pt-4 border-t">
              <div className="text-sm font-medium mb-2">
                {t('settings.backfillHistory', 'Backfill Historical Data')}
              </div>
              <div className="text-xs text-muted-foreground mb-3">
                {t('settings.backfillDesc', 'K-lines 1m-1M for the retention period, OI (real-time only), Funding Rate (365d), Long/Short Ratio (30d)')}
              </div>
              {backfillStatus['binance']?.status === 'running' || backfillStatus['binance']?.status === 'pending' ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-300"
                        style={{ width: `${backfillStatus['binance']?.progress || 0}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium">{backfillStatus['binance']?.progress || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                      {t('settings.backfillRunning', 'Backfilling')} {backfillStatus['binance']?.symbols?.join(', ')}...
                    </div>
                    <Button
                      onClick={() => onStartBackfill('binance', true)}
                      disabled={backfillStarting['binance']}
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
                    onClick={() => onStartBackfill('binance')}
                    disabled={backfillStarting['binance']}
                    size="sm"
                    variant="outline"
                  >
                    {backfillStarting['binance'] ? t('common.loading', 'Loading...') : t('settings.startBackfill', 'Start Backfill')}
                  </Button>
                  {backfillJustCompleted['binance'] && (
                    <div className="text-xs text-green-500">
                      {t('settings.backfillCompleted', 'Last backfill completed successfully')}
                    </div>
                  )}
                  {backfillStatus['binance']?.status === 'failed' && backfillStatus['binance']?.task_id && (
                    <div className="text-xs text-red-500">
                      {t('settings.backfillFailed', 'Last backfill failed')}: {backfillStatus['binance']?.error_message}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-muted-foreground">{t('settings.noData', 'No data available')}</div>
        )}
        <div className="pt-4 border-t">
          <div className="text-sm font-medium mb-3">{t('settings.marketFlowCoverage', 'Market Flow Coverage')}</div>
          <DataCoverageHeatmap exchange="binance" dataType="market_flow" />
        </div>
        <div className="pt-4 border-t">
          <div className="text-sm font-medium mb-1">{t('settings.klineCoverage', 'K-line Coverage')}</div>
          <div className="text-xs text-muted-foreground mb-3">
            {BINANCE_KLINE_PERIODS.join(', ')}
          </div>
          <DataCoverageHeatmap
            exchange="binance"
            dataType="klines"
            periodOptions={BINANCE_KLINE_PERIODS}
            defaultPeriod="1m"
          />
        </div>
      </CardContent>
    </Card>
  )
}
