import { apiRequest } from './apiClient'

export interface EventContractSymbol {
  exchange: string
  symbol: string
  environment: string
  periods: string[]
  records: number
  earliest_ts?: number | null
  latest_ts?: number | null
}

export interface EventContractConfig {
  symbol: string
  exchange: string
  environment?: string
  period: string
  expiry_minutes: number
  consensus_mode?: 'ai_confirmed' | 'rule_only'
  decision_policy?: 'professional_v1' | 'legacy_vote'
  ai_trader_id?: number | null
  max_ai_evaluations?: number
  consensus_threshold: number
  reviewer_panel_size: number
  target_win_rate?: number
  target_min_trades?: number
  enable_edge_quality_gate?: boolean
  max_trade_range_risk?: number
  allow_pullback_trades?: boolean
  enable_fake_breakout_filter: boolean
  enable_trap_filter: boolean
  enable_range_filter: boolean
  enable_multi_timeframe_filter: boolean
  enable_volume_filter: boolean
  enable_cvd_filter: boolean
  enable_coinglass_features?: boolean
  min_coinglass_coverage_pct?: number
  strict_coinglass_quality?: boolean
  coinglass_metrics?: string[] | null
  coinglass_no_future_leakage?: boolean
  max_entry_lag_seconds?: number
  max_expiry_lag_seconds?: number
  min_data_coverage_pct?: number
  strict_data_quality?: boolean
  enable_l2_features?: boolean
  min_l2_coverage_pct?: number
  strict_l2_quality?: boolean
  max_l2_lag_seconds?: number
}

export interface EventContractBacktestConfig extends EventContractConfig {
  start_time: string
  end_time: string
  initial_balance: number
  stake_amount: number
  win_payout_ratio: number
  fee_rate: number
  slippage_bps: number
  delay_seconds: number
  draw_result: string
  max_bars?: number
  platform?: 'hibt' | 'binance_event' | 'custom'
  non_overlapping_only?: boolean
}

export interface EventAiDecision {
  ai_name: string
  source?: 'llm_ai' | 'system_panel' | 'main_logic' | 'rule_prefilter'
  model?: string
  account_name?: string
  direction: 'long' | 'short' | 'hold'
  confidence: number
  reason: string
  risk_flags: string[]
  evidence: string[]
  timeframes: string[]
  invalid_conditions: string[]
}

export interface EventAiReviewerStatus {
  ai_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  direction?: 'long' | 'short' | 'hold' | null
  confidence?: number | null
  reason?: string | null
  model?: string | null
  account_name?: string | null
  error?: string | null
}

export interface EventFactorSnapshot {
  factor_name: string
  category: string
  timeframe: string
  value: number
  normalized_score: number
  direction_bias: 'long' | 'short' | 'neutral'
  confidence: number
  weight: number
  explanation: string
}

export interface EventConsensus {
  final_direction: 'long' | 'short' | 'hold'
  consensus_mode?: 'ai_confirmed' | 'rule_only'
  decision_policy?: 'professional_v1' | 'legacy_vote'
  consensus_source?: 'llm_ai' | 'system_panel' | 'main_logic' | 'rule_prefilter'
  ai_participated?: boolean
  main_logic_participated?: boolean
  main_logic_direction?: 'long' | 'short' | 'hold' | null
  ai_model?: string | null
  ai_account_name?: string | null
  long_votes: number
  short_votes: number
  hold_votes: number
  top_votes?: number
  top_direction?: 'long' | 'short' | 'hold'
  required_votes?: number
  reviewer_count?: number
  reviewer_panel_size?: number
  weighted_consensus_rate?: number
  consensus_rate: number
  edge_score?: number
  risk_score?: number
  execution_score?: number
  decision_grade?: 'A' | 'B' | 'C' | 'D' | 'F'
  trade_readiness?: 'tradable' | 'watch' | 'blocked'
  veto_reasons?: string[]
  decision_diagnostics?: EventDecisionDiagnostics
  allow_trade: boolean
  signal_type: string
  event_signal_type?: string
  signal_strength: number
  reason_summary: string
}

export interface EventSignal {
  signal_id: string
  symbol: string
  signal_type: string
  direction: 'long' | 'short' | 'hold'
  entry_time: string
  entry_price: number
  expiry_time: string
  expiry_minutes: number
  confidence: number
  signal_strength: number
  expected_win_rate: number
  decision_policy?: 'professional_v1' | 'legacy_vote'
  edge_score?: number
  risk_score?: number
  execution_score?: number
  decision_grade?: 'A' | 'B' | 'C' | 'D' | 'F'
  trade_readiness?: 'tradable' | 'watch' | 'blocked'
  veto_reasons?: string[]
  decision_diagnostics?: EventDecisionDiagnostics
  trap_risk: number
  fake_breakout_risk: number
  range_risk: number
  valid_seconds: number
  entry_condition: string
  avoid_condition: string
  reason: string
  related_factors: string[]
  ai_consensus: EventConsensus
}

export interface EventDecisionDiagnostics {
  vote_rate?: number
  top_direction?: 'long' | 'short' | 'hold'
  trend_component?: number
  volume_component?: number
  avg_confidence?: number
  risk_veto_count?: number
  composite_score?: number
  edge_threshold?: number
  risk_threshold?: number
  execution_threshold?: number
  readiness_rule?: string
  [key: string]: any
}

export interface EventDataQuality {
  enabled?: boolean
  source?: string
  key_source?: string
  period: string
  interval_seconds: number
  records_loaded: number
  decision_records: number
  expected_decision_records: number
  coverage_pct: number
  duplicate_count: number
  non_monotonic_count: number
  gap_count: number
  missing_bar_count?: number
  max_gap_seconds: number
  sample_gaps?: Array<any>
  warnings: string[]
  strict: boolean
  unclosed_bars_dropped?: number
  min_required_coverage_pct?: number
  metric_coverage?: Array<any>
  coinglass?: EventDataQuality
  l2?: EventDataQuality
  no_future_leakage?: boolean
  max_lag_seconds?: number | null
  avg_lag_seconds?: number | null
}

export interface EventPrediction {
  symbol: string
  engine_version?: string
  exchange: string
  period: string
  consensus_mode?: 'ai_confirmed' | 'rule_only'
  decision_policy?: 'professional_v1' | 'legacy_vote'
  ai_participated?: boolean
  ai_model?: string | null
  ai_account_name?: string | null
  current_time: string
  current_price: number
  expiry_time: string
  market_state: string
  long_5m_probability: number
  short_5m_probability: number
  hold_probability: number
  best_action: 'long' | 'short' | 'hold'
  allow_trade: boolean
  confidence: number
  signal_strength: number
  signal_type?: string
  event_signal_type?: string
  trap_risk: number
  fake_breakout_risk: number
  range_risk: number
  edge_score?: number
  risk_score?: number
  execution_score?: number
  decision_grade?: 'A' | 'B' | 'C' | 'D' | 'F'
  trade_readiness?: 'tradable' | 'watch' | 'blocked'
  veto_reasons?: string[]
  decision_diagnostics?: EventDecisionDiagnostics
  reason: string
  entry_warning: string
  similar_patterns: Array<any>
  event_signal?: EventSignal
  data_quality?: EventDataQuality
  ai_consensus: EventConsensus
  ai_decisions: EventAiDecision[]
  factors: EventFactorSnapshot[]
}

export interface EventTradeLog {
  trade_id?: string
  trade_index: number
  symbol: string
  direction: 'long' | 'short'
  signal_time?: string
  entry_time: string
  entry_price: number
  expiry_time: string
  expiry_price: number
  entry_delay_lag_seconds?: number
  expiry_lag_seconds?: number
  result: 'win' | 'loss' | 'draw'
  profit_loss: number
  equity_before?: number
  equity_after?: number
  signal_strength: number
  ai_consensus_rate: number
  consensus_source?: 'llm_ai' | 'system_panel' | 'main_logic' | 'rule_prefilter'
  ai_participated?: boolean
  ai_model?: string | null
  ai_account_name?: string | null
  signal_type?: string
  event_signal?: EventSignal
  long_votes: number
  short_votes: number
  hold_votes: number
  market_state: string
  trap_risk: number
  fake_breakout_risk: number
  reason: string
  factor_snapshot: EventFactorSnapshot[]
  ai_decision_snapshot: EventAiDecision[]
}

export interface EventBacktestQualityCheck {
  id: string
  label: string
  status: 'pass' | 'warning' | 'fail'
  message: string
  deduction?: number
}

export interface EventBacktestQualityGate {
  score: number
  grade: 'A' | 'B' | 'C' | 'D' | 'F'
  status: 'pass' | 'warning' | 'fail'
  warnings: string[]
  checks: EventBacktestQualityCheck[]
  recommendations: string[]
}

export interface EventBacktestValidationWindow {
  window: number
  start_trade_index: number
  end_trade_index: number
  trade_count: number
  win_rate: number
  pnl: number
  max_drawdown: number
  passed: boolean
}

export interface EventBacktestRegimeValidation {
  regime: string
  trade_count: number
  win_rate: number
  pnl: number
  max_drawdown: number
  unstable: boolean
}

export interface EventBacktestValidationReport {
  version: string
  verdict: 'pass' | 'warning' | 'fail'
  warnings: string[]
  walk_forward: {
    window_count: number
    pass_rate: number
    stability_score: number
    worst_window_win_rate: number
    worst_window_pnl: number
    windows: EventBacktestValidationWindow[]
  }
  monte_carlo: {
    simulations: number
    profitable_ratio: number
    p5_pnl: number
    p50_pnl: number
    p95_pnl: number
    max_drawdown_p95: number
  }
  regime_stability: {
    regime_count: number
    weakest_regime?: string | null
    unstable_regime_count: number
    by_regime: EventBacktestRegimeValidation[]
  }
  live_decay_estimate: {
    expected_decay_pct: number
    conservative_pnl: number
    verdict: 'pass' | 'warning' | 'fail'
    reasons: string[]
  }
  edge_monotonicity?: {
    status: 'ok' | 'insufficient_sample'
    n: number
    min_samples?: number
    groups?: Array<{ group: number; n: number; avg_score: number; win_rate: number }>
    inversions?: number
    top_minus_bottom?: number
    verdict?: 'monotonic' | 'partial' | 'flat_or_inverted'
  }
  threshold_sensitivity?: {
    status: 'ok' | 'insufficient_sample'
    direction?: string
    base_win_rate?: number
    base_pnl?: number
    base_trades?: number
    dimensions?: Array<{
      param: string
      base_value: number
      tightened_value: number
      trades_kept: number
      kept_ratio: number
      win_rate: number
      win_rate_delta: number
      pnl: number
    }>
  }
}

export interface EventBacktestResearchVerdict {
  status: 'rejected' | 'watch' | 'paper_candidate'
  label: string
  best_candidate_id?: string | null
  best_candidate_name?: string | null
  reasons: string[]
}

export interface EventBacktestOosValidation {
  method: string
  train_trade_count: number
  train_win_rate: number
  train_pnl: number
  oos_trade_count: number
  oos_win_rate: number
  oos_pnl: number
  win_rate_gap: number
  target_win_rate: number
  break_even_win_rate: number
  split_trade_index?: number
  overfit_risk: 'none' | 'low' | 'medium' | 'high' | 'critical'
  status: 'pass' | 'watch' | 'fail' | 'insufficient_oos' | 'no_trades'
  summary: string
}

export interface EventBacktestStrategyCandidate {
  candidate_id: string
  name: string
  description: string
  trade_count: number
  win_rate: number
  pnl: number
  train_trade_count: number
  train_win_rate: number
  oos_trade_count: number
  oos_win_rate: number
  oos_pnl: number
  win_rate_gap: number
  overfit_risk: 'none' | 'low' | 'medium' | 'high' | 'critical'
  recommendation: string
  recommendation_rank?: number
}

export interface EventBacktestFactorInsight {
  factor_name: string
  category: string
  sample_count: number
  win_mean: number
  loss_mean: number
  separation_score: number
  direction: 'positive_edge' | 'negative_edge'
  reliability: 'strong' | 'medium' | 'weak' | 'low_sample'
  interpretation: string
}

export interface EventBacktestOverfitWarning {
  severity: 'medium' | 'high' | 'critical'
  message: string
  evidence: string
}

export interface EventBacktestMissingDataRecommendation {
  data_type: string
  status: string
  recommendation: string
}

export interface EventBacktestAiTrader {
  trader_id: string
  ai_name: string
  name: string
  strategy_type: string
  factor_focus: string[]
  evaluated_count: number
  hold_count: number
  missing_decision_count: number
  trade_count: number
  wins: number
  losses: number
  draws: number
  win_rate: number
  pnl: number
  max_drawdown: number
  train_trade_count: number
  train_win_rate: number
  train_pnl: number
  oos_trade_count: number
  oos_win_rate: number
  oos_pnl: number
  win_rate_gap: number
  overfit_risk: 'none' | 'low' | 'medium' | 'high' | 'critical'
  break_even_win_rate: number
  target_win_rate: number
  recommendation: string
  recommendation_rank: number
}

export interface EventBacktestAiTraderTeam {
  mode: 'independent_traders'
  description: string
  total_traders: number
  total_team_trades: number
  top_traders: EventBacktestAiTrader[]
  paper_candidates: EventBacktestAiTrader[]
  rejected_traders: EventBacktestAiTrader[]
  traders: EventBacktestAiTrader[]
}

export interface EventBacktestWindowReuse {
  available: boolean
  overlap_threshold_pct?: number
  prior_runs?: number
  distinct_configs?: number
  distinct_fingerprints?: number
  overfit_risk?: 'low' | 'medium' | 'high'
}

export interface EventBacktestResearchReport {
  version: string
  verdict: EventBacktestResearchVerdict
  oos_validation: EventBacktestOosValidation
  strategy_candidates: EventBacktestStrategyCandidate[]
  factor_insights: EventBacktestFactorInsight[]
  overfitting_warnings: EventBacktestOverfitWarning[]
  missing_data_recommendations: EventBacktestMissingDataRecommendation[]
  ai_trader_team?: EventBacktestAiTraderTeam
  window_reuse?: EventBacktestWindowReuse
}

export interface EventBacktestSummary {
  engine_version?: string
  config_hash?: string
  data_quality?: EventDataQuality
  quality_gate?: EventBacktestQualityGate
  validation_report?: EventBacktestValidationReport
  research_report?: EventBacktestResearchReport
  consensus_mode?: 'ai_confirmed' | 'rule_only'
  consensus_source?: 'llm_ai' | 'system_panel' | 'main_logic' | 'rule_prefilter'
  ai_confirmed?: boolean
  max_ai_evaluations?: number
  target_win_rate?: number
  target_min_trades?: number
  target_sample_met?: boolean
  target_win_rate_met?: boolean
  break_even_win_rate?: number
  partial?: boolean
  audit_status?: string
  total_trades: number
  wins: number
  losses: number
  draws: number
  win_rate: number
  loss_rate: number
  profit_factor: number
  expectancy: number
  initial_balance: number
  final_equity: number
  total_pnl: number
  total_pnl_percent: number
  max_drawdown: number
  max_consecutive_wins: number
  max_consecutive_losses: number
  average_signal_strength: number
  average_trap_risk: number
  long_win_rate: number
  short_win_rate: number
  trend_market_win_rate: number
  range_market_win_rate: number
  breakout_win_rate: number
  pullback_win_rate: number
  fake_breakout_filtered_count: number
  trap_filtered_count: number
  edge_quality_filtered_count?: number
  no_trade_filtered_count: number
  rule_prefiltered_count?: number
  ai_evaluated_count?: number
  llm_evaluated_count?: number
  ai_rejected_count?: number
  ai_skipped_cap_count?: number
  missing_expiry_count?: number
  expiry_lag_skipped_count?: number
  entry_delay_skipped_count?: number
  decision_bars_count?: number
  candidate_signals_count?: number
  execution_time_ms: number
  decided_trades?: number
  decided_win_rate?: number
  win_rate_ci_low?: number
  win_rate_ci_high?: number
  p_value_vs_breakeven?: number
  significant_vs_breakeven?: boolean
  target_win_rate_status?: 'met' | 'not_met' | 'insufficient_sample'
  settlement_sensitivity?: { trades_evaluated: number; bps_2: number; bps_5: number; bps_10: number }
  calibration_report?: {
    status: 'ok' | 'insufficient_sample'
    n: number
    brier_score?: number
    buckets?: { range: string; n: number; predicted_avg: number; actual_win_rate: number }[]
  }
  strategy_fingerprint?: string
  platform?: string
  non_overlapping_only?: boolean
  overlap_skipped_count?: number
  frequency_skipped_count?: number
  daily_cap_skipped_count?: number
}

export interface EventBacktestResponse {
  run_id: number
  config: EventContractBacktestConfig
  summary: EventBacktestSummary
  data_quality?: EventDataQuality
  equity_curve: Array<{ timestamp: number; equity: number }>
  trades: EventTradeLog[]
  trades_returned: number
  total_trade_logs: number
}

export interface EventBacktestTaskStatus {
  task_id: number
  id: number
  user_id?: number | null
  run_id?: number | null
  name?: string | null
  status: 'pending' | 'running' | 'pause_requested' | 'paused' | 'completed' | 'failed'
  symbol: string
  exchange: string
  environment: string
  period: string
  config: EventContractBacktestConfig
  progress_pct: number
  phase: string
  processed_decision_bars: number
  total_decision_bars: number
  completed_ai_reviews: number
  expected_ai_reviews: number
  ai_reviewer_statuses: EventAiReviewerStatus[]
  latest_message?: string | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  result?: EventBacktestResponse
}

export async function getEventContractSymbols(exchange?: string): Promise<{
  symbols: EventContractSymbol[]
  default_exchange: string
  default_symbol: string
  supported_periods: string[]
}> {
  const query = exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''
  const response = await apiRequest(`/event-contract/symbols${query}`)
  return response.json()
}

export async function predictEventContract(
  config: EventContractConfig,
  options: { signal?: AbortSignal } = {}
): Promise<EventPrediction> {
  const isAiConfirmed = config.consensus_mode === 'ai_confirmed'
  const fetchOpts: RequestInit = {
    method: 'POST',
    body: JSON.stringify(config),
  }
  if (options.signal) fetchOpts.signal = options.signal
  const response = await apiRequest('/event-contract/predict', fetchOpts, {
    timeoutMs: isAiConfirmed ? 180_000 : 30_000,
  })
  return response.json()
}

export async function runEventContractBacktest(
  config: EventContractBacktestConfig,
  options: { signal?: AbortSignal } = {}
): Promise<EventBacktestResponse> {
  const fetchOpts: RequestInit = {
    method: 'POST',
    body: JSON.stringify(config),
  }
  if (options.signal) fetchOpts.signal = options.signal
  const response = await apiRequest('/event-contract/backtest', fetchOpts, {
    timeoutMs: 600_000,
  })
  return response.json()
}

export interface KlineSanitizeReport {
  input_bars: number
  output_bars: number
  dropped_invalid_bars: number
  dropped_duplicate_bars: number
  warnings: string[]
}

export interface DataQualityAudit {
  coverage_pct: number
  records_loaded: number
  decision_records: number
  expected_decision_records: number
  min_required_coverage_pct?: number
  warnings: string[]
  strict: boolean
  sanitize?: KlineSanitizeReport
}

export interface DataQualityPreview {
  symbol: string
  exchange: string
  period: string
  start_time: string
  end_time: string
  kline: DataQualityAudit | null
  l2: DataQualityAudit | null
  coinglass: DataQualityAudit | null
  strict: { kline: boolean; l2: boolean; coinglass: boolean }
  would_block: Array<{ source: 'kline' | 'l2' | 'coinglass'; warnings: string[] }>
  ok: boolean
}

export async function previewEventBacktestDataQuality(
  config: EventContractBacktestConfig,
): Promise<DataQualityPreview> {
  const response = await apiRequest('/event-contract/backtest/data-quality-preview', {
    method: 'POST',
    body: JSON.stringify(config),
  }, { timeoutMs: 120_000 })
  return response.json()
}

export async function createEventContractBacktestTask(
  config: EventContractBacktestConfig,
): Promise<EventBacktestTaskStatus> {
  const response = await apiRequest('/event-contract/backtest/tasks', {
    method: 'POST',
    body: JSON.stringify(config),
  })
  return response.json()
}

export async function getEventContractBacktestTask(taskId: number): Promise<EventBacktestTaskStatus> {
  const response = await apiRequest(`/event-contract/backtest/tasks/${taskId}`)
  return response.json()
}

export async function getLatestEventContractBacktestTask(): Promise<EventBacktestTaskStatus | null> {
  const response = await apiRequest('/event-contract/backtest/tasks/latest')
  return response.json()
}

export async function pauseEventContractBacktestTask(taskId: number): Promise<EventBacktestTaskStatus> {
  const response = await apiRequest(`/event-contract/backtest/tasks/${taskId}/pause`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  return response.json()
}

export interface CoinGlassEventContractCapability {
  available: boolean
  configured: boolean
  status: string
  reason: string
  period: string
  symbol?: string
  exchange?: string
  key_source?: 'user' | 'server' | 'none'
  key_masked?: string | null
  level?: string | null
  expired?: boolean | null
  expire_time?: number | null
  required_plan?: string | null
  fetched_at?: number
  metrics: Array<{
    metric: string
    label: string
    path: string
    ok: boolean
    status_code?: number
    code?: string | number
    message?: string | null
  }>
}

export async function getCoinGlassEventContractCapability(params: {
  symbol: string
  exchange: string
  period: string
}): Promise<CoinGlassEventContractCapability> {
  const query = new URLSearchParams({
    symbol: params.symbol,
    exchange: params.exchange,
    period: params.period,
  })
  const response = await apiRequest(`/coinglass/event-contract-capability?${query.toString()}`)
  return response.json()
}

export async function createEventContractHoldoutTask(
  runId: number,
  window: { start_time: string; end_time: string },
): Promise<EventBacktestTaskStatus & { source_run_id?: number; strategy_fingerprint?: string }> {
  const response = await apiRequest(`/event-contract/backtest/${runId}/holdout`, {
    method: 'POST',
    body: JSON.stringify(window),
  })
  return response.json()
}

// -- Paper traders (live "follow the trader" - spec module 3) -----------------

export interface EventPaperTraderStats {
  trader_id: number
  n_settled: number
  decided: number
  wins: number
  losses: number
  draws: number
  decided_win_rate: number
  win_rate_ci_low: number
  win_rate_ci_high: number
  p_value_vs_breakeven: number
  break_even_win_rate: number
  total_pnl: number
  current_balance: number
  stake_amount: number
  open_bets: number
  strategy_fingerprint: string | null
}

export interface EventPaperTrader extends EventPaperTraderStats {
  id: number
  name: string
  enabled: boolean
  symbol: string
  exchange: string
  environment: string
  config: Record<string, unknown>
  initial_balance: number
  created_at: string | null
  updated_at: string | null
}

export interface EventPaperTraderBet {
  id: number
  trader_id: number
  direction: 'long' | 'short'
  status: 'pending_entry' | 'open' | 'settled'
  decision_time: string | null
  entry_time: string | null
  entry_price: number | null
  expiry_time: string | null
  expiry_price: number | null
  result: 'win' | 'loss' | 'draw' | null
  pnl: number | null
  stake: number
  payout_ratio: number | null
  market_state: string | null
  signal_strength: number | null
  reason: string | null
  analysis_snapshot: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
}

export interface EventPaperTraderBetsResponse {
  trader_id: number
  total: number
  limit: number
  offset: number
  bets: EventPaperTraderBet[]
}

export async function getEventPaperTraders(): Promise<EventPaperTrader[]> {
  const response = await apiRequest('/event-contract/paper-traders')
  return response.json()
}

export async function getEventPaperTraderBets(
  traderId: number,
  limit = 20,
  offset = 0,
): Promise<EventPaperTraderBetsResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const response = await apiRequest(`/event-contract/paper-traders/${traderId}/bets?${query.toString()}`)
  return response.json()
}

export async function getEventPaperTraderStats(traderId: number): Promise<EventPaperTraderStats> {
  const response = await apiRequest(`/event-contract/paper-traders/${traderId}/stats`)
  return response.json()
}

// -- Rolling out-of-sample validation progress (spec module 4) ----------

export interface EventValidationSegment {
  window_start: string | null
  window_end: string | null
  decided: number
  wins: number
  status: 'pending' | 'recorded' | 'failed'
  holdout_run_id: number | null
}

export interface EventValidationProgress {
  fingerprint: string
  segments: EventValidationSegment[]
  n: number
  wins: number
  decided_win_rate: number
  ci_low: number
  ci_high: number
  p_value: number
  break_even_win_rate: number
  target_n: number
}

export async function getEventContractValidationProgress(fingerprint: string): Promise<EventValidationProgress> {
  const response = await apiRequest(`/event-contract/validation/${encodeURIComponent(fingerprint)}`)
  return response.json()
}
