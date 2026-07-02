"""Research-mode diagnostics for event-contract backtests.

The report in this module is intentionally read-only: it never changes trade
selection, settlement, PnL, or validation math.  It turns the already-settled
trade stream into a desk-style research summary that highlights OOS decay,
candidate strategy pockets, factor usefulness, overfitting risk, and missing
data needed before paper/live trading.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence


def build_backtest_research_report(
    *,
    cfg: Dict[str, Any],
    trades: List[Dict[str, Any]],
    skipped: Dict[str, int],
    data_quality: Dict[str, Any],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    ordered_trades = sorted(trades, key=lambda item: int(item.get("trade_index") or 0))
    oos_validation = _oos_validation(cfg, ordered_trades)
    factor_insights = _factor_insights(ordered_trades)
    strategy_candidates = _strategy_candidates(cfg, ordered_trades, oos_validation, factor_insights)
    missing_data = _missing_data_recommendations(cfg, data_quality)
    overfit_warnings = _overfitting_warnings(
        cfg=cfg,
        summary=summary,
        oos=oos_validation,
        candidates=strategy_candidates,
        factors=factor_insights,
        trades=ordered_trades,
        skipped=skipped,
    )
    verdict = _research_verdict(
        cfg=cfg,
        summary=summary,
        oos=oos_validation,
        candidates=strategy_candidates,
        overfit_warnings=overfit_warnings,
        missing_data=missing_data,
    )
    return {
        "version": "research-v1",
        "verdict": verdict,
        "oos_validation": oos_validation,
        "strategy_candidates": strategy_candidates,
        "factor_insights": factor_insights,
        "overfitting_warnings": overfit_warnings,
        "missing_data_recommendations": missing_data,
    }


def _oos_validation(cfg: Dict[str, Any], trades: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(trades)
    target = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    break_even = _break_even_win_rate(cfg)
    if total == 0:
        return {
            "method": "chronological_70_30",
            "train_trade_count": 0,
            "train_win_rate": 0.0,
            "train_pnl": 0.0,
            "oos_trade_count": 0,
            "oos_win_rate": 0.0,
            "oos_pnl": 0.0,
            "win_rate_gap": 0.0,
            "target_win_rate": round(target, 2),
            "break_even_win_rate": round(break_even, 2),
            "overfit_risk": "none",
            "status": "no_trades",
            "summary": "没有成交样本，无法进行样本外验证。",
        }

    split = _split_index(total)
    train = list(trades[:split])
    oos = list(trades[split:])
    train_metrics = _trade_metrics(train)
    oos_metrics = _trade_metrics(oos)
    gap = round(train_metrics["win_rate"] - oos_metrics["win_rate"], 2)
    overfit_risk = _overfit_risk(gap, train_metrics["trade_count"], oos_metrics["trade_count"], oos_metrics["win_rate"], break_even)
    if oos_metrics["trade_count"] < 10:
        status = "insufficient_oos"
        text = "样本外交易数不足，不能证明策略可持续。"
    elif oos_metrics["win_rate"] >= target and gap <= 10:
        status = "pass"
        text = "样本外胜率达到目标且训练/样本外差距可控。"
    elif oos_metrics["win_rate"] >= break_even and gap <= 15:
        status = "watch"
        text = "样本外略高于盈亏平衡，但未达到目标胜率。"
    else:
        status = "fail"
        text = "样本外表现不足，存在衰减或过拟合风险。"
    return {
        "method": "chronological_70_30",
        "train_trade_count": train_metrics["trade_count"],
        "train_win_rate": train_metrics["win_rate"],
        "train_pnl": train_metrics["pnl"],
        "oos_trade_count": oos_metrics["trade_count"],
        "oos_win_rate": oos_metrics["win_rate"],
        "oos_pnl": oos_metrics["pnl"],
        "win_rate_gap": gap,
        "target_win_rate": round(target, 2),
        "break_even_win_rate": round(break_even, 2),
        "split_trade_index": int(trades[split - 1].get("trade_index") or split) if split else 0,
        "overfit_risk": overfit_risk,
        "status": status,
        "summary": text,
    }


def _strategy_candidates(
    cfg: Dict[str, Any],
    trades: Sequence[Dict[str, Any]],
    oos: Dict[str, Any],
    factor_insights: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    split_trade_index = int(oos.get("split_trade_index") or 0)
    candidates.append(_candidate("baseline_all", "当前默认策略", "所有已通过当前交易门槛的成交。", trades, cfg, split_trade_index))
    candidates.append(_candidate("long_only", "只做多", "只保留当前成交流中的做多信号。", [t for t in trades if t.get("direction") == "long"], cfg, split_trade_index))
    candidates.append(_candidate("short_only", "只做空", "只保留当前成交流中的做空信号。", [t for t in trades if t.get("direction") == "short"], cfg, split_trade_index))

    for state in sorted({str(t.get("market_state") or "unknown") for t in trades}):
        items = [t for t in trades if str(t.get("market_state") or "unknown") == state]
        if len(items) >= 5:
            candidates.append(
                _candidate(
                    f"regime_{state}",
                    f"市场状态：{state}",
                    "按市场状态拆分的候选，用于检查Regime路由是否有价值。",
                    items,
                    cfg,
                    split_trade_index,
                )
            )

    for insight in factor_insights[:5]:
        name = insight["factor_name"]
        threshold = insight["win_mean"] if insight["direction"] == "positive_edge" else insight["loss_mean"]
        if insight["direction"] == "positive_edge":
            items = [t for t in trades if _factor_value(t, name) is not None and _factor_value(t, name) >= threshold]
            label = f"因子高值：{name}"
            desc = f"{name} >= {threshold:.6g} 的候选；只用于研究，不代表可交易。"
        else:
            items = [t for t in trades if _factor_value(t, name) is not None and _factor_value(t, name) <= threshold]
            label = f"因子低值：{name}"
            desc = f"{name} <= {threshold:.6g} 的候选；只用于研究，不代表可交易。"
        if len(items) >= 5:
            candidates.append(_candidate(f"factor_{_safe_id(name)}", label, desc, items, cfg, split_trade_index))

    unique: Dict[str, Dict[str, Any]] = {}
    for item in candidates:
        unique[item["candidate_id"]] = item
    ordered = list(unique.values())
    baseline = [item for item in ordered if item["candidate_id"] == "baseline_all"]
    rest = [item for item in ordered if item["candidate_id"] != "baseline_all"]
    rest.sort(key=lambda item: (item["recommendation_rank"], item["oos_win_rate"], item["win_rate"], item["trade_count"]), reverse=True)
    return (baseline + rest)[:12]


def _candidate(
    candidate_id: str,
    name: str,
    description: str,
    trades: Sequence[Dict[str, Any]],
    cfg: Dict[str, Any],
    split_trade_index: int,
) -> Dict[str, Any]:
    target = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    break_even = _break_even_win_rate(cfg)
    metrics = _trade_metrics(trades)
    train = [t for t in trades if int(t.get("trade_index") or 0) <= split_trade_index]
    oos = [t for t in trades if int(t.get("trade_index") or 0) > split_trade_index]
    train_metrics = _trade_metrics(train)
    oos_metrics = _trade_metrics(oos)
    gap = round(train_metrics["win_rate"] - oos_metrics["win_rate"], 2)
    risk = _overfit_risk(gap, train_metrics["trade_count"], oos_metrics["trade_count"], oos_metrics["win_rate"], break_even)
    if metrics["trade_count"] < max(10, int(cfg.get("target_min_trades") or 10)):
        recommendation = "样本不足"
        rank = 0
    elif risk in {"critical", "high"}:
        recommendation = "高过拟合风险，不建议交易"
        rank = 1
    elif oos_metrics["win_rate"] >= target and metrics["pnl"] > 0:
        recommendation = "可进入纸盘观察"
        rank = 4
    elif oos_metrics["win_rate"] >= break_even and metrics["pnl"] > 0:
        recommendation = "研究候选，继续观察"
        rank = 3
    else:
        recommendation = "拒绝，未超过可交易门槛"
        rank = 2
    return {
        "candidate_id": candidate_id,
        "name": name,
        "description": description,
        "trade_count": metrics["trade_count"],
        "win_rate": metrics["win_rate"],
        "pnl": metrics["pnl"],
        "train_trade_count": train_metrics["trade_count"],
        "train_win_rate": train_metrics["win_rate"],
        "oos_trade_count": oos_metrics["trade_count"],
        "oos_win_rate": oos_metrics["win_rate"],
        "oos_pnl": oos_metrics["pnl"],
        "win_rate_gap": gap,
        "overfit_risk": risk,
        "recommendation": recommendation,
        "recommendation_rank": rank,
    }


def _factor_insights(trades: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"wins": [], "losses": [], "category": "unknown"})
    for trade in trades:
        won = trade.get("result") == "win"
        for factor in trade.get("factor_snapshot") or []:
            name = str(factor.get("factor_name") or "").strip()
            if not name:
                continue
            value = _as_float(factor.get("value"))
            if value is None:
                continue
            grouped[name]["category"] = factor.get("category") or grouped[name]["category"]
            (grouped[name]["wins"] if won else grouped[name]["losses"]).append(value)

    insights = []
    for name, payload in grouped.items():
        wins = payload["wins"]
        losses = payload["losses"]
        sample_count = len(wins) + len(losses)
        if sample_count < 4 or not wins or not losses:
            continue
        win_mean = _mean(wins)
        loss_mean = _mean(losses)
        values = wins + losses
        span = max(values) - min(values)
        raw_gap = abs(win_mean - loss_mean)
        separation = raw_gap / span * 100 if span else raw_gap * 100
        direction = "positive_edge" if win_mean > loss_mean else "negative_edge"
        if sample_count < 30:
            reliability = "low_sample"
        elif separation >= 35:
            reliability = "strong"
        elif separation >= 18:
            reliability = "medium"
        else:
            reliability = "weak"
        insights.append(
            {
                "factor_name": name,
                "category": str(payload["category"]),
                "sample_count": sample_count,
                "win_mean": round(win_mean, 6),
                "loss_mean": round(loss_mean, 6),
                "separation_score": round(separation, 2),
                "direction": direction,
                "reliability": reliability,
                "interpretation": _factor_interpretation(name, direction, reliability),
            }
        )
    insights.sort(key=lambda item: (item["separation_score"], item["sample_count"]), reverse=True)
    return insights[:15]


def _overfitting_warnings(
    *,
    cfg: Dict[str, Any],
    summary: Dict[str, Any],
    oos: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
    factors: Sequence[Dict[str, Any]],
    trades: Sequence[Dict[str, Any]],
    skipped: Dict[str, int],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    if oos.get("overfit_risk") in {"high", "critical"}:
        warnings.append(
            {
                "severity": "critical" if oos.get("overfit_risk") == "critical" else "high",
                "message": "训练集与样本外胜率差距过大，疑似过拟合或市场状态衰减。",
                "evidence": (
                    f"训练 {oos.get('train_win_rate')}%，样本外 {oos.get('oos_win_rate')}%，"
                    f"差距 {oos.get('win_rate_gap')}%。"
                ),
            }
        )
    if len(trades) < int(cfg.get("target_min_trades") or 10):
        warnings.append(
            {
                "severity": "high",
                "message": "成交样本低于目标样本量，漂亮胜率没有统计意义。",
                "evidence": f"交易数 {len(trades)} < 目标 {cfg.get('target_min_trades') or 10}。",
            }
        )
    small_high = [
        item
        for item in candidates
        if item["trade_count"] < 30 and item["win_rate"] >= float(cfg.get("target_win_rate") or 75)
    ]
    if small_high:
        warnings.append(
            {
                "severity": "medium",
                "message": "发现小样本高胜率候选，不能当作可交易结论。",
                "evidence": "；".join(f"{item['name']} n={item['trade_count']} win={item['win_rate']}%" for item in small_high[:3]),
            }
        )
    decayed = [
        item
        for item in candidates
        if item["win_rate"] >= float(cfg.get("target_win_rate") or 75)
        and item["oos_trade_count"] > 0
        and item["oos_win_rate"] < item["win_rate"] - 15
    ]
    if decayed:
        warnings.append(
            {
                "severity": "high",
                "message": "候选策略总胜率漂亮，但样本外明显衰减。",
                "evidence": "；".join(f"{item['name']} 总={item['win_rate']}% OOS={item['oos_win_rate']}%" for item in decayed[:3]),
            }
        )
    if any(item.get("reliability") == "low_sample" and item.get("separation_score", 0) >= 35 for item in factors):
        warnings.append(
            {
                "severity": "medium",
                "message": "部分因子区分度高但样本不足，可能是数据挖掘噪声。",
                "evidence": "低样本强因子需要更长窗口复核。",
            }
        )
    if float(summary.get("win_rate") or 0) < float(summary.get("break_even_win_rate") or _break_even_win_rate(cfg)):
        warnings.append(
            {
                "severity": "high",
                "message": "默认策略低于盈亏平衡线，不能因为局部候选漂亮就放大。",
                "evidence": f"默认胜率 {summary.get('win_rate')}%，盈亏平衡 {summary.get('break_even_win_rate')}%。",
            }
        )
    if int(skipped.get("ai_skipped_cap_count") or 0) > 0:
        warnings.append(
            {
                "severity": "medium",
                "message": "AI评估上限跳过候选，回测不是完整窗口。",
                "evidence": f"跳过 {skipped.get('ai_skipped_cap_count')} 个候选。",
            }
        )
    return warnings


def _missing_data_recommendations(cfg: Dict[str, Any], data_quality: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    l2 = data_quality.get("l2") or {}
    if not l2.get("enabled") or l2.get("warnings") or float(l2.get("coverage_pct") or 0) < float(cfg.get("min_l2_coverage_pct") or 96):
        items.append(
            {
                "data_type": "L2 orderbook",
                "status": "missing_or_low_coverage",
                "recommendation": "补充盘口深度、spread、imbalance和快照延迟；否则执行可行性只能用OHLCV代理。",
            }
        )
    cg = data_quality.get("coinglass") or {}
    if not cg.get("enabled") or cg.get("warnings") or float(cg.get("coverage_pct") or 0) < float(cfg.get("min_coinglass_coverage_pct") or 96):
        items.append(
            {
                "data_type": "CoinGlass derivatives",
                "status": "missing_or_low_coverage",
                "recommendation": "补充CVD、taker buy/sell、OI、funding、liquidation，并保持无未来函数对齐。",
            }
        )
    if float(cfg.get("fee_rate") or 0) <= 0 or float(cfg.get("slippage_bps") or 0) <= 0:
        items.append(
            {
                "data_type": "Execution costs",
                "status": "optimistic_assumption",
                "recommendation": "手续费和滑点不能为0；加入真实费率、冲击成本和延迟后再判断可交易性。",
            }
        )
    if int(cfg.get("delay_seconds") or 0) <= 0:
        items.append(
            {
                "data_type": "Execution latency",
                "status": "not_modeled",
                "recommendation": "加入信号生成到下单的延迟、订单失败和成交价偏移，避免理想成交偏差。",
            }
        )
    return items


def _research_verdict(
    *,
    cfg: Dict[str, Any],
    summary: Dict[str, Any],
    oos: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
    overfit_warnings: Sequence[Dict[str, Any]],
    missing_data: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    target = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    break_even = float(summary.get("break_even_win_rate") or _break_even_win_rate(cfg))
    critical = any(item.get("severity") == "critical" for item in overfit_warnings)
    best = max(candidates, key=lambda item: (item["recommendation_rank"], item["oos_win_rate"], item["win_rate"]), default=None)
    reasons: List[str] = []
    if float(summary.get("win_rate") or 0) < break_even:
        reasons.append("默认策略低于盈亏平衡。")
    if oos.get("status") in {"fail", "insufficient_oos", "no_trades"}:
        reasons.append(oos.get("summary") or "样本外验证未通过。")
    if critical:
        reasons.append("存在关键过拟合警告。")
    if missing_data:
        reasons.append("关键盘口/衍生品/执行成本数据仍不完整。")
    if best and best.get("recommendation") == "可进入纸盘观察" and not critical:
        status = "paper_candidate"
        label = "可进入纸盘观察"
    elif float(summary.get("win_rate") or 0) >= break_even and not critical:
        status = "watch"
        label = "研究观察"
    else:
        status = "rejected"
        label = "不可交易"
    if float(summary.get("win_rate") or 0) >= target and oos.get("oos_win_rate", 0) < target:
        reasons.append("总胜率达到目标但样本外没有达到目标。")
    return {
        "status": status,
        "label": label,
        "best_candidate_id": best.get("candidate_id") if best else None,
        "best_candidate_name": best.get("name") if best else None,
        "reasons": reasons or ["研究报告未发现硬性拒绝项，但仍需纸盘前瞻验证。"],
    }


def _trade_metrics(trades: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    trade_count = len(trades)
    wins = sum(1 for trade in trades if trade.get("result") == "win")
    pnl = round(sum(float(trade.get("profit_loss") or 0) for trade in trades), 4)
    return {
        "trade_count": trade_count,
        "wins": wins,
        "win_rate": round(wins / trade_count * 100, 2) if trade_count else 0.0,
        "pnl": pnl,
    }


def _split_index(total: int) -> int:
    if total <= 1:
        return total
    return min(total - 1, max(1, int(total * 0.70)))


def _overfit_risk(gap: float, train_count: int, oos_count: int, oos_win_rate: float, break_even: float) -> str:
    if train_count == 0 and oos_count == 0:
        return "none"
    if oos_count < 10:
        return "high"
    if gap >= 25 or (gap >= 15 and oos_win_rate < break_even):
        return "critical"
    if gap >= 15:
        return "high"
    if gap >= 8:
        return "medium"
    return "low"


def _break_even_win_rate(cfg: Dict[str, Any]) -> float:
    stake = float(cfg.get("stake_amount") or 100)
    payout = float(cfg.get("win_payout_ratio") or 0.8)
    fee = stake * float(cfg.get("fee_rate") or 0)
    if payout <= -1:
        return 100.0
    return round((stake + fee) / (stake * (payout + 1)) * 100, 2)


def _factor_value(trade: Dict[str, Any], name: str) -> float | None:
    for factor in trade.get("factor_snapshot") or []:
        if factor.get("factor_name") == name:
            return _as_float(factor.get("value"))
    return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "factor"


def _factor_interpretation(name: str, direction: str, reliability: str) -> str:
    edge_text = "赢单均值更高" if direction == "positive_edge" else "输单均值更高，可能需要反向或过滤"
    reliability_text = {
        "strong": "区分度强",
        "medium": "区分度中等",
        "weak": "区分度弱",
        "low_sample": "样本不足",
    }.get(reliability, reliability)
    return f"{name}：{edge_text}；{reliability_text}。"
