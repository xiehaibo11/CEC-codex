"""Statistical credibility helpers for event-contract backtests."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple


def wilson_interval(wins: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score 95% interval, returned in percent (0-100)."""
    if n <= 0:
        return 0.0, 0.0
    phat = wins / n
    z2 = z * z
    denom = 1 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    lo = max(0.0, (center - margin) / denom)
    hi = min(1.0, (center + margin) / denom)
    return round(lo * 100, 2), round(hi * 100, 2)


def binomial_p_value(wins: int, n: int, p0: float) -> float:
    """One-sided exact binomial tail P(X >= wins | n, p0)."""
    if n <= 0:
        return 1.0
    p0 = min(max(p0, 0.0), 1.0)
    tail = 0.0
    for k in range(wins, n + 1):
        tail += math.comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
    return min(1.0, max(0.0, tail))


def _settles_win(direction: str, entry: float, expiry: float) -> Any:
    """True=win, False=loss, None=draw for a shifted settlement print."""
    if expiry == entry:
        return None
    if direction == "long":
        return expiry > entry
    return expiry < entry


def settlement_sensitivity(
    trades: List[Dict[str, Any]], bps_levels: Sequence[int] = (2, 5, 10)
) -> Dict[str, Any]:
    """% of decided trades whose outcome flips if the venue settlement print
    differs from our kline source by +/- N bps."""
    decided = [t for t in trades if t.get("result") in ("win", "loss")]
    evaluable = [
        t
        for t in decided
        if t.get("entry_price") is not None
        and t.get("expiry_price") is not None
        and t.get("direction") is not None
    ]
    report: Dict[str, Any] = {
        "trades_evaluated": len(evaluable),
        "trades_skipped": len(decided) - len(evaluable),
    }

    for bps in bps_levels:
        if not evaluable:
            report[f"bps_{bps}"] = 0.0
            continue
        flips = 0
        shift = bps / 10000.0
        for trade in evaluable:
            entry = float(trade["entry_price"])
            expiry = float(trade["expiry_price"])
            direction = str(trade["direction"])
            base = trade["result"] == "win"
            for factor in (1 + shift, 1 - shift):
                outcome = _settles_win(direction, entry, expiry * factor)
                if outcome is None or outcome != base:
                    flips += 1
                    break
        report[f"bps_{bps}"] = round(flips / len(evaluable) * 100, 2)
    return report


CALIBRATION_BUCKETS = ((0, 55), (55, 65), (65, 75), (75, 85), (85, 101))


def calibration_report(trades: List[Dict[str, Any]], min_samples: int = 50) -> Dict[str, Any]:
    """Reliability table + Brier score of predicted expected_win_rate."""
    samples = []
    for trade in trades:
        if trade.get("result") not in ("win", "loss"):
            continue
        predicted = ((trade.get("event_signal") or {}).get("expected_win_rate"))
        if predicted is None:
            continue
        samples.append((float(predicted) / 100.0, 1.0 if trade["result"] == "win" else 0.0))
    if len(samples) < min_samples:
        return {"status": "insufficient_sample", "n": len(samples), "min_samples": min_samples}

    brier = sum((p - y) ** 2 for p, y in samples) / len(samples)
    buckets = []
    for lo, hi in CALIBRATION_BUCKETS:
        rows = [(p, y) for p, y in samples if lo <= p * 100 < hi]
        if not rows:
            continue
        buckets.append(
            {
                "range": f"{lo}-{min(hi, 100)}",
                "n": len(rows),
                "predicted_avg": round(sum(p for p, _ in rows) / len(rows) * 100, 2),
                "actual_win_rate": round(sum(y for _, y in rows) / len(rows) * 100, 2),
            }
        )
    return {"status": "ok", "n": len(samples), "brier_score": round(brier, 4), "buckets": buckets}
