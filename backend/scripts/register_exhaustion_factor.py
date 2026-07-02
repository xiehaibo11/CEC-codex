"""Register the "exhaustion reversal" custom factor (spec module 6).

Concept: after a run of same-direction bars, a price move that is large
relative to recent realised volatility, and accompanied by above-average
volume, tends to be exhausted rather than continuing — i.e. it carries
mean-reversion information. The expression below implements that idea using
only functions registered in ``services/factor_expression/definitions.py``:

    extension       = ROC(close, 3)                              # 3-bar % move
    vol_floor       = CLAMP(STDDEV(ROC(close, 1), 20), 0.05, 100) # realised 1-bar
                                                                   # vol over 20 bars,
                                                                   # floored so we never
                                                                   # divide by ~0
    volume_confirm  = volume / TS_MEAN(volume, 20)                # >1 => above-average
                                                                   # participation
    factor          = -1 * (extension / vol_floor) * volume_confirm

A large positive ``extension / vol_floor`` (an up-move that is big relative to
typical single-bar volatility) combined with volume confirmation produces a
large *negative* factor value, betting on a pullback; the symmetric case (a
volatility-adjusted down-move on volume) produces a large positive value,
betting on a bounce. This is the mean-reversion sign called for by the spec's
conceptual form ``NEG(MUL(ZSCORE_PROXY(ROC(close,3)), VOLUME_CONFIRM))``.

This is a research script, not an API endpoint: it evaluates the expression's
forward IC/ICIR on live BTC/binance K-line data via the same
``factor_expression_engine.evaluate_ic`` used by ``POST /api/factors/evaluate``,
prints the numbers, and only persists the factor (as ``CustomFactor`` row named
``EXHAUSTION_REVERSAL``, the same table backing ``POST /api/factors/custom``)
if at least one evaluated forward period clears ``|ICIR| >= 1``. If the bar
isn't cleared, the numbers are still printed and the script exits without
writing anything — a negative result is a valid research outcome.

Idempotent: if a custom factor named ``EXHAUSTION_REVERSAL`` already exists,
the script reports its existing effectiveness and exits without duplicating.

Usage:
    uv run python scripts/register_exhaustion_factor.py [--symbol BTC]
        [--exchange binance] [--periods 1h,4h] [--min-icir 1.0]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal  # noqa: E402
from database.models import CustomFactor  # noqa: E402
from services.factor_expression_engine import factor_expression_engine  # noqa: E402
from services.factor_timeframes import get_forward_period_offsets  # noqa: E402
from services.market_data import get_kline_data  # noqa: E402

FACTOR_NAME = "EXHAUSTION_REVERSAL"
FACTOR_EXPRESSION = (
    "-1 * (ROC(close, 3) / CLAMP(STDDEV(ROC(close, 1), 20), 0.05, 100)) "
    "* (volume / TS_MEAN(volume, 20))"
)
FACTOR_DESCRIPTION = (
    "Exhaustion reversal: negates the volatility-normalized 3-bar return, "
    "scaled by a volume-confirmation ratio, to score over-extended "
    "same-direction moves as mean-reversion candidates."
)
DEFAULT_SYMBOL = "BTC"
DEFAULT_EXCHANGE = "binance"
DEFAULT_KLINE_PERIODS = ["1h", "4h"]
DEFAULT_MIN_SAMPLES = 50
DEFAULT_KLINE_COUNT = 1500
DEFAULT_MIN_ICIR = 1.0


def evaluate_periods(
    symbol: str,
    exchange: str,
    kline_periods: list,
    kline_count: int = DEFAULT_KLINE_COUNT,
) -> dict:
    """Evaluate FACTOR_EXPRESSION's forward IC/ICIR for each kline period.

    Returns ``{kline_period: {forward_label: metrics_dict, ...}, ...}``.
    Mirrors exactly what ``POST /api/factors/evaluate`` does per-period
    (fetch klines -> evaluate_ic with that period's forward offsets), just
    called as a function instead of over HTTP.
    """
    market = "binance" if exchange == "binance" else "CRYPTO"
    all_results = {}
    for kline_period in kline_periods:
        klines = get_kline_data(symbol, market=market, period=kline_period, count=kline_count)
        if not klines or len(klines) < DEFAULT_MIN_SAMPLES:
            print(f"  [{kline_period}] insufficient K-line data ({len(klines) if klines else 0} bars)")
            continue

        forward_periods = get_forward_period_offsets(kline_period)
        results, err = factor_expression_engine.evaluate_ic(
            FACTOR_EXPRESSION, klines, forward_periods=forward_periods
        )
        if results is None:
            print(f"  [{kline_period}] evaluate_ic error: {err}")
            continue
        all_results[kline_period] = results
    return all_results


def best_abs_icir(all_results: dict):
    """Return (kline_period, forward_label, icir) for the max |icir|, or None."""
    best = None
    for kline_period, per_forward in all_results.items():
        for forward_label, metrics in per_forward.items():
            icir = metrics.get("icir", 0.0)
            if best is None or abs(icir) > abs(best[2]):
                best = (kline_period, forward_label, icir)
    return best


def print_results(all_results: dict) -> None:
    for kline_period, per_forward in all_results.items():
        for forward_label, metrics in per_forward.items():
            print(
                f"  klines={kline_period:>3}  forward={forward_label:>3}  "
                f"ic_mean={metrics['ic_mean']:+.4f}  ic_std={metrics['ic_std']:.4f}  "
                f"icir={metrics['icir']:+.4f}  win_rate={metrics['win_rate']:.4f}  "
                f"n={metrics['sample_count']}"
            )


def save_factor(db, name: str, expression: str, description: str) -> CustomFactor:
    factor = CustomFactor(
        name=name,
        expression=expression,
        description=description,
        category="reversal",
        source="research_script",
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return factor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    parser.add_argument(
        "--periods",
        default=",".join(DEFAULT_KLINE_PERIODS),
        help="Comma-separated K-line periods to evaluate (e.g. 1h,4h)",
    )
    parser.add_argument("--min-icir", type=float, default=DEFAULT_MIN_ICIR)
    args = parser.parse_args()

    kline_periods = [p.strip() for p in args.periods.split(",") if p.strip()]

    print(f"Factor: {FACTOR_NAME}")
    print(f"Expression ({len(FACTOR_EXPRESSION)} chars): {FACTOR_EXPRESSION}")

    ok, err = factor_expression_engine.validate(FACTOR_EXPRESSION)
    if not ok:
        print(f"VALIDATION FAILED: {err}")
        return 1
    print("Expression syntax: valid")

    db = SessionLocal()
    try:
        existing = db.query(CustomFactor).filter(CustomFactor.name == FACTOR_NAME).first()
        if existing:
            print(
                f"Factor '{FACTOR_NAME}' already exists (id={existing.id}, "
                f"created_at={existing.created_at}). Skipping (idempotent)."
            )
            return 0

        print(f"\nEvaluating IC/ICIR on {args.symbol}/{args.exchange} "
              f"for K-line periods {kline_periods} ...")
        all_results = evaluate_periods(args.symbol, args.exchange, kline_periods)
        if not all_results:
            print("No evaluable results (insufficient data or evaluate_ic errors). Not saving.")
            return 1

        print_results(all_results)

        best = best_abs_icir(all_results)
        if best is None:
            print("No forward periods produced metrics. Not saving.")
            return 1
        best_period, best_forward, best_icir = best
        print(
            f"\nBest |ICIR| = {abs(best_icir):.4f} "
            f"(klines={best_period}, forward={best_forward}, icir={best_icir:+.4f})"
        )

        if abs(best_icir) < args.min_icir:
            print(
                f"HONESTY GATE: |ICIR| {abs(best_icir):.4f} < {args.min_icir} threshold "
                f"on every evaluated forward period. NOT saving {FACTOR_NAME}."
            )
            return 0

        factor = save_factor(db, FACTOR_NAME, FACTOR_EXPRESSION, FACTOR_DESCRIPTION)
        print(
            f"HONESTY GATE PASSED: |ICIR| {abs(best_icir):.4f} >= {args.min_icir}. "
            f"Saved custom factor id={factor.id} name={factor.name}."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
