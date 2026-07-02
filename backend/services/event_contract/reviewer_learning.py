"""Evolutionary learning for the 30 event-contract reviewers.

Mechanics:
  1. For every closed event-contract trade we already have an `ai_decision_snapshot`
     in `event_contract_trade_logs` containing each reviewer's direction call.
  2. We compare each reviewer's direction against the realized outcome
     (entry vs expiry price) and update a Beta(alpha, beta) posterior.
  3. Posterior mean and variance feed a Bayesian shrinkage weight:
       weight = base * (mean / 0.5) ^ k   capped to [0.4, 2.0]
     where k grows with sample size so cold-start reviewers stay near 1.0.

The same posterior also produces an "evolution score" used by the panel:
  reviewer score = (long_accuracy + short_accuracy) / 2 - hold_drag.
Reviewers below a floor (default 0.45) get their vote weight halved; consistent
out-performers (> 0.65) get up to 2x. Weights are loaded once per backtest /
predict call and re-cached after each run.

Output of `compute_reviewer_weights(...)` is a dict {ai_name: weight}, suitable
for `weighted_consensus(...)` which folds it into rule_only or ai_confirmed
voting without changing the underlying decision generators.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.event_contract.constants import EVENT_AI_NAMES
from services.event_contract.reviewer_expertise import get_base_weight

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Posterior bookkeeping
# ---------------------------------------------------------------------------

@dataclass
class ReviewerStats:
    """Per-reviewer Beta-Bernoulli posterior over directional correctness.

    `correct` and `total` count realized trades where this reviewer's
    direction matched the trade outcome (winning side).
    `hold_total` is the count of trades where reviewer abstained.
    """
    name: str
    correct: int = 0
    total: int = 0
    hold_total: int = 0
    long_correct: int = 0
    long_total: int = 0
    short_correct: int = 0
    short_total: int = 0
    last_confidence_sum: float = 0.0
    last_confidence_n: int = 0
    flags_seen: Dict[str, int] = field(default_factory=dict)

    # Beta-Bernoulli prior (slightly optimistic so cold-start reviewers vote ~1.0)
    PRIOR_ALPHA: float = 4.0
    PRIOR_BETA: float = 4.0

    def observe(self, reviewer_direction: str, outcome_direction: str, *, confidence: float | None) -> None:
        rd = (reviewer_direction or "hold").lower()
        if rd == "hold":
            self.hold_total += 1
            return
        if confidence is not None:
            try:
                self.last_confidence_sum += float(confidence)
                self.last_confidence_n += 1
            except (TypeError, ValueError):
                pass
        self.total += 1
        is_correct = rd == outcome_direction
        if is_correct:
            self.correct += 1
        if rd == "long":
            self.long_total += 1
            if is_correct:
                self.long_correct += 1
        elif rd == "short":
            self.short_total += 1
            if is_correct:
                self.short_correct += 1

    @property
    def posterior_mean(self) -> float:
        return (self.correct + self.PRIOR_ALPHA) / max(
            1.0, self.total + self.PRIOR_ALPHA + self.PRIOR_BETA
        )

    @property
    def posterior_variance(self) -> float:
        a = self.correct + self.PRIOR_ALPHA
        b = self.total - self.correct + self.PRIOR_BETA
        s = a + b
        if s <= 0:
            return 0.25
        return (a * b) / ((s * s) * (s + 1.0))

    @property
    def hold_drag(self) -> float:
        """Penalize chronic abstainers (>70% hold) so they don't dilute the vote."""
        total_decisions = self.total + self.hold_total
        if total_decisions == 0:
            return 0.0
        hold_rate = self.hold_total / total_decisions
        return max(0.0, hold_rate - 0.6) * 0.15

    @property
    def avg_confidence(self) -> Optional[float]:
        if self.last_confidence_n == 0:
            return None
        return self.last_confidence_sum / self.last_confidence_n

    def evolution_score(self) -> float:
        """A single number in [0, 1] reflecting how reliable this reviewer has been.

        Combines posterior mean with hold drag. Reviewers with very few samples
        sit close to the prior mean (0.5).
        """
        return max(0.0, min(1.0, self.posterior_mean - self.hold_drag))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ai_name": self.name,
            "samples": self.total,
            "hold_samples": self.hold_total,
            "correct": self.correct,
            "posterior_mean": round(self.posterior_mean, 4),
            "posterior_variance": round(self.posterior_variance, 6),
            "evolution_score": round(self.evolution_score(), 4),
            "long_accuracy": round(self.long_correct / self.long_total, 4) if self.long_total else None,
            "short_accuracy": round(self.short_correct / self.short_total, 4) if self.short_total else None,
            "avg_confidence": round(self.avg_confidence, 2) if self.avg_confidence is not None else None,
        }


# ---------------------------------------------------------------------------
# Cache (thread-safe; invalidated by `clear_reviewer_cache()` after a backtest)
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE: Dict[Any, Dict[str, Any]] = {}
_LOOKBACK_TRADES = 1500


def clear_reviewer_cache() -> None:
    """Force a refit on next access."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _winning_direction(entry_price: float, expiry_price: float) -> Optional[str]:
    if expiry_price is None or entry_price is None:
        return None
    if expiry_price > entry_price:
        return "long"
    if expiry_price < entry_price:
        return "short"
    return None  # draw - skip


def fit_reviewer_stats(
    db: Session, *, lookback: int = _LOOKBACK_TRADES, before_ts: Optional[Any] = None
) -> Dict[str, ReviewerStats]:
    """Build per-reviewer posterior stats from settled trades.

    before_ts: only trades with entry_time strictly before this datetime are
    used. Pass the backtest window start to prevent in-window leakage.
    """
    stats = {name: ReviewerStats(name=name) for name in EVENT_AI_NAMES}
    try:
        if before_ts is not None:
            cutoff = before_ts.replace(tzinfo=None) if getattr(before_ts, "tzinfo", None) else before_ts
            rows = db.execute(
                text(
                    """
                    SELECT entry_price, expiry_price, ai_decision_snapshot
                    FROM event_contract_trade_logs
                    WHERE ai_decision_snapshot IS NOT NULL
                      AND entry_time < :cutoff
                    ORDER BY entry_time DESC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": int(lookback)},
            ).fetchall()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT entry_price, expiry_price, ai_decision_snapshot
                    FROM event_contract_trade_logs
                    WHERE ai_decision_snapshot IS NOT NULL
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": int(lookback)},
            ).fetchall()
    except Exception as exc:  # noqa: BLE001 - cold DB shouldn't crash predict()
        logger.warning("reviewer_learning: trade log scan failed (%s) - using priors only", exc)
        return stats

    for entry_price, expiry_price, snapshot_text in rows:
        outcome = _winning_direction(entry_price, expiry_price)
        if outcome is None or not snapshot_text:
            continue
        try:
            payload = snapshot_text if isinstance(snapshot_text, list) else json.loads(snapshot_text)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, list):
            continue
        for decision in payload:
            if not isinstance(decision, Mapping):
                continue
            name = str(decision.get("ai_name", "")).strip()
            if name not in stats:
                continue
            stats[name].observe(
                str(decision.get("direction", "")).lower(),
                outcome,
                confidence=decision.get("confidence"),
            )
            for flag in decision.get("risk_flags") or []:
                if not isinstance(flag, str) or not flag.strip():
                    continue
                key = flag.strip()[:60]
                stats[name].flags_seen[key] = stats[name].flags_seen.get(key, 0) + 1
    return stats


# ---------------------------------------------------------------------------
# Weighting + voting
# ---------------------------------------------------------------------------

WEIGHT_FLOOR = 0.4
WEIGHT_CAP = 2.0
LEARN_RATE_CAP_SAMPLES = 200   # weight exponent saturates after this many samples


def _shrinkage_k(samples: int) -> float:
    """Exponent strength: 0 for cold start, ~2.5 once well sampled."""
    return min(2.5, math.log1p(samples) / math.log1p(LEARN_RATE_CAP_SAMPLES) * 2.5)


def compute_reviewer_weights(db: Session, before_ts: Optional[Any] = None) -> Dict[str, float]:
    """Return {ai_name: weight} folding base expertise weight with learning.

    before_ts: only trades before this datetime are used to compute weights.
    Cached per before_ts value; clear with `clear_reviewer_cache()` to force a refit.
    """
    cache_key = before_ts.isoformat() if before_ts is not None else "__latest__"
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None:
            return dict(cached["weights"])

    stats = fit_reviewer_stats(db, before_ts=before_ts)
    weights: Dict[str, float] = {}
    for name in EVENT_AI_NAMES:
        stat = stats[name]
        base = get_base_weight(name)
        mean = stat.posterior_mean
        # ratio of evolution_score to neutral baseline (0.5).
        evo = stat.evolution_score()
        ratio = (evo + 1e-3) / 0.5
        k = _shrinkage_k(stat.total)
        adjusted = base * (ratio ** k)
        weights[name] = max(WEIGHT_FLOOR, min(WEIGHT_CAP, round(adjusted, 4)))
        # If reviewer is way off (mean < 0.4) AND has > 50 samples, force halve.
        if stat.total > 50 and mean < 0.4:
            weights[name] = max(WEIGHT_FLOOR, weights[name] * 0.5)

    with _CACHE_LOCK:
        _CACHE[cache_key] = {"weights": dict(weights), "stats": stats}
    return weights


def weighted_consensus(
    decisions: Iterable[Mapping[str, Any]],
    weights: Mapping[str, float],
) -> Dict[str, Any]:
    """Apply learning weights on top of an existing 30-reviewer panel.

    Returns the weighted vote tally and a recommended final_direction.
    Holds always count as themselves (no weight, no flip) so chronic abstainers
    don't accidentally swing the outcome.
    """
    long_w = short_w = 0.0
    long_n = short_n = hold_n = 0
    for decision in decisions:
        if not isinstance(decision, Mapping):
            continue
        name = str(decision.get("ai_name", "")).strip()
        direction = str(decision.get("direction", "hold")).lower()
        weight = float(weights.get(name, 1.0))
        if direction == "long":
            long_w += weight
            long_n += 1
        elif direction == "short":
            short_w += weight
            short_n += 1
        else:
            hold_n += 1

    total_weight = long_w + short_w
    if total_weight <= 0:
        return {
            "weighted_long": 0.0, "weighted_short": 0.0, "long_votes": long_n,
            "short_votes": short_n, "hold_votes": hold_n, "final_direction": "hold",
            "weighted_consensus_rate": 0.0,
        }
    long_share = long_w / total_weight
    short_share = short_w / total_weight
    direction = "long" if long_share > short_share else "short"
    return {
        "weighted_long": round(long_w, 4),
        "weighted_short": round(short_w, 4),
        "long_votes": long_n,
        "short_votes": short_n,
        "hold_votes": hold_n,
        "final_direction": direction,
        "weighted_consensus_rate": round(max(long_share, short_share) * 100, 2),
    }


# ---------------------------------------------------------------------------
# Public introspection (for a future API / Dashboard panel)
# ---------------------------------------------------------------------------

def get_reviewer_evolution_snapshot(db: Session) -> List[Dict[str, Any]]:
    """Snapshot used by the team-stats endpoint to show learning progress.

    Always refits (no cache) so the Dashboard sees the up-to-date posterior
    once a backtest has finished writing new trade logs.
    """
    stats = fit_reviewer_stats(db)
    weights = compute_reviewer_weights(db)
    snapshot = []
    for name in EVENT_AI_NAMES:
        record = stats[name].to_dict()
        record["weight"] = weights.get(name, 1.0)
        record["weight_base"] = get_base_weight(name)
        # Top 3 risk flags this reviewer has cited (signal what it sees)
        flags = stats[name].flags_seen
        record["top_flags"] = sorted(flags.items(), key=lambda kv: kv[1], reverse=True)[:3]
        snapshot.append(record)
    return snapshot
