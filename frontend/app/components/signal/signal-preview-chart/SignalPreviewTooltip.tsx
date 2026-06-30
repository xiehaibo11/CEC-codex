import type { ReactNode } from 'react'
import {
  formatDominantMultiplier,
  formatMacdEventLabel,
  formatMetricName,
  formatMillions,
  formatRegimeDirection,
  formatRegimeName,
  formatThousands,
  formatValue,
  getDirectionColor,
  getDirectionLabel,
  getDominantLabel,
  getMacdEventColor,
  getRegimeColor,
} from './formatters'
import type { TooltipState, TriggerData, TriggeredSignal } from './types'

interface SignalPreviewTooltipProps {
  tooltip: TooltipState
  signalMetric?: string
  containerWidth: number
}

function renderTriggeredSignal(sig: TriggeredSignal, index: number): ReactNode {
  if (sig.metric === 'taker_volume' && sig.direction !== undefined) {
    const dirColor = getDirectionColor(sig.direction)
    const dirLabel = getDirectionLabel(sig.direction)
    const dominantMultiplier = formatDominantMultiplier(sig.direction, sig.ratio)
    const dominantLabel = getDominantLabel(sig.direction)

    return (
      <div key={index} className="text-xs border-l-2 border-gray-600 pl-2">
        <div className="text-gray-400 mb-0.5">{sig.signal_name || 'Taker Volume'}</div>
        <div>
          <span className="text-gray-500">Dir:</span>{' '}
          <span className={`font-mono font-medium ${dirColor}`}>{dirLabel}</span>
          <span className="text-gray-500 ml-2">{dominantLabel}:</span>{' '}
          <span className="text-white font-mono">{dominantMultiplier}x</span>
          <span className="text-gray-500 ml-1">(≥{sig.ratio_threshold?.toFixed(1)}x)</span>
        </div>
        <div>
          <span className="text-gray-500">Vol:</span>{' '}
          <span className="text-white font-mono">${formatMillions(sig.volume)}M</span>
          <span className="text-gray-500 ml-1">(≥${formatMillions(sig.volume_threshold)}M)</span>
        </div>
      </div>
    )
  }

  return (
    <div key={index} className="text-xs border-l-2 border-gray-600 pl-2">
      <div className="text-gray-400 mb-0.5">{sig.signal_name || 'Signal'}</div>
      <div>
        <span className="text-white font-mono">{sig.value?.toFixed(4) ?? 'N/A'}</span>
        <span className="text-gray-500 ml-1">(≥{sig.threshold?.toFixed(4) ?? 'N/A'})</span>
      </div>
    </div>
  )
}

function renderSingleTrigger(t: TriggerData, signalMetric?: string, index?: number): ReactNode {
  if (t.triggered_signals && t.triggered_signals.length > 0) {
    return (
      <div key={index} className="space-y-2">
        {t.triggered_signals.map(renderTriggeredSignal)}
      </div>
    )
  }

  if (t.ratio !== undefined && t.direction !== undefined) {
    const dirColor = getDirectionColor(t.direction)
    const dirLabel = getDirectionLabel(t.direction)
    const dominantMultiplier = formatDominantMultiplier(t.direction, t.ratio)
    const dominantLabel = getDominantLabel(t.direction)

    return (
      <div key={index} className="text-xs space-y-0.5">
        <div>
          <span className="text-gray-400">Direction:</span>{' '}
          <span className={`font-mono font-medium ${dirColor}`}>{dirLabel}</span>
        </div>
        <div>
          <span className="text-gray-400">{dominantLabel}:</span>{' '}
          <span className="text-white font-mono">{dominantMultiplier}x</span>
          <span className="text-gray-500 ml-1">(≥{t.ratio_threshold?.toFixed(2)}x)</span>
        </div>
        <div>
          <span className="text-gray-400">Volume:</span>{' '}
          <span className="text-white font-mono">${formatThousands(t.volume)}K</span>
          {t.volume_threshold !== undefined && t.volume_threshold > 0 && (
            <span className="text-gray-500 ml-1">(≥${formatThousands(t.volume_threshold)}K)</span>
          )}
        </div>
      </div>
    )
  }

  if (t.triggered_event && t.values) {
    const eventColor = getMacdEventColor(t.triggered_event)

    return (
      <div key={index} className="text-xs space-y-0.5">
        <div>
          <span className="text-gray-400">Event:</span>{' '}
          <span className={`font-mono font-medium ${eventColor}`}>
            {formatMacdEventLabel(t.triggered_event)}
          </span>
        </div>
        <div>
          <span className="text-gray-400">MACD:</span>{' '}
          <span className="text-white font-mono">{t.values.macd?.toFixed(4)}</span>
        </div>
        <div>
          <span className="text-gray-400">Signal:</span>{' '}
          <span className="text-white font-mono">{t.values.signal?.toFixed(4)}</span>
        </div>
        <div>
          <span className="text-gray-400">Histogram:</span>{' '}
          <span className="text-white font-mono">{t.values.histogram?.toFixed(4)}</span>
          {t.values.prev_histogram !== undefined && (
            <span className="text-gray-500 ml-1">(prev: {t.values.prev_histogram?.toFixed(4)})</span>
          )}
        </div>
        {t.cross_strength !== undefined && (
          <div>
            <span className="text-gray-400">Strength:</span>{' '}
            <span className="text-white font-mono">{t.cross_strength?.toFixed(4)}</span>
          </div>
        )}
      </div>
    )
  }

  if (t.value !== undefined) {
    const metric = t.metric || signalMetric || 'value'
    return (
      <div key={index} className="text-xs">
        <span className="text-gray-400">{formatMetricName(metric)}:</span>{' '}
        <span className="text-white font-mono">{formatValue(metric, t.value)}</span>
        {t.threshold !== undefined && (
          <span className="text-gray-500 ml-1">(≥{formatValue(metric, t.threshold)})</span>
        )}
      </div>
    )
  }

  return null
}

function renderTooltipContent(content: TooltipState['content'], signalMetric?: string): ReactNode {
  if (!content) return null

  const triggers = Array.isArray(content) ? content : [content]
  const regime = triggers[0]?.market_regime

  return (
    <div className="space-y-2">
      <div className="text-xs text-yellow-400 font-medium border-b border-gray-600 pb-1">
        Trigger Values {triggers.length > 1 && `(${triggers.length})`}
      </div>
      {triggers.map((trigger, index) => renderSingleTrigger(trigger, signalMetric, index))}
      {regime && (
        <div className="text-xs border-t border-gray-600 pt-1 mt-1">
          <span className="text-gray-400">Regime:</span>{' '}
          <span className={`font-medium ${getRegimeColor(regime.regime)}`}>
            {formatRegimeName(regime.regime)}
          </span>
          <span className="text-gray-500 ml-1">({formatRegimeDirection(regime.direction)})</span>
          <span className="text-gray-500 ml-1">
            {(regime.confidence * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  )
}

export function SignalPreviewTooltip({ tooltip, signalMetric, containerWidth }: SignalPreviewTooltipProps) {
  if (!tooltip.visible || !tooltip.content) return null

  return (
    <div
      className="absolute z-50 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-lg pointer-events-none"
      style={{
        left: Math.min(tooltip.x + 15, containerWidth - 250),
        top: Math.max(tooltip.y - 60, 10),
      }}
    >
      {renderTooltipContent(tooltip.content, signalMetric)}
    </div>
  )
}
