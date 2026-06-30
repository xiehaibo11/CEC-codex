"""Sliding-window IC/ICIR scoring and persistence for FactorEffectivenessService.

Core sliding-window IC computation, cross-window ICIR, custom-factor
effectiveness, statistics helpers (fast rank correlation, legacy metrics,
decay half-life), and the factor_effectiveness upsert.
"""

import logging
from datetime import date, datetime, timezone, timedelta
from typing import List, Dict, Optional

import numpy as np
from sqlalchemy import text

from services.factor_timeframes import get_forward_period_offsets

logger = logging.getLogger(__name__)


class _ScoringMixin:
    def _compute_factor_windowed(self, db, exchange, fname, fcat, symbol, period,
                                  fvals, closes, klines, n_bars, force=False) -> int:
        """Core sliding window IC computation with cross-window ICIR.

        Two-phase approach:
          Phase 1: Slide 720-bar window, compute per-window IC via _calc_ic_fast().
          Phase 2: Compute trailing ICIR across windows (standard quant ICIR definition:
                   mean(IC_series) / std(IC_series) over trailing 30 windows).

        Args:
            force: True = recompute all windows (manual compute, algorithm change).
                   False = skip existing calc_dates (daily cron incremental).
                   ON CONFLICT DO UPDATE ensures force mode overwrites old data.

        Performance: ~0.05ms per _calc_ic_fast call (pure numpy rank correlation)
        vs ~5ms for old _calc_metrics (scipy + pandas rolling). See module docstring.
        """
        WINDOW_BARS = 720   # bars in each IC window
        SLIDE_BARS = 24     # slide by 24 bars
        FORWARD_PERIODS = get_forward_period_offsets(period)
        ICIR_TRAILING = 30  # trailing window count for ICIR computation

        if not FORWARD_PERIODS:
            return 0

        if n_bars < WINDOW_BARS:
            if n_bars < 50:
                return 0
            # Insufficient data for sliding window — single computation, no ICIR
            calc_date = datetime.fromtimestamp(
                klines[-1]["timestamp"], tz=timezone.utc).date()
            count = 0
            ic_by_fp = {}
            for fp_label, fp_hours in FORWARD_PERIODS.items():
                af, ar = self._align_series(fvals, closes, fp_hours, n_bars)
                if len(af) < 10:
                    continue
                m = self._calc_ic_fast(af, ar)
                ic_by_fp[fp_label] = m["ic"]
                dhl = None  # not enough data for decay
                self._upsert(db, exchange, fname, fcat, symbol, period,
                             fp_label, calc_date, n_bars,
                             {"ic_mean": m["ic"], "ic_std": 0.0, "icir": 0.0,
                              "win_rate": m["win_rate"], "sample_count": m["sample_count"],
                              "decay_half_life": dhl})
                count += 1
            return count

        # Load existing data: used for incremental skip AND trailing ICIR base
        existing_by_fp: Dict[str, list] = {fp: [] for fp in FORWARD_PERIODS}
        existing_dates = set()
        if not force:
            rows = db.execute(text("""
                SELECT forward_period, calc_date, ic_mean FROM factor_effectiveness
                WHERE exchange = :ex AND factor_name = :fn
                    AND symbol = :sym AND period = :p
                ORDER BY calc_date
            """), {"ex": exchange, "fn": fname, "sym": symbol, "p": period}).fetchall()
            for r in rows:
                existing_by_fp.setdefault(r[0], []).append((r[1], float(r[2])))
                existing_dates.add(r[1])

        # Phase 1: Compute per-window IC for each forward_period
        # window_data[calc_date][fp_label] = {ic, win_rate, sample_count}
        window_data: Dict[date, Dict[str, dict]] = {}
        for end_idx in range(WINDOW_BARS, n_bars + 1, SLIDE_BARS):
            start_idx = end_idx - WINDOW_BARS
            calc_date = datetime.fromtimestamp(
                klines[end_idx - 1]["timestamp"], tz=timezone.utc).date()

            if not force and calc_date in existing_dates:
                continue

            w_fvals = fvals[start_idx:end_idx]
            w_closes = closes[start_idx:end_idx]
            w_n = end_idx - start_idx

            fp_results = {}
            for fp_label, fp_hours in FORWARD_PERIODS.items():
                af, ar = self._align_series(w_fvals, w_closes, fp_hours, w_n)
                if len(af) < 10:
                    continue
                fp_results[fp_label] = self._calc_ic_fast(af, ar)
            if fp_results:
                window_data[calc_date] = fp_results

        if not window_data:
            return 0

        # Phase 2: Compute trailing ICIR and upsert
        count = 0
        for fp_label in FORWARD_PERIODS:
            # Merge existing + new ICs in chronological order
            existing_ics = existing_by_fp.get(fp_label, [])
            new_entries = sorted(
                [(d, window_data[d][fp_label])
                 for d in window_data if fp_label in window_data[d]],
                key=lambda x: x[0],
            )
            all_ics = [ic for _, ic in existing_ics] + [m["ic"] for _, m in new_entries]
            all_dates = [d for d, _ in existing_ics] + [d for d, _ in new_entries]
            # Sort combined by date
            sorted_pairs = sorted(zip(all_dates, all_ics), key=lambda x: x[0])
            ic_series = [ic for _, ic in sorted_pairs]
            date_to_idx = {d: i for i, (d, _) in enumerate(sorted_pairs)}

            for calc_date, m in new_entries:
                idx = date_to_idx[calc_date]
                start = max(0, idx - ICIR_TRAILING + 1)
                trailing = ic_series[start:idx + 1]

                if len(trailing) >= 3:
                    ic_mean = float(np.mean(trailing))
                    ic_std = float(np.std(trailing))
                    icir = ic_mean / ic_std if ic_std > 1e-8 else 0.0
                else:
                    ic_mean = m["ic"]
                    ic_std = 0.0
                    icir = 0.0

                # Decay half-life from this window's IC across forward periods
                ic_by_fp = {fp: window_data[calc_date][fp]["ic"]
                            for fp in window_data[calc_date]}
                dhl = self._compute_decay_half_life(ic_by_fp, FORWARD_PERIODS)

                self._upsert(db, exchange, fname, fcat, symbol, period,
                             fp_label, calc_date, WINDOW_BARS, {
                                 "ic_mean": round(m["ic"], 6),
                                 "ic_std": round(ic_std, 6),
                                 "icir": round(icir, 4),
                                 "win_rate": round(m["win_rate"], 4),
                                 "sample_count": m["sample_count"],
                                 "decay_half_life": dhl,
                             })
                count += 1

        return count

    def _compute_custom_effectiveness(self, db, exchange, symbol, period,
                                       klines, closes, n_bars, force=False,
                                       factor_offset=0, factor_total=0):
        """Compute IC for active custom factors using sliding window."""
        import pandas as pd
        from database.models import CustomFactor
        from services.factor_expression_engine import factor_expression_engine

        try:
            custom_factors = db.query(CustomFactor).filter(
                CustomFactor.is_active == True).all()
        except Exception:
            return 0

        count = 0
        for ci, cf in enumerate(custom_factors):
            self._progress["current_factor"] = cf.name
            self._progress["factor_completed"] = factor_offset + ci
            self._progress["factor_total"] = factor_total
            try:
                series, err = factor_expression_engine.execute(cf.expression, klines)
                if series is None or len(series) != n_bars:
                    continue
                fvals = [None if pd.isna(v) else float(v) for v in series.tolist()]
                count += self._compute_factor_windowed(
                    db, exchange, cf.name, cf.category or "custom", symbol, period,
                    fvals, closes, klines, n_bars, force=force,
                )
            except Exception as e:
                logger.warning(f"[FactorEffectiveness] custom '{cf.name}' err: {e}")
        return count

    def _align_series(self, fvals, closes, offset, n_bars):
        """Align factor values with forward returns, filtering None."""
        aligned_fv, aligned_rt = [], []
        for i in range(n_bars - offset):
            fv = fvals[i]
            if fv is None or closes[i] == 0:
                continue
            ret = (closes[i + offset] - closes[i]) / closes[i]
            aligned_fv.append(fv)
            aligned_rt.append(ret)
        return aligned_fv, aligned_rt

    def _calc_ic_fast(self, factor_vals, returns):
        """Fast per-window IC computation using pure numpy rank correlation.

        Why this exists (2026-03 optimization):
          The old _calc_metrics() used scipy.spearmanr + pandas rolling IC to compute
          both IC and ICIR within a single window. That approach was designed for
          one-shot full-data mode (called ~700 times total). When we switched to
          sliding window mode, it gets called ~147K times (89 factors × 2 symbols ×
          207 windows × 4 forward_periods), taking ~15 minutes.

          In sliding window mode, ICIR is properly computed ACROSS windows (trailing
          mean/std of per-window ICs) — the standard quantitative finance definition.
          So each window only needs a simple Spearman rank correlation (IC) + win_rate.

          Pure numpy implementation avoids scipy/pandas import overhead and function
          call overhead. Benchmark: ~0.05ms vs ~5ms per call = 100x speedup.
          Total full computation: ~30-60s vs ~15 minutes.

        Returns: {"ic": float, "win_rate": float, "sample_count": int}
        """
        n = len(factor_vals)
        fv = np.array(factor_vals, dtype=float)
        rt = np.array(returns, dtype=float)

        # Spearman rank correlation via numpy argsort (avoids scipy overhead)
        fv_rank = np.argsort(np.argsort(fv)).astype(float)
        rt_rank = np.argsort(np.argsort(rt)).astype(float)
        fv_rank -= fv_rank.mean()
        rt_rank -= rt_rank.mean()
        denom = np.sqrt((fv_rank ** 2).sum() * (rt_rank ** 2).sum())
        ic = float((fv_rank * rt_rank).sum() / denom) if denom > 1e-10 else 0.0

        signs_match = np.sign(fv) == np.sign(rt)
        win_rate = float(signs_match.mean())

        return {
            "ic": round(ic, 6),
            "win_rate": round(win_rate, 4),
            "sample_count": n,
        }

    def _calc_metrics(self, factor_vals, returns):
        """Legacy: Compute IC, ICIR, win_rate within a single data window.

        Kept for backward compatibility but no longer called by sliding window code.
        The sliding window pipeline uses _calc_ic_fast() per window + cross-window
        ICIR computation instead. See _calc_ic_fast() docstring for rationale.
        """
        from scipy.stats import spearmanr
        import pandas as pd

        n = len(factor_vals)
        fv = np.array(factor_vals, dtype=float)
        rt = np.array(returns, dtype=float)

        ic, _ = spearmanr(fv, rt)
        ic = float(ic) if not np.isnan(ic) else 0.0

        # Rolling IC for ICIR using rank-based Pearson (vectorized via pandas)
        # Use non-overlapping windows for large datasets to avoid O(n) scipy calls
        window = min(50, max(20, n // 20))
        ics = []
        if window >= 10 and n >= window * 3:
            fv_rank = pd.Series(fv).rolling(window).rank()
            rt_rank = pd.Series(rt).rolling(window).rank()
            # Sample at window-stride intervals to avoid redundant overlapping windows
            stride = max(1, window // 2)
            for i in range(window - 1, n, stride):
                fr = fv_rank.iloc[i - window + 1:i + 1].values
                rr = rt_rank.iloc[i - window + 1:i + 1].values
                valid = ~(np.isnan(fr) | np.isnan(rr))
                if valid.sum() < 10:
                    continue
                fr_v, rr_v = fr[valid], rr[valid]
                denom = np.std(fr_v) * np.std(rr_v)
                if denom > 1e-10:
                    corr = np.corrcoef(fr_v, rr_v)[0, 1]
                    if not np.isnan(corr):
                        ics.append(corr)

        ic_mean = float(np.mean(ics)) if ics else ic
        ic_std = float(np.std(ics)) if ics else 0.0
        icir = ic_mean / ic_std if ic_std > 1e-8 else 0.0

        signs_match = np.sign(fv) == np.sign(rt)
        win_rate = float(signs_match.mean())

        return {
            "ic_mean": round(ic_mean, 6), "ic_std": round(ic_std, 6),
            "icir": round(icir, 4), "win_rate": round(win_rate, 4),
            "sample_count": n,
        }

    def _compute_decay_half_life(self, ic_by_fp: Dict[str, float],
                                  forward_periods: Dict[str, int]) -> Optional[int]:
        """Fit exponential decay |IC(t)| = a * exp(-lambda * t) across forward periods.

        Returns:
            positive int: half_life in hours (factor prediction decays over time)
            -1: IC strengthens over time (trend/persistent factor, no decay)
            None: insufficient data to determine pattern
        """
        # Collect (hours, |IC|) pairs with valid IC > 0
        points = []
        for fp_label, fp_hours in forward_periods.items():
            if fp_label in ic_by_fp:
                abs_ic = abs(ic_by_fp[fp_label])
                if abs_ic > 1e-8:
                    points.append((fp_hours, abs_ic))

        if len(points) < 3:
            return None

        points.sort(key=lambda p: p[0])

        # Check decay pattern: first point should be >= last point
        if points[-1][1] >= points[0][1]:
            return -1  # IC strengthens over time (trend factor)

        # Log-linear regression: ln(|IC|) = ln(a) - lambda * t
        t_arr = np.array([p[0] for p in points], dtype=float)
        ln_ic = np.log(np.array([p[1] for p in points], dtype=float))

        # Least squares: ln_ic = b0 + b1 * t, where b1 = -lambda
        t_mean = t_arr.mean()
        ln_mean = ln_ic.mean()
        numerator = ((t_arr - t_mean) * (ln_ic - ln_mean)).sum()
        denominator = ((t_arr - t_mean) ** 2).sum()
        if abs(denominator) < 1e-12:
            return -1  # flat IC, treat as persistent

        slope = numerator / denominator  # should be negative for decay
        if slope >= 0:
            return -1  # not decaying, treat as persistent

        lam = -slope
        half_life_hours = np.log(2) / lam
        half_life = int(round(half_life_hours))

        # Sanity: cap at reasonable range (1h ~ 720h=30d)
        if half_life < 1 or half_life > 720:
            return -1

        return half_life

    def _upsert(self, db, exchange, fname, fcat, symbol, period, fp, calc_date, lookback, m):
        db.execute(text("""
            INSERT INTO factor_effectiveness
                (exchange, factor_name, factor_category, symbol, period, forward_period,
                 calc_date, lookback_days, ic_mean, ic_std, icir,
                 win_rate, decay_half_life, sample_count)
            VALUES
                (:ex, :fn, :fc, :sym, :p, :fp, :cd, :lb, :icm, :ics, :icir,
                 :wr, :dhl, :sc)
            ON CONFLICT (exchange, factor_name, symbol, period, forward_period, calc_date)
            DO UPDATE SET
                ic_mean = EXCLUDED.ic_mean, ic_std = EXCLUDED.ic_std,
                icir = EXCLUDED.icir, win_rate = EXCLUDED.win_rate,
                decay_half_life = EXCLUDED.decay_half_life,
                sample_count = EXCLUDED.sample_count
        """), {
            "ex": exchange, "fn": fname, "fc": fcat, "sym": symbol,
            "p": period, "fp": fp, "cd": calc_date, "lb": lookback,
            "icm": m["ic_mean"], "ics": m["ic_std"], "icir": m["icir"],
            "wr": m["win_rate"], "dhl": m.get("decay_half_life"), "sc": m["sample_count"],
        })
