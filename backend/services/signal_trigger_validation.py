"""Sample-gated stratified validation of signal-trigger extremity vs outcomes.

Question this answers: do extreme trigger readings (e.g. DEPTH_RATIO at 4x its
P90 threshold) behave differently from normal-range triggers? The lone extreme
loss on the Binance testnet (31.2 -> bought a local top, -50.33) suggests
extreme depth imbalance may be absorption rather than demand - but one sample
is an anecdote, not a finding. Buckets stay ``insufficient_sample`` until they
hold ``min_bucket_n`` settled trades; only then does the report turn ``ready``.

The trigger value lives only in the decision reason text (no structured
column), so parsing is best-effort and unparsed rows are counted explicitly -
silent drops would make the report look more complete than it is.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.trading import AIDecisionLog
from services.event_contract.backtest_stats import wilson_interval

DEFAULT_MIN_BUCKET_N = 20

# (label, lower-inclusive, upper-exclusive) trigger-value strata. The DEPTH_RATIO
# P90 threshold sits ~7.3, so <10 = normal fire, 10-20 = elevated, >=20 = extreme.
DEFAULT_BUCKETS = (("<10", 0.0, 10.0), ("10-20", 10.0, 20.0), (">=20", 20.0, float("inf")))


def parse_trigger_value(reason: Optional[str], factor: str) -> Optional[float]:
    """Trigger value from a decision reason, keyword-anchored.

    Handles the observed phrasings: ``FACTOR ... (7.76 vs threshold``,
    ``FACTOR=11.45``, ``at 12.31``, ``current 31.2``, ``current value 7.996``.
    Keyword anchors run first so window text like ``30-day P90`` never gets
    mistaken for the reading."""
    if not reason or factor not in reason:
        return None
    segment = reason[reason.index(factor):][:160]
    number = r"([0-9]+(?:\.[0-9]+)?)"
    for pattern in (
        r"(?:\bcurrent value\b|\bcurrent\b|\bvalue\b|\bat\b|=)\s*\(?" + number,
        r"\(" + number + r"\s*(?:vs|>)",
        number + r"\s*(?:vs|>)\s*(?:threshold|[0-9])",
    ):
        match = re.search(pattern, segment)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def signal_trigger_stratified_report(
    db: Session,
    *,
    factor: str = "DEPTH_RATIO",
    min_bucket_n: int = DEFAULT_MIN_BUCKET_N,
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Win-rate table of settled signal-triggered decisions bucketed by the
    factor's trigger value. Verdict-safe by construction: every bucket below
    ``min_bucket_n`` reports ``insufficient_sample`` and the overall status
    only turns ``ready`` when every non-empty bucket has enough data."""
    query = db.query(AIDecisionLog.reason, AIDecisionLog.realized_pnl).filter(
        AIDecisionLog.signal_trigger_id.isnot(None),
        AIDecisionLog.executed == "true",
        AIDecisionLog.realized_pnl.isnot(None),
        AIDecisionLog.realized_pnl != 0,
    )
    if account_id is not None:
        query = query.filter(AIDecisionLog.account_id == account_id)
    rows = query.all()

    samples: List[tuple] = []
    unparsed = 0
    for reason, pnl in rows:
        value = parse_trigger_value(reason, factor)
        if value is None:
            unparsed += 1
            continue
        samples.append((value, float(pnl)))

    buckets = []
    for label, lo, hi in DEFAULT_BUCKETS:
        in_bucket = [pnl for value, pnl in samples if lo <= value < hi]
        wins = sum(1 for pnl in in_bucket if pnl > 0)
        n = len(in_bucket)
        ci_low, ci_high = wilson_interval(wins, n)
        buckets.append(
            {
                "range": label,
                "n": n,
                "wins": wins,
                "losses": n - wins,
                "win_rate": round(wins / n * 100, 2) if n else None,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "net_pnl": round(sum(in_bucket), 2),
                "status": "ok" if n >= min_bucket_n else "insufficient_sample",
            }
        )

    populated = [b for b in buckets if b["n"]]
    ready = bool(populated) and all(b["status"] == "ok" for b in populated)
    return {
        "factor": factor,
        "total_decisions": len(samples) + unparsed,
        "parsed": len(samples),
        "unparsed": unparsed,
        "min_bucket_n": min_bucket_n,
        "buckets": buckets,
        "status": "ready" if ready else "insufficient_sample",
    }


def signal_validation_gate(
    db: Session,
    trigger_context: Optional[Dict[str, Any]],
    *,
    min_n: int = DEFAULT_MIN_BUCKET_N,
) -> Dict[str, Any]:
    """Mainnet deploy gate for signal-triggered orders (问题.md §1).

    Testnet is the validation sandbox and keeps trading freely to accumulate
    the forward record; a signal may drive MAINNET orders only once its
    deduplicated settled record is big enough (>= min_n) and net positive.
    Non-signal triggers pass through - this gate owns exactly one question:
    has this signal earned real money yet?"""
    if not trigger_context or trigger_context.get("trigger_type") != "signal":
        return {"allowed": True, "reason": ""}

    metrics = {
        str(sig.get("metric") or "").upper()
        for sig in trigger_context.get("triggered_signals") or []
        if sig.get("metric")
    }
    if not metrics:
        return {
            "allowed": False,
            "reason": "信号验证门：触发上下文缺少 metric 字段，无法核对验证记录",
        }

    for metric in sorted(metrics):
        report = signal_trigger_stratified_report(db, factor=metric, min_bucket_n=min_n)
        n = report["parsed"]
        net_pnl = round(sum(b["net_pnl"] for b in report["buckets"]), 2)
        wins = sum(b["wins"] for b in report["buckets"])
        if n < min_n:
            return {
                "allowed": False,
                "reason": (
                    f"信号验证门：{metric} 已结算样本 {n} < {min_n}，"
                    "验证期内仅允许测试网执行（观察模式）"
                ),
                "metric": metric,
                "record": {"n": n, "wins": wins, "net_pnl": net_pnl},
            }
        if net_pnl <= 0:
            return {
                "allowed": False,
                "reason": (
                    f"信号验证门：{metric} 前向记录 {n} 笔净盈亏 {net_pnl}（未证明正期望），"
                    "禁止驱动主网订单"
                ),
                "metric": metric,
                "record": {"n": n, "wins": wins, "net_pnl": net_pnl},
            }
    return {"allowed": True, "reason": ""}
