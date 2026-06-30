import { useState } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { ExchangeBadge } from './exchange'
import type { SignalConfig } from './types'

// Signal Cards Panel Component
export function SignalCardsPanel({
  configs, onPreview, onCreate, onCreatePool, getMetricLabel, getOperatorLabel, t
}: {
  configs: SignalConfig[]
  onPreview: (config: SignalConfig) => void
  onCreate: (config: SignalConfig) => Promise<boolean>
  onCreatePool: (config: SignalConfig) => Promise<boolean>
  getMetricLabel: (m: string) => string
  getOperatorLabel: (o: string) => string
  t: (key: string, fallback?: string) => string
}) {
  // Track which signals/pools are being created and which have been created
  const [creatingSignals, setCreatingSignals] = useState<Set<string>>(new Set())
  const [createdSignals, setCreatedSignals] = useState<Set<string>>(new Set())

  const handleCreate = async (config: SignalConfig, isPool: boolean) => {
    const signalKey = config.name || `signal-${configs.indexOf(config)}`
    setCreatingSignals(prev => new Set(prev).add(signalKey))
    try {
      const success = isPool ? await onCreatePool(config) : await onCreate(config)
      if (success) {
        setCreatedSignals(prev => new Set(prev).add(signalKey))
      }
    } finally {
      setCreatingSignals(prev => {
        const next = new Set(prev)
        next.delete(signalKey)
        return next
      })
    }
  }

  return (
    <div className="w-[55%] flex flex-col bg-muted/30">
      <div className="p-4 border-b">
        <h3 className="text-sm font-semibold">{t('signals.aiGenerator.generatedSignals', 'Generated Signals')}</h3>
        <p className="text-xs text-muted-foreground mt-1">
          {configs.length > 0
            ? t('signals.aiGenerator.signalsCount', '{{count}} signal(s) generated').replace('{{count}}', configs.length.toString())
            : t('signals.aiGenerator.signalsWillAppear', 'AI-generated signals will appear here')}
        </p>
      </div>
      <ScrollArea className="flex-1 p-4">
        {configs.length > 0 ? (
          <div className="space-y-4">
            {configs.map((config, idx) => {
              const signalKey = config.name || `signal-${idx}`
              const isPool = config._type === 'pool'
              return isPool ? (
                <SignalPoolCard
                  key={idx}
                  config={config}
                  onCreate={() => handleCreate(config, true)}
                  getMetricLabel={getMetricLabel}
                  getOperatorLabel={getOperatorLabel}
                  isCreating={creatingSignals.has(signalKey)}
                  isCreated={createdSignals.has(signalKey)}
                  t={t}
                />
              ) : (
                <SignalCard
                  key={idx}
                  config={config}
                  onPreview={() => onPreview(config)}
                  onCreate={() => handleCreate(config, false)}
                  getMetricLabel={getMetricLabel}
                  getOperatorLabel={getOperatorLabel}
                  isCreating={creatingSignals.has(signalKey)}
                  isCreated={createdSignals.has(signalKey)}
                  t={t}
                />
              )
            })}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-sm">{t('signals.aiGenerator.noSignalsYet', 'No signals generated yet')}</p>
              <p className="text-xs mt-2">{t('signals.aiGenerator.startConversation', 'Start a conversation to generate signals')}</p>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

// Individual Signal Card Component
function SignalCard({
  config, onPreview, onCreate, getMetricLabel, getOperatorLabel, isCreating, isCreated, t
}: {
  config: SignalConfig
  onPreview: () => void
  onCreate: () => void
  getMetricLabel: (m: string) => string
  getOperatorLabel: (o: string) => string
  isCreating?: boolean
  isCreated?: boolean
  t: (key: string, fallback?: string) => string
}) {
  const cond = config.trigger_condition || {}
  const isTakerVolume = cond.metric === 'taker_volume'
  const hasValidMetric = cond.metric && typeof cond.metric === 'string'

  // Check if signal config is valid
  const isValid = hasValidMetric && (
    isTakerVolume || (cond.operator && cond.threshold !== undefined)
  )

  return (
    <div className={`rounded-lg border bg-card p-4 ${!isValid ? 'border-destructive/50' : ''}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-sm">{config.name || t('signals.aiGenerator.unnamedSignal', 'Unnamed Signal')}</h4>
            <ExchangeBadge exchange={config.exchange || 'hyperliquid'} size="sm" />
          </div>
          <p className="text-xs text-muted-foreground">{config.symbol || t('signals.aiGenerator.noSymbol', 'No symbol')}</p>
        </div>
        {hasValidMetric ? (
          <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
            {getMetricLabel(cond.metric)}
          </span>
        ) : (
          <span className="text-xs bg-destructive/10 text-destructive px-2 py-1 rounded">
            {t('signals.aiGenerator.invalidConfig', 'Invalid Config')}
          </span>
        )}
      </div>
      {config.description && (
        <p className="text-xs text-muted-foreground mb-3">{config.description}</p>
      )}
      <div className="bg-muted/50 rounded p-2 mb-3">
        <div className="text-xs space-y-1">
          {!hasValidMetric ? (
            <div className="text-destructive">{t('signals.aiGenerator.missingMetric', 'Missing metric configuration')}</div>
          ) : isTakerVolume ? (
            <>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('signals.aiGenerator.direction', 'Direction')}:</span>
                <span>{cond.direction || 'any'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('signals.aiGenerator.ratioThreshold', 'Ratio Threshold')}:</span>
                <span>{cond.ratio_threshold || 1.5}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('signals.aiGenerator.volumeThreshold', 'Volume Threshold')}:</span>
                <span>{cond.volume_threshold || 0}</span>
              </div>
            </>
          ) : (
            <>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('signals.aiGenerator.metric', 'Metric')}:</span>
                <span>{getMetricLabel(cond.metric)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('signals.aiGenerator.condition', 'Condition')}:</span>
                <span>{getOperatorLabel(cond.operator || '')} {cond.threshold}</span>
              </div>
            </>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t('signals.aiGenerator.timeWindow', 'Time Window')}:</span>
            <span>{cond.time_window || '5m'}</span>
          </div>
        </div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" className="flex-1" onClick={onPreview} disabled={!isValid}>
          {t('signals.aiGenerator.preview', 'Preview')}
        </Button>
        {isCreated ? (
          <Button size="sm" className="flex-1" variant="secondary" disabled>
            <span className="text-green-600">✓ {t('signals.aiGenerator.created', 'Created')}</span>
          </Button>
        ) : (
          <Button size="sm" className="flex-1" onClick={onCreate} disabled={!isValid || isCreating}>
            {isCreating ? t('signals.aiGenerator.creating', 'Creating...') : t('signals.aiGenerator.createSignal', 'Create Signal')}
          </Button>
        )}
      </div>
    </div>
  )
}

// Signal Pool Card Component
function SignalPoolCard({
  config, onCreate, getMetricLabel, getOperatorLabel, isCreating, isCreated, t
}: {
  config: SignalConfig
  onCreate: () => void
  getMetricLabel: (m: string) => string
  getOperatorLabel: (o: string) => string
  isCreating?: boolean
  isCreated?: boolean
  t: (key: string, fallback?: string) => string
}) {
  const signals = config.signals || []
  // Validate signals - support both 'metric' and 'indicator' field names (AI uses 'indicator')
  // taker_volume uses direction/ratio_threshold/volume_threshold instead of operator/threshold
  const isValid = signals.length > 0 && signals.every(s => {
    const metricName = s.metric || s.indicator  // AI outputs 'indicator', frontend uses 'metric'
    if (metricName === 'taker_volume') {
      return s.direction && s.ratio_threshold !== undefined && s.volume_threshold !== undefined
    }
    return metricName && s.operator && s.threshold !== undefined
  })

  return (
    <div className={`rounded-lg border bg-card p-4 ${!isValid ? 'border-destructive/50' : 'border-primary/50'}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-sm">{config.name || t('signals.aiGenerator.unnamedPool', 'Unnamed Pool')}</h4>
            <ExchangeBadge exchange={config.exchange || 'hyperliquid'} size="sm" />
          </div>
          <p className="text-xs text-muted-foreground">{config.symbol || t('signals.aiGenerator.noSymbol', 'No symbol')}</p>
        </div>
        <span className="text-xs bg-primary/20 text-primary px-2 py-1 rounded font-medium">
          {t('signals.aiGenerator.pool', 'Pool')} ({config.logic || 'AND'})
        </span>
      </div>
      {config.description && (
        <p className="text-xs text-muted-foreground mb-3">{config.description}</p>
      )}
      <div className="bg-muted/50 rounded p-2 mb-3">
        <div className="text-xs font-medium mb-2">
          {t('signals.aiGenerator.signalsCombined', '{{count}} Signal(s) Combined with {{logic}}:')
            .replace('{{count}}', signals.length.toString())
            .replace('{{logic}}', config.logic || 'AND')}
        </div>
        <div className="space-y-1">
          {signals.map((sig, idx) => {
            const metricName = sig.metric || sig.indicator  // AI outputs 'indicator', frontend uses 'metric'
            return (
              <div key={idx} className="text-xs flex items-center gap-2 bg-background/50 rounded px-2 py-1">
                <span className="font-medium">{getMetricLabel(metricName || '')}</span>
                {metricName === 'taker_volume' ? (
                  <span className="text-muted-foreground">
                    {sig.direction?.toUpperCase()} ≥{sig.ratio_threshold}x, ≥${((sig.volume_threshold || 0) / 1000000).toFixed(1)}M
                  </span>
                ) : (
                  <span className="text-muted-foreground">
                    {getOperatorLabel(sig.operator || '')} {sig.threshold}
                  </span>
                )}
                <span className="text-muted-foreground">({sig.time_window || '5m'})</span>
              </div>
            )
          })}
        </div>
      </div>
      <div className="flex gap-2">
        {isCreated ? (
          <Button size="sm" className="flex-1" variant="secondary" disabled>
            <span className="text-green-600">✓ {t('signals.aiGenerator.poolCreated', 'Pool Created')}</span>
          </Button>
        ) : (
          <Button size="sm" className="flex-1" onClick={onCreate} disabled={!isValid || isCreating}>
            {isCreating ? t('signals.aiGenerator.creating', 'Creating...') : t('signals.aiGenerator.createPool', 'Create Signal Pool')}
          </Button>
        )}
      </div>
    </div>
  )
}
