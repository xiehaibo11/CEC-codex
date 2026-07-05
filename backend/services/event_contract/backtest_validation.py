"""Validation-report helpers for event-contract backtest credibility."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Dict, Iterable, List

from services.event_contract.constants import PERIOD_SECONDS


MONTE_CARLO_SIMULATIONS = 200
MONTE_CARLO_SEED = 20260701


def build_backtest_validation_report(
    *,
    cfg: Dict[str, Any],
    trades: List[Dict[str, Any]],
    skipped: Dict[str, int],
    data_quality: Dict[str, Any],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a deterministic credibility report from already-settled trades.

    This does not alter settlement math or create new trades. It audits the
    realized trade stream for sample-window stability, sequence/sample risk,
    regime concentration, and quant-book-style live decay.
    """

    walk_forward = _walk_forward_report(cfg, trades)
    monte_carlo = _monte_carlo_report(trades, cfg)
    regime_stability = _regime_stability_report(cfg, trades)
    live_decay = _live_decay_estimate(
        cfg=cfg,
        skipped=skipped,
        data_quality=data_quality,
        summary=summary,
        walk_forward=walk_forward,
        monte_carlo=monte_carlo,
        regime_stability=regime_stability,
    )
    edge_monotonicity = _edge_monotonicity_report(trades)
    threshold_sensitivity = _threshold_sensitivity_report(cfg, trades)
    warnings = _collect_validation_warnings(
        walk_forward=walk_forward,
        monte_carlo=monte_carlo,
        regime_stability=regime_stability,
        live_decay=live_decay,
    )
    if edge_monotonicity.get("verdict") == "flat_or_inverted":
        warnings.append("Edge 分数与实际胜率无单调关系：打分模型对该窗口无区分度")
    for dim in threshold_sensitivity.get("dimensions", []):
        if abs(dim.get("win_rate_delta") or 0) > 15:
            warnings.append(
                f"参数敏感：收紧 {dim['param']} 后胜率变化 {dim['win_rate_delta']:+.1f} 个百分点（>15），结果对该阈值不稳健"
            )
    verdict = _validation_verdict(
        summary=summary,
        walk_forward=walk_forward,
        monte_carlo=monte_carlo,
        regime_stability=regime_stability,
        live_decay=live_decay,
    )
    return {
        "version": "validation-v1",
        "verdict": verdict,
        "warnings": warnings,
        "walk_forward": walk_forward,
        "monte_carlo": monte_carlo,
        "regime_stability": regime_stability,
        "live_decay_estimate": live_decay,
        "edge_monotonicity": edge_monotonicity,
        "threshold_sensitivity": threshold_sensitivity,
    }


def _edge_monotonicity_report(
    trades: List[Dict[str, Any]], groups: int = 4, min_samples: int = 40
) -> Dict[str, Any]:
    """Quantile-monotonicity check: do higher edge scores actually win more?

    Quant-book layered test adapted to event contracts: decided trades are
    ranked by edge score into quantile groups; a scoring model with real
    discriminative power shows win rate rising from bottom to top group. A
    flat or inverted profile means the score is noise for this window.
    """
    samples = []
    for trade in trades:
        if trade.get("result") not in ("win", "loss"):
            continue
        signal = trade.get("event_signal") or {}
        # Prefer the unclamped raw score: the clamped edge_score saturates at
        # 100 for most accepted setups and carries no rank information.
        score = signal.get("edge_score_raw")
        if score is None:
            score = signal.get("edge_score")
        if score is None:
            score = trade.get("signal_strength")
        if score is None:
            continue
        samples.append((float(score), 1.0 if trade["result"] == "win" else 0.0))
    if len(samples) < min_samples:
        return {"status": "insufficient_sample", "n": len(samples), "min_samples": min_samples}

    samples.sort(key=lambda item: item[0])
    size = len(samples) / groups
    buckets = []
    for group in range(groups):
        rows = samples[int(round(group * size)) : int(round((group + 1) * size))]
        if not rows:
            continue
        buckets.append(
            {
                "group": group + 1,
                "n": len(rows),
                "avg_score": round(sum(score for score, _ in rows) / len(rows), 2),
                "win_rate": round(sum(won for _, won in rows) / len(rows) * 100, 2),
            }
        )
    inversions = sum(
        1 for prev, cur in zip(buckets, buckets[1:]) if cur["win_rate"] < prev["win_rate"]
    )
    spread = round(buckets[-1]["win_rate"] - buckets[0]["win_rate"], 2)
    if spread > 0 and inversions == 0:
        verdict = "monotonic"
    elif spread > 0:
        verdict = "partial"
    else:
        verdict = "flat_or_inverted"
    return {
        "status": "ok",
        "n": len(samples),
        "groups": buckets,
        "inversions": inversions,
        "top_minus_bottom": spread,
        "verdict": verdict,
    }


def _threshold_sensitivity_report(
    cfg: Dict[str, Any], trades: List[Dict[str, Any]], tighten_factor: float = 0.8
) -> Dict[str, Any]:
    """Tighten-only parameter perturbation on the realized trade stream.

    The quant-book robustness test perturbs parameters +/-20% and expects
    results to stay stable. Loosening a gate would admit trades we never
    simulated, so only the tightening direction can be evaluated honestly
    from recorded trades; each dimension re-scores the subset that would
    survive a 20% stricter gate.
    """
    decided = [t for t in trades if t.get("result") in ("win", "loss")]
    if len(decided) < 10:
        return {"status": "insufficient_sample", "n": len(decided), "min_samples": 10}

    def _metrics(items: List[Dict[str, Any]]) -> Dict[str, float]:
        wins = sum(1 for t in items if t["result"] == "win")
        return {
            "win_rate": round(wins / len(items) * 100, 2) if items else 0.0,
            "pnl": round(sum(float(t.get("profit_loss") or 0) for t in items), 4),
        }

    base = _metrics(decided)
    dimensions = []

    max_range_risk = float(cfg.get("max_trade_range_risk") or 45)
    tightened_risk = round(max_range_risk * tighten_factor, 2)
    kept = [
        t
        for t in decided
        if float((t.get("event_signal") or {}).get("range_risk") or 0) <= tightened_risk
    ]
    if kept:
        kept_metrics = _metrics(kept)
        dimensions.append(
            {
                "param": "max_trade_range_risk",
                "base_value": max_range_risk,
                "tightened_value": tightened_risk,
                "trades_kept": len(kept),
                "kept_ratio": round(len(kept) / len(decided) * 100, 2),
                "win_rate": kept_metrics["win_rate"],
                "win_rate_delta": round(kept_metrics["win_rate"] - base["win_rate"], 2),
                "pnl": kept_metrics["pnl"],
            }
        )

    target_win_rate = float(cfg.get("target_win_rate") or 75)
    raised_floor = min(target_win_rate + 5, 100.0)
    kept = [
        t
        for t in decided
        if float((t.get("event_signal") or {}).get("expected_win_rate") or 0) >= raised_floor
    ]
    if kept:
        kept_metrics = _metrics(kept)
        dimensions.append(
            {
                "param": "expected_win_rate_floor",
                "base_value": target_win_rate,
                "tightened_value": raised_floor,
                "trades_kept": len(kept),
                "kept_ratio": round(len(kept) / len(decided) * 100, 2),
                "win_rate": kept_metrics["win_rate"],
                "win_rate_delta": round(kept_metrics["win_rate"] - base["win_rate"], 2),
                "pnl": kept_metrics["pnl"],
            }
        )

    return {
        "status": "ok",
        "direction": "tighten_only",
        "base_win_rate": base["win_rate"],
        "base_pnl": base["pnl"],
        "base_trades": len(decided),
        "dimensions": dimensions,
    }


def _walk_forward_report(cfg: Dict[str, Any], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(trades)
    target_win_rate = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    if total == 0:
        return {
            "window_count": 0,
            "pass_rate": 0.0,
            "stability_score": 0.0,
            "worst_window_win_rate": 0.0,
            "worst_window_pnl": 0.0,
            "windows": [],
        }

    window_count = _window_count(total)
    window_size = max(1, math.ceil(total / window_count))
    windows = []
    for idx, start in enumerate(range(0, total, window_size), start=1):
        chunk = trades[start : start + window_size]
        metrics = _trade_metrics(chunk)
        window_passed = metrics["trade_count"] >= 3 and metrics["win_rate"] >= target_win_rate and metrics["pnl"] > 0
        windows.append(
            {
                "window": idx,
                "start_trade_index": int(chunk[0].get("trade_index") or start + 1),
                "end_trade_index": int(chunk[-1].get("trade_index") or start + len(chunk)),
                "trade_count": metrics["trade_count"],
                "win_rate": metrics["win_rate"],
                "pnl": metrics["pnl"],
                "max_drawdown": metrics["max_drawdown"],
                "passed": window_passed,
            }
        )

    pass_rate = round(sum(1 for item in windows if item["passed"]) / len(windows) * 100, 2) if windows else 0.0
    worst_by_pnl = min(windows, key=lambda item: (item["pnl"], item["win_rate"])) if windows else None
    worst_win_rate = min((item["win_rate"] for item in windows), default=0.0)
    worst_pnl = float(worst_by_pnl["pnl"]) if worst_by_pnl else 0.0
    stability_score = _clamp(pass_rate * 0.65 + max(0.0, 100.0 - abs(min(worst_pnl, 0.0))) * 0.15 + worst_win_rate * 0.20)
    return {
        "window_count": len(windows),
        "pass_rate": pass_rate,
        "stability_score": round(stability_score, 2),
        "worst_window_win_rate": round(worst_win_rate, 2),
        "worst_window_pnl": round(worst_pnl, 4),
        "windows": windows,
    }


def _monte_carlo_report(
    trades: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    simulations: int = MONTE_CARLO_SIMULATIONS,
) -> Dict[str, Any]:
    pnls = [float(trade.get("profit_loss") or 0.0) for trade in trades]
    non_overlapping = bool(cfg.get("non_overlapping_only", True))
    interval = PERIOD_SECONDS.get(str(cfg.get("period") or "1m"), 60)
    block_length = max(1, math.ceil(int(cfg.get("expiry_minutes") or 5) * 60 / interval))
    method = "iid" if non_overlapping else "block"
    if not pnls:
        return {
            "simulations": 0,
            "method": method,
            "block_length": block_length,
            "profitable_ratio": 0.0,
            "p5_pnl": 0.0,
            "p50_pnl": 0.0,
            "p95_pnl": 0.0,
            "max_drawdown_p95": 0.0,
        }

    rng = random.Random(MONTE_CARLO_SEED)
    totals: List[float] = []
    drawdowns: List[float] = []
    for _ in range(simulations):
        if method == "iid" or block_length >= len(pnls):
            sampled = [rng.choice(pnls) for _ in pnls]
        else:
            sampled = []
            while len(sampled) < len(pnls):
                start = rng.randrange(0, len(pnls) - block_length + 1)
                sampled.extend(pnls[start : start + block_length])
            sampled = sampled[: len(pnls)]
        totals.append(round(sum(sampled), 4))
        drawdowns.append(round(_max_drawdown_from_pnls(sampled), 4))

    return {
        "simulations": simulations,
        "method": method,
        "block_length": block_length,
        "profitable_ratio": round(sum(1 for total in totals if total > 0) / simulations * 100, 2),
        "p5_pnl": round(_percentile(totals, 5), 4),
        "p50_pnl": round(_percentile(totals, 50), 4),
        "p95_pnl": round(_percentile(totals, 95), 4),
        "max_drawdown_p95": round(_percentile(drawdowns, 95), 4),
    }


def _regime_stability_report(cfg: Dict[str, Any], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    target_win_rate = float(cfg.get("target_win_rate") if cfg.get("target_win_rate") is not None else 75)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("market_state") or "unknown")].append(trade)

    regimes = []
    for name, items in sorted(grouped.items()):
        metrics = _trade_metrics(items)
        unstable = metrics["trade_count"] >= 3 and (metrics["pnl"] < 0 or metrics["win_rate"] < target_win_rate)
        regimes.append({"regime": name, **metrics, "unstable": unstable})

    weakest = min(regimes, key=lambda item: (item["pnl"], item["win_rate"])) if regimes else None
    unstable_count = sum(1 for item in regimes if item["unstable"])
    return {
        "regime_count": len(regimes),
        "weakest_regime": weakest["regime"] if weakest else None,
        "unstable_regime_count": unstable_count,
        "by_regime": regimes,
    }


def _live_decay_estimate(
    *,
    cfg: Dict[str, Any],
    skipped: Dict[str, int],
    data_quality: Dict[str, Any],
    summary: Dict[str, Any],
    walk_forward: Dict[str, Any],
    monte_carlo: Dict[str, Any],
    regime_stability: Dict[str, Any],
) -> Dict[str, Any]:
    decay = 50.0
    reasons = ["基础实盘衰减 50%"]
    if float(cfg.get("fee_rate") or 0) <= 0 or float(cfg.get("slippage_bps") or 0) <= 0:
        decay += 15.0
        reasons.append("手续费或滑点为 0，成本假设偏乐观")
    if summary.get("partial"):
        decay += 10.0
        reasons.append("回测为 partial，完整性不足")
    if not summary.get("target_sample_met"):
        decay += 10.0
        reasons.append("样本量未达到目标")
    if int(regime_stability.get("unstable_regime_count") or 0) > 0:
        penalty = min(15.0, float(regime_stability["unstable_regime_count"]) * 5.0)
        decay += penalty
        reasons.append("存在不稳定市场状态")
    if float(walk_forward.get("pass_rate") or 0.0) < 70.0:
        decay += 10.0
        reasons.append("Walk-Forward 通过率偏低")
    if float(monte_carlo.get("profitable_ratio") or 0.0) < 90.0:
        decay += 10.0
        reasons.append("Monte Carlo 盈利比例不足 90%")
    if any(skipped.get(key, 0) for key in ("missing_expiry_count", "expiry_lag_skipped_count", "entry_delay_skipped_count")):
        decay += 5.0
        reasons.append("存在执行或到期跳过样本")
    if _has_quality_warnings(data_quality):
        decay += 5.0
        reasons.append("存在数据质量警告")

    decay = min(90.0, round(decay, 2))
    total_pnl = float(summary.get("total_pnl") or 0.0)
    conservative_pnl = total_pnl * (1.0 - decay / 100.0) if total_pnl >= 0 else total_pnl * (1.0 + decay / 100.0)
    if conservative_pnl > 0 and decay < 65:
        verdict = "pass"
    elif conservative_pnl > 0:
        verdict = "warning"
    else:
        verdict = "fail"
    return {
        "expected_decay_pct": decay,
        "conservative_pnl": round(conservative_pnl, 4),
        "verdict": verdict,
        "reasons": reasons,
    }


def _trade_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    trade_count = len(trades)
    wins = sum(1 for trade in trades if trade.get("result") == "win")
    pnl_values = [float(trade.get("profit_loss") or 0.0) for trade in trades]
    pnl = round(sum(pnl_values), 4)
    return {
        "trade_count": trade_count,
        "win_rate": round(wins / trade_count * 100, 2) if trade_count else 0.0,
        "pnl": pnl,
        "max_drawdown": round(_max_drawdown_from_pnls(pnl_values), 4),
    }


def _window_count(total: int) -> int:
    if total <= 0:
        return 0
    if total < 6:
        return 1
    return min(10, max(3, total // 4))


def _max_drawdown_from_pnls(pnls: Iterable[float]) -> float:
    equity = peak = max_drawdown = 0.0
    for pnl in pnls:
        equity += float(pnl)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _collect_validation_warnings(
    *,
    walk_forward: Dict[str, Any],
    monte_carlo: Dict[str, Any],
    regime_stability: Dict[str, Any],
    live_decay: Dict[str, Any],
) -> List[str]:
    warnings: List[str] = []
    if float(walk_forward.get("pass_rate") or 0.0) < 70.0:
        warnings.append("Walk-Forward 通过率低于 70%")
    if float(monte_carlo.get("profitable_ratio") or 0.0) < 90.0:
        warnings.append("Monte Carlo 盈利比例低于 90%")
    if int(regime_stability.get("unstable_regime_count") or 0) > 0:
        warnings.append("存在不稳定市场状态")
    if live_decay.get("verdict") != "pass":
        warnings.append("保守实盘衰减后结果不可直接放大")
    return warnings


def _validation_verdict(
    *,
    summary: Dict[str, Any],
    walk_forward: Dict[str, Any],
    monte_carlo: Dict[str, Any],
    regime_stability: Dict[str, Any],
    live_decay: Dict[str, Any],
) -> str:
    if not summary.get("target_sample_met") or live_decay.get("verdict") == "fail":
        return "fail"
    if (
        float(walk_forward.get("pass_rate") or 0.0) < 70.0
        or float(monte_carlo.get("profitable_ratio") or 0.0) < 90.0
        or int(regime_stability.get("unstable_regime_count") or 0) > 0
        or live_decay.get("verdict") == "warning"
    ):
        return "warning"
    return "pass"


def _has_quality_warnings(data_quality: Dict[str, Any]) -> bool:
    if data_quality.get("warnings"):
        return True
    return any(bool((data_quality.get(key) or {}).get("warnings")) for key in ("l2", "coinglass"))


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
