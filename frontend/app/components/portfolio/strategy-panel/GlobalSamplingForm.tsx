import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

interface GlobalSamplingFormProps {
  loading: boolean
  samplingInterval: string
  error: string | null
  success: string | null
  saving: boolean
  onSamplingIntervalChange: (value: string) => void
  onResetMessages: () => void
  onSaveGlobal: () => void
}

export default function GlobalSamplingForm({
  loading,
  samplingInterval,
  error,
  success,
  saving,
  onSamplingIntervalChange,
  onResetMessages,
  onSaveGlobal,
}: GlobalSamplingFormProps) {
  const { t } = useTranslation()

  if (loading) {
    return <div className="text-sm text-muted-foreground">{t('strategy.loadingConfig', 'Loading configuration…')}</div>
  }

  return (
    <Card className="border-muted">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t('strategy.globalConfig', 'Global Configuration')}</CardTitle>
        <CardDescription className="text-xs">{t('strategy.globalDesc', 'Settings that affect all traders')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <section className="space-y-2">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">{t('strategy.samplingInterval', 'Sampling Interval (seconds)')}</div>
          <Input
            type="number"
            min={5}
            max={60}
            step={1}
            value={samplingInterval}
            onChange={(event) => {
              onSamplingIntervalChange(event.target.value)
              onResetMessages()
            }}
          />
          <p className="text-xs text-muted-foreground">{t('strategy.samplingHint', 'How often to collect price samples (default: 18s)')}</p>
        </section>

        {error && <div className="text-sm text-destructive">{error}</div>}
        {success && <div className="text-sm text-green-500">{success}</div>}

        <Button onClick={onSaveGlobal} disabled={saving} className="w-full">
          {saving ? t('strategy.saving', 'Saving…') : t('strategy.saveGlobalSettings', 'Save Global Settings')}
        </Button>
      </CardContent>
    </Card>
  )
}
