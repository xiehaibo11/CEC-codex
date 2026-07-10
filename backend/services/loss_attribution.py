"""Six-dimension loss attribution with kline counterfactual replay.

问题.md §3 operationalized: every settled losing AI decision gets a
structured attribution row instead of a gut-feel post-mortem.

Dimensions tagged per loss:
1. signal quality   - unvalidated / extreme-reading signal, or pure LLM narrative
2. regime mismatch  - counter-trend entries against the prior 4h move
3. execution        - (needs venue fill data; tagged only when available)
4. position / risk  - oversized portion, high leverage, stacking onto exposure
5. trade management - stop parked inside ordinary 1h noise
6. event shock      - news-narrative-driven decisions

Counterfactuals replayed on real 1m klines per loss: no-stop outcomes at
+1h/+4h/+24h, a 2x-wider stop, and half sizing. Aggregation turns tag
commonalities (>=50% share) into explicit rule-patch suggestions - the
"extract the correct operation from the losses" step.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Tag thresholds
COUNTER_TREND_RET4H_PCT = 0.3
OVERSIZED_PORTION = 0.6  # above the sanctioned 0.5 default (2026-07-10 sizing change)
HIGH_LEVERAGE = 5
NEWS_HINTS = ("etf", "geopolit", "news", "narrative", "跌破", "dip", "outflow", "headline")

# A tag must cover at least this share of losses to graduate into a rule suggestion.
SUGGESTION_SHARE = 0.5

RULE_SUGGESTIONS = {
    "news_narrative_driven": (
        "叙事型决策占亏损主体：要求非信号触发的开仓必须有至少一个已验证信号佐证，"
        "否则只允许 hold/close（提示词约束已存在，建议升级为执行层硬规则）"
    ),
    "counter_trend_short": "逆 4h 趋势做空占比过高：开空前检查 4h 收益率 > +0.3% 即降级观望",
    "counter_trend_long": "逆 4h 趋势做多占比过高：开多前检查 4h 收益率 < -0.3% 即降级观望",
    "stop_within_1h_noise": "止损放在 1 小时常态波动区内被反复扫损：止损距离至少设为 1 倍小时波幅之外",
    "stacking_add": "对已有敞口加仓的亏损占比过高：收紧同方向敞口上限或禁止亏损持仓加仓",
    "oversized_portion": "单笔仓位过大：将 target_portion 上限收紧到 0.5 默认值附近",
    "high_leverage": "高杠杆亏损集中：下调默认/最大杠杆",
    "unvalidated_signal": "未通过样本验证的信号在驱动实单：启用主网信号验证门",
    "signal_extreme_reading": "信号极端读数时段亏损集中：等分层验证样本充足后为极端档加过滤",
}


def _pnl_pct(direction: str, entry: float, price: float, leverage: float) -> float:
    move = (price - entry) / entry * 100 * leverage
    return move if direction == "buy" else -move


def _bar_at_or_before(klines: List[Dict[str, Any]], ts: int) -> Optional[Dict[str, Any]]:
    candidate = None
    for bar in klines:
        if bar["timestamp"] <= ts:
            candidate = bar
        else:
            break
    return candidate


def analyze_loss(decision: Dict[str, Any], klines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Attribution row for one losing decision against its kline window.

    ``decision`` carries: decision_id, symbol, operation (buy|sell),
    entry_price, entry_ts, realized_pnl, reason, stop_loss_price,
    take_profit_price, leverage, target_portion, prev_portion,
    signal_trigger_id (optional signal_value)."""
    tags: List[str] = []
    direction = str(decision.get("operation") or "").lower()
    entry = float(decision.get("entry_price") or 0)
    entry_ts = int(decision.get("entry_ts") or 0)
    leverage = float(decision.get("leverage") or 1)
    reason = str(decision.get("reason") or "").lower()

    pre = [b for b in klines if b["timestamp"] < entry_ts]
    post = [b for b in klines if b["timestamp"] >= entry_ts]

    # 1. signal quality / 6. event shock
    if decision.get("signal_trigger_id"):
        n_similar = decision.get("signal_sample_n")
        if n_similar is not None and n_similar < 20:
            tags.append("unvalidated_signal")
        value = decision.get("signal_value")
        if value is not None and value >= 20:
            tags.append("signal_extreme_reading")
    elif any(hint in reason for hint in NEWS_HINTS):
        tags.append("news_narrative_driven")

    # 2. regime mismatch: entry against the prior 4h move
    bar_4h = _bar_at_or_before(pre, entry_ts - 4 * 3600)
    if bar_4h and entry:
        ret4h = (entry - bar_4h["close"]) / bar_4h["close"] * 100
        if direction == "sell" and ret4h > COUNTER_TREND_RET4H_PCT:
            tags.append("counter_trend_short")
        elif direction == "buy" and ret4h < -COUNTER_TREND_RET4H_PCT:
            tags.append("counter_trend_long")

    # 4. position / risk
    if float(decision.get("target_portion") or 0) >= OVERSIZED_PORTION:
        tags.append("oversized_portion")
    if leverage >= HIGH_LEVERAGE:
        tags.append("high_leverage")
    if float(decision.get("prev_portion") or 0) > 0:
        tags.append("stacking_add")

    # 5. trade management: stop inside ordinary hourly noise
    stop = decision.get("stop_loss_price")
    stop_distance_pct = None
    hour_range_pct = None
    if stop and entry:
        stop_distance_pct = abs(float(stop) - entry) / entry * 100
        last_hour = pre[-60:]
        if last_hour:
            hour_high = max(b["high"] for b in last_hour)
            hour_low = min(b["low"] for b in last_hour)
            hour_range_pct = (hour_high - hour_low) / entry * 100
            if stop_distance_pct < hour_range_pct:
                tags.append("stop_within_1h_noise")

    # Counterfactual replay
    counterfactuals: Dict[str, Any] = {
        "half_size_pnl": round(float(decision.get("realized_pnl") or 0) / 2, 2),
    }
    for label, hours in (("1h", 1), ("4h", 4), ("24h", 24)):
        bar = _bar_at_or_before(post, entry_ts + hours * 3600)
        counterfactuals[f"no_stop_pnl_pct_{label}"] = (
            round(_pnl_pct(direction, entry, bar["close"], leverage), 2) if bar and entry else None
        )
    if stop and entry and post:
        stop_price = float(stop)
        horizon = [b for b in post if b["timestamp"] <= entry_ts + 24 * 3600]
        if direction == "sell":
            counterfactuals["stop_was_hit"] = any(b["high"] >= stop_price for b in horizon)
            double_stop = entry + 2 * (stop_price - entry)
            swept = next((b for b in horizon if b["high"] >= double_stop), None)
        else:
            counterfactuals["stop_was_hit"] = any(b["low"] <= stop_price for b in horizon)
            double_stop = entry - 2 * (entry - stop_price)
            swept = next((b for b in horizon if b["low"] <= double_stop), None)
        if swept is not None:
            counterfactuals["double_stop_pnl_pct"] = round(
                _pnl_pct(direction, entry, double_stop, leverage), 2
            )
        elif horizon:
            counterfactuals["double_stop_pnl_pct"] = round(
                _pnl_pct(direction, entry, horizon[-1]["close"], leverage), 2
            )

    return {
        "decision_id": decision.get("decision_id"),
        "symbol": decision.get("symbol"),
        "operation": direction,
        "entry_price": entry,
        "realized_pnl": decision.get("realized_pnl"),
        "reason_head": str(decision.get("reason") or "")[:120],
        "tags": tags,
        "metrics": {
            "stop_distance_pct": round(stop_distance_pct, 3) if stop_distance_pct else None,
            "hour_range_pct": round(hour_range_pct, 3) if hour_range_pct else None,
        },
        "counterfactuals": counterfactuals,
    }


def aggregate_attribution(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Commonalities across attribution rows + rule-patch suggestions for
    every tag covering >= 50% of losses."""
    total = len(rows)
    counts: Dict[str, int] = {}
    for row in rows:
        for tag in row.get("tags") or []:
            counts[tag] = counts.get(tag, 0) + 1

    commonalities = [
        {
            "tag": tag,
            "count": count,
            "share_pct": round(count / total * 100, 1),
            "pnl_sum": round(
                sum(float(r.get("realized_pnl") or 0) for r in rows if tag in (r.get("tags") or [])),
                2,
            ),
        }
        for tag, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    rule_suggestions = [
        {"tag": c["tag"], "share_pct": c["share_pct"], "suggestion": RULE_SUGGESTIONS.get(c["tag"], "")}
        for c in commonalities
        if total and c["count"] / total >= SUGGESTION_SHARE and RULE_SUGGESTIONS.get(c["tag"])
    ]
    return {
        "total_losses": total,
        "commonalities": commonalities,
        "rule_suggestions": rule_suggestions,
    }


# ---------------------------------------------------------------------------
# DB assembly
# ---------------------------------------------------------------------------

_KLINES_SQL = text(
    """
    SELECT timestamp, open_price, high_price, low_price, close_price
    FROM crypto_klines
    WHERE symbol = :symbol AND period = '1m' AND exchange = :exchange
      AND timestamp BETWEEN :start_ts AND :end_ts
    ORDER BY timestamp
    """
)


def _load_klines(db: Session, symbol: str, exchange: str, start_ts: int, end_ts: int):
    rows = db.execute(
        _KLINES_SQL,
        {"symbol": symbol, "exchange": exchange, "start_ts": start_ts, "end_ts": end_ts},
    ).all()
    return [
        {
            "timestamp": int(ts),
            "open": float(o),
            "high": float(h),
            "low": float(low),
            "close": float(c),
        }
        for ts, o, h, low, c in rows
    ]


def attribute_recent_losses(
    db: Session,
    *,
    account_id: Optional[int] = None,
    exchange: str = "binance",
    lookback_days: int = 30,
    limit: int = 100,
) -> Dict[str, Any]:
    """Full attribution report over recent settled losing decisions.

    Entry price approximation: the kline close at decision time (decision
    logs do not persist fill prices); rows note this via entry_price_source."""
    from database.models.trading import AIDecisionLog

    query = db.query(AIDecisionLog).filter(
        AIDecisionLog.executed == "true",
        AIDecisionLog.realized_pnl.isnot(None),
        AIDecisionLog.realized_pnl < 0,
        AIDecisionLog.operation.in_(("buy", "sell")),
        AIDecisionLog.decision_time
        >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=lookback_days),
    )
    if account_id is not None:
        query = query.filter(AIDecisionLog.account_id == account_id)
    if exchange:
        query = query.filter(AIDecisionLog.exchange == exchange)
    query = query.order_by(AIDecisionLog.decision_time.desc()).limit(limit)

    rows = []
    skipped = 0
    for log in query.all():
        try:
            snapshot = json.loads(log.decision_snapshot or "{}")
        except (TypeError, ValueError):
            snapshot = {}
        entry_ts = int(log.decision_time.replace(tzinfo=timezone.utc).timestamp())
        klines = _load_klines(
            db, log.symbol, exchange or "binance", entry_ts - 5 * 3600, entry_ts + 25 * 3600
        )
        entry_bar = _bar_at_or_before(klines, entry_ts)
        if not entry_bar:
            skipped += 1
            continue
        decision = {
            "decision_id": log.id,
            "symbol": log.symbol,
            "operation": log.operation,
            "entry_price": entry_bar["close"],
            "entry_ts": entry_ts,
            "realized_pnl": float(log.realized_pnl),
            "reason": log.reason,
            "stop_loss_price": snapshot.get("stop_loss_price"),
            "take_profit_price": snapshot.get("take_profit_price"),
            "leverage": snapshot.get("leverage") or 1,
            "target_portion": float(log.target_portion or 0),
            "prev_portion": float(log.prev_portion or 0),
            "signal_trigger_id": log.signal_trigger_id,
        }
        row = analyze_loss(decision, klines)
        row["decision_time"] = log.decision_time.isoformat()
        row["entry_price_source"] = "kline_close_at_decision"
        rows.append(row)

    report = aggregate_attribution(rows)
    report["skipped_no_klines"] = skipped
    report["losses"] = rows
    return report
