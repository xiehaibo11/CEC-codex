export type FormState = {
  symbol: string
  exchange: string
  environment: string
  period: string
  consensus_mode: 'ai_confirmed' | 'rule_only'
  decision_policy: 'professional_v1' | 'legacy_vote'
  max_ai_evaluations: number
  start_time: string
  end_time: string
  expiry_minutes: number
  initial_balance: number
  stake_amount: number
  win_payout_ratio: number
  fee_rate: number
  slippage_bps: number
  impact_cost_bps: number
  delay_seconds: number
  consensus_threshold: number
  reviewer_panel_size: number
  target_win_rate: number
  enable_edge_quality_gate: boolean
  max_trade_range_risk: number
  allow_pullback_trades: boolean
  draw_result: string
  enable_fake_breakout_filter: boolean
  enable_trap_filter: boolean
  enable_range_filter: boolean
  enable_multi_timeframe_filter: boolean
  enable_volume_filter: boolean
  enable_cvd_filter: boolean
  enable_l2_features: boolean
  min_l2_coverage_pct: number
  strict_l2_quality: boolean
  enable_coinglass_features: boolean
  min_coinglass_coverage_pct: number
  strict_coinglass_quality: boolean
  coinglass_no_future_leakage: boolean
  platform: 'hibt' | 'binance_event' | 'custom'
  non_overlapping_only: boolean
}

export const PLATFORM_FORM_PRESETS: Record<string, Partial<FormState>> = {
  // fee_rate 0.001 mirrors the backend-enforced execution-cost floor so the
  // submitted config matches what actually runs.
  hibt: { win_payout_ratio: 0.8, fee_rate: 0.001, draw_result: 'loss' },
  binance_event: { win_payout_ratio: 0.8, fee_rate: 0.001, draw_result: 'refund' },
  custom: {},
}

export const PERIOD_OPTIONS = ['1m', '3m', '5m', '15m', '30m', '1h']

export const PERIOD_SECONDS: Record<string, number> = {
  '1m': 60,
  '3m': 180,
  '5m': 300,
  '15m': 900,
  '30m': 1800,
  '1h': 3600,
}
