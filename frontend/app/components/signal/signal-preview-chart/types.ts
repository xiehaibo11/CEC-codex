export interface KlineData {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
}

export interface TriggeredSignal {
  signal_id: number
  signal_name: string
  value: number
  threshold: number
  metric?: string
  direction?: string
  ratio?: number
  volume?: number
  ratio_threshold?: number
  volume_threshold?: number
}

// Full trigger data from backend
export interface TriggerData {
  timestamp: number
  value?: number
  threshold?: number
  metric?: string
  triggered_signals?: TriggeredSignal[]
  trigger_type?: string
  // taker_volume composite signal fields
  direction?: string
  ratio?: number
  log_ratio?: number
  volume?: number
  ratio_threshold?: number
  volume_threshold?: number
  // MACD event-based signal fields
  triggered_event?: string
  event_types?: string[]
  values?: {
    macd: number
    signal: number
    histogram: number
    prev_histogram?: number
  }
  cross_strength?: number
  // Market Regime classification
  market_regime?: {
    regime: string
    direction: string
    confidence: number
    reason?: string
  }
}

// MACD indicator data from backend
export interface MacdData {
  macd: number[]
  signal: number[]
  histogram: number[]
}

export interface SignalPreviewChartProps {
  klines: KlineData[]
  triggers: TriggerData[]
  timeWindow: string
  signalMetric?: string
  macd?: MacdData
}

export type TriggerBucketContent = TriggerData | TriggerData[]

export interface TooltipState {
  visible: boolean
  x: number
  y: number
  content: TriggerBucketContent | null
}
