import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import type { NewsSourceAdapter, NewsSourcesSettingsTabProps } from './types'

export function NewsSourcesSettingsTab({
  t,
  newsSources,
  newsStats,
  newsLoading,
  newsSaving,
  newsError,
  newsSuccess,
  enabledNewsSourceCount,
  hasUnsavedNewsSources,
  newsCountsByDomain,
  newsFormAdapter,
  newsTestUrl,
  newsFormInterval,
  newsFormAuthToken,
  newsFormApiKey,
  newsTesting,
  newsTestError,
  newsTestResult,
  formatDateTime,
  extractDomain,
  onToggleNewsSource,
  onSaveNewsSources,
  onRefreshNewsSources,
  onNewsSourceIntervalChange,
  onNewsFormAdapterChange,
  onNewsFormIntervalChange,
  onNewsFormAuthTokenChange,
  onNewsFormApiKeyChange,
  onNewsTestUrlChange,
  onTestNewsSource,
  onAddNewsSource,
}: NewsSourcesSettingsTabProps) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="shrink-0">
          <CardTitle>{t('settings.newsSources', 'News Sources')}</CardTitle>
          <CardDescription>
            {t('settings.newsSourcesDesc', 'Manage RSS sources and review collection health')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {newsLoading ? (
            <div className="text-muted-foreground text-sm">{t('common.loading', 'Loading...')}</div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-muted-foreground">
                    {t('settings.newsTotalArticles', 'Total Articles')}
                  </div>
                  <div className="text-xl font-semibold">{newsStats?.total_articles ?? 0}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">
                    {t('settings.newsLast24h', 'New in 24h')}
                  </div>
                  <div className="text-xl font-semibold">{newsStats?.last_24h?.total ?? 0}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">
                    {t('settings.newsEnabledSources', 'Enabled Sources')}
                  </div>
                  <div className="text-xl font-semibold">{enabledNewsSourceCount}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">
                    {t('settings.newsLatestCollected', 'Latest Article')}
                  </div>
                  <div className="text-sm font-medium break-words">
                    {formatDateTime(newsStats?.latest_article_at)}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t space-y-3">
                <div className="text-sm font-medium">
                  {t('settings.newsConfiguredSources', 'Configured Sources')}
                </div>
                {newsSources.length === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    {t('settings.newsNoSources', 'No news sources configured')}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {newsSources.map((source, index) => {
                      const domain = extractDomain(source.url)
                      const last24hCount = newsCountsByDomain[domain] ?? 0
                      return (
                        <div
                          key={`${source.url}-${index}`}
                          className="flex flex-col gap-3 rounded-lg border p-3 md:flex-row md:items-center md:justify-between"
                        >
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                                {domain}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {t('settings.newsCollected24h', '{{count}} in 24h', { count: last24hCount })}
                              </span>
                            </div>
                            <div className="truncate text-sm text-muted-foreground">
                              {source.url}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {t('settings.newsIntervalSeconds', 'Interval')}: {source.interval_seconds}s
                            </div>
                          </div>
                          <div className="flex items-center gap-3 flex-wrap md:flex-nowrap">
                            <Input
                              type="number"
                              min={10}
                              className="w-24 h-8 text-xs"
                              value={source.interval_seconds}
                              onChange={(e) => onNewsSourceIntervalChange(index, e.target.value)}
                            />
                            <span className="text-xs text-muted-foreground">
                              {source.enabled
                                ? t('settings.enabled', 'Enabled')
                                : t('settings.disabled', 'Disabled')}
                            </span>
                            <Switch
                              checked={source.enabled}
                              onCheckedChange={(checked) => onToggleNewsSource(index, checked)}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
        <CardFooter className="border-t pt-3 flex items-center gap-3">
          <Button
            size="sm"
            onClick={onSaveNewsSources}
            disabled={newsLoading || newsSaving || !hasUnsavedNewsSources}
          >
            {newsSaving ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={onRefreshNewsSources}
            disabled={newsLoading || newsSaving}
          >
            {t('common.refresh', 'Refresh')}
          </Button>
          {newsError && <span className="text-red-500 text-xs">{newsError}</span>}
          {newsSuccess && <span className="text-green-500 text-xs">{newsSuccess}</span>}
        </CardFooter>
      </Card>

      <Card>
        <CardHeader className="shrink-0">
          <CardTitle>{t('settings.addNewsSource', 'Add New Source')}</CardTitle>
          <CardDescription>
            {t('settings.addNewsSourceDesc', 'Test an RSS feed before adding it to the source list')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground">{t('settings.newsSourceType', 'Source Type')}</div>
              <Select
                value={newsFormAdapter}
                onValueChange={(value: NewsSourceAdapter) => onNewsFormAdapterChange(value)}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rss_generic">RSS / Atom</SelectItem>
                  <SelectItem value="cryptopanic">CryptoPanic</SelectItem>
                  <SelectItem value="finnhub_calendar">Finnhub Calendar</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground">{t('settings.newsIntervalSeconds', 'Interval')}</div>
              <Input
                type="number"
                min={10}
                value={newsFormInterval}
                onChange={(e) => onNewsFormIntervalChange(e.target.value)}
              />
            </div>
            {newsFormAdapter === 'cryptopanic' && (
              <div className="space-y-2 md:col-span-2">
                <div className="text-xs text-muted-foreground">{t('settings.newsAuthToken', 'Auth Token')}</div>
                <Input
                  type="password"
                  value={newsFormAuthToken}
                  onChange={(e) => onNewsFormAuthTokenChange(e.target.value)}
                />
              </div>
            )}
            {newsFormAdapter === 'finnhub_calendar' && (
              <div className="space-y-2 md:col-span-2">
                <div className="text-xs text-muted-foreground">{t('settings.newsApiKey', 'API Key')}</div>
                <Input
                  type="password"
                  value={newsFormApiKey}
                  onChange={(e) => onNewsFormApiKeyChange(e.target.value)}
                />
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 md:flex-row">
            <Input
              type="url"
              placeholder={t('settings.newsSourceUrlPlaceholder', 'https://example.com/rss')}
              value={newsTestUrl}
              onChange={(e) => onNewsTestUrlChange(e.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              onClick={onTestNewsSource}
              disabled={newsTesting}
            >
              {newsTesting ? t('settings.testing', 'Testing...') : t('settings.test', 'Test')}
            </Button>
            <Button
              type="button"
              onClick={onAddNewsSource}
              disabled={!newsTestResult?.success}
            >
              {t('settings.add', 'Add')}
            </Button>
          </div>

          {newsTestError && (
            <div className="text-sm text-red-500">{newsTestError}</div>
          )}

          {newsTestResult?.success && (
            <div className="rounded-lg border p-4 space-y-3">
              <div className="text-sm font-medium">
                {t('settings.newsSourceTestSuccess', 'Fetched {{count}} articles', {
                  count: newsTestResult.total_fetched ?? newsTestResult.articles.length,
                })}
              </div>
              {newsTestResult.articles.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    {t('settings.newsSampleTitles', 'Sample Titles')}
                  </div>
                  {newsTestResult.articles.slice(0, 5).map((article, index) => (
                    <div key={`${article.source_url}-${index}`} className="text-sm">
                      {article.title || article.source_url}
                    </div>
                  ))}
                </div>
              )}
              <div className="rounded-md bg-muted/50 p-3 space-y-1">
                <div className="text-sm font-medium">
                  {newsTestResult.validation?.schema_match
                    ? t('settings.newsSchemaMatchYes', 'Schema validation passed')
                    : t('settings.newsSchemaMatchNo', 'Schema validation found issues')}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('settings.newsSchemaValidationSummary', 'Valid {{valid}} / Invalid {{invalid}}', {
                    valid: newsTestResult.validation?.valid_articles ?? 0,
                    invalid: newsTestResult.validation?.invalid_articles ?? 0,
                  })}
                </div>
                {!!newsTestResult.validation?.issues?.length && (
                  <div className="space-y-1">
                    {newsTestResult.validation.issues.slice(0, 5).map((issue, index) => (
                      <div key={`${issue.source_url}-${index}`} className="text-xs text-amber-600">
                        {issue.issues.join(', ')}: {issue.source_url}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
