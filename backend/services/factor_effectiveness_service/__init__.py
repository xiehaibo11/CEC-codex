"""
Factor Effectiveness Service

Computes IC (Information Coefficient) time series using sliding window approach.
For each factor, slides a 720-bar window over full K-line history,
computing IC at each daily position. This produces a complete historical IC
time series immediately — no need to wait for daily accumulation.

Architecture:
  - _compute_factor_windowed(): Core method. Slides a 720-bar window with 24-bar step
    (on 1h K-lines this is a 30-day window with a 1-day step).
    Each window produces one IC value via fast numpy rank correlation (_calc_ic_fast).
    ICIR is computed ACROSS windows (trailing 30-day mean(IC)/std(IC)), which is
    the standard quant definition. Supports force mode (full overwrite) for manual
    compute and incremental mode (skip existing dates) for daily cron.
  - _compute_symbol(): Computes ALL factors for one symbol. Reports per-factor progress.
  - compute_single_factor(): Computes ONE factor across all symbols (Hyper AI tool).

Performance history (2026-03):
  v1: One-shot _calc_metrics with scipy.spearmanr + pandas rolling IC per window.
      147K calls × 5ms = 15 minutes for full compute. Bottleneck was rolling IC
      within each 720-bar window — redundant in sliding window mode where ICIR
      should be computed across windows, not within.
  v2 (current): _calc_ic_fast using pure numpy rank correlation per window (~0.05ms).
      ICIR computed as trailing cross-window mean(IC)/std(IC). Full compute ~30-60s.
      More standard quant approach AND 100x faster per call.

Runs daily via CronTrigger at UTC 01:00, also callable on-demand.
"""

from services.factor_effectiveness_service.core import (
    FactorEffectivenessService,
    factor_effectiveness_service,
)

__all__ = [
    "FactorEffectivenessService",
    "factor_effectiveness_service",
]
