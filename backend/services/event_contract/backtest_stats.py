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
    report: Dict[str, Any] = {"trades_evaluated": len(decided)}

    # If trades lack entry/expiry prices, return zeros for all bps levels
    if decided and "entry_price" not in decided[0]:
        for bps in bps_levels:
            report[f"bps_{bps}"] = 0.0
        return report

    for bps in bps_levels:
        if not decided:
            report[f"bps_{bps}"] = 0.0
            continue
        flips = 0
        shift = bps / 10000.0
        for trade in decided:
            entry = float(trade["entry_price"])
            expiry = float(trade["expiry_price"])
            direction = str(trade["direction"])
            base = trade["result"] == "win"
            for factor in (1 + shift, 1 - shift):
                outcome = _settles_win(direction, entry, expiry * factor)
                if outcome is None or outcome != base:
                    flips += 1
                    break
        report[f"bps_{bps}"] = round(flips / len(decided) * 100, 2)
    return report
