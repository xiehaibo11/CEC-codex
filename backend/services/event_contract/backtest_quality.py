"""Quality gate scoring for event-contract backtest summaries."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def build_backtest_quality_gate(
    cfg: Dict[str, Any],
    trades: List[Dict[str, Any]],
    skipped: Dict[str, int],
    data_quality: Dict[str, Any],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a compact, UI-friendly audit of whether a backtest is trustworthy.

    The quality gate intentionally does not change settlement, win-rate, or PnL
    math. It only scores research credibility using inputs already produced by
    the backtest engine.
    """

    score = 100
    checks: List[Dict[str, Any]] = []
    recommendations: List[str] = []

    def add_check(
        check_id: str,
        label: str,
        status: str,
        message: str,
        deduction: int = 0,
        recommendation: str | None = None,
    ) -> None:
        nonlocal score
        score -= deduction
        checks.append(
            {
                "id": check_id,
                "label": label,
                "status": status,
                "message": message,
                "deduction": deduction,
            }
        )
        if recommendation:
            recommendations.append(recommendation)

    total_trades = len(trades)
    target_min_trades = int(_value_or_default(summary, cfg, "target_min_trades", 10))
    if total_trades < target_min_trades:
        add_check(
            "sample_size",
            "Minimum sample size",
            "fail",
            f"Only {total_trades} settled trades; target requires at least {target_min_trades}.",
            25,
            "Increase the backtest window or loosen filters until the sample size reaches the target.",
        )
    else:
        add_check(
            "sample_size",
            "Minimum sample size",
            "pass",
            f"{total_trades} settled trades meets the target of {target_min_trades}.",
        )

    if summary.get("partial"):
        partial_reasons = _partial_reasons(skipped, data_quality)
        add_check(
            "audit_completeness",
            "Backtest completeness",
            "fail",
            "Backtest is partial: " + "; ".join(partial_reasons),
            25,
            "Do not treat target win-rate pass/fail as final until the partial causes are resolved.",
        )
    else:
        add_check(
            "audit_completeness",
            "Backtest completeness",
            "pass",
            "No partial-run conditions were detected.",
        )

    quality_warnings = _collect_quality_warnings(data_quality)
    if quality_warnings:
        add_check(
            "data_quality",
            "Data quality",
            "warning",
            "; ".join(quality_warnings[:4]),
            15,
            "Review K-line, L2, and CoinGlass coverage before trusting the result.",
        )
    else:
        add_check("data_quality", "Data quality", "pass", "No data-quality warnings were reported.")

    fee_rate = float(cfg.get("fee_rate") or 0)
    slippage_bps = float(cfg.get("slippage_bps") or 0)
    if fee_rate <= 0 and slippage_bps <= 0:
        add_check(
            "execution_costs",
            "Execution costs",
            "warning",
            "Fee rate and slippage are both zero; results may be optimistic.",
            18,
            "Set non-zero fee and slippage for realistic execution costs.",
        )
    elif fee_rate <= 0 or slippage_bps <= 0:
        missing = "fee rate" if fee_rate <= 0 else "slippage"
        add_check(
            "execution_costs",
            "Execution costs",
            "warning",
            f"{missing} is zero; execution costs may be understated.",
            8,
            "Use conservative fee and slippage assumptions before live-trading decisions.",
        )
    else:
        add_check(
            "execution_costs",
            "Execution costs",
            "pass",
            f"Fee rate {fee_rate:g} and slippage {slippage_bps:g} bps are included.",
        )

    ai_skipped = int(skipped.get("ai_skipped_cap_count") or 0)
    if ai_skipped:
        add_check(
            "ai_evaluation_cap",
            "AI evaluation cap",
            "warning",
            f"{ai_skipped} candidate signals were skipped after reaching the AI evaluation cap.",
            10,
            "Increase max AI evaluations or use rule-only mode for full-window deterministic scans.",
        )
    else:
        add_check(
            "ai_evaluation_cap",
            "AI evaluation cap",
            "pass",
            "No candidate signals were skipped by the AI evaluation cap.",
        )

    target_win_rate = float(_value_or_default(summary, cfg, "target_win_rate", 75))
    win_rate = float(summary.get("win_rate") if summary.get("win_rate") is not None else 0)
    if summary.get("target_win_rate_met"):
        add_check(
            "target_edge",
            "Target edge",
            "pass",
            f"Win rate {win_rate:.2f}% meets target {target_win_rate:.2f}% with a complete audit.",
        )
    elif total_trades < target_min_trades or summary.get("partial"):
        add_check(
            "target_edge",
            "Target edge",
            "warning",
            "Target edge cannot be trusted until sample and completeness checks pass.",
            5,
        )
    else:
        add_check(
            "target_edge",
            "Target edge",
            "fail",
            f"Win rate {win_rate:.2f}% is below target {target_win_rate:.2f}%.",
            15,
            "Treat this configuration as rejected unless a broader validation window improves the edge.",
        )

    score = min(100, max(0, score))
    warnings = [check["message"] for check in checks if check["status"] in {"warning", "fail"}]
    status = _overall_status(score, checks)
    return {
        "score": score,
        "grade": _grade(score),
        "status": status,
        "warnings": warnings,
        "checks": checks,
        "recommendations": _dedupe(recommendations),
    }


def _partial_reasons(skipped: Dict[str, int], data_quality: Dict[str, Any]) -> List[str]:
    reason_map = (
        ("ai_skipped_cap_count", "AI evaluation cap skipped candidates"),
        ("missing_expiry_count", "missing expiry bars"),
        ("expiry_lag_skipped_count", "expiry lag exceeded limit"),
        ("entry_delay_skipped_count", "entry delay exceeded limit"),
    )
    reasons = [
        f"{label} ({int(skipped.get(key) or 0)})"
        for key, label in reason_map
        if int(skipped.get(key) or 0) > 0
    ]
    quality_warnings = _collect_quality_warnings(data_quality)
    if quality_warnings:
        reasons.append("data-quality warnings")
    return reasons or ["unknown partial-run condition"]


def _value_or_default(
    primary: Dict[str, Any],
    fallback: Dict[str, Any],
    key: str,
    default: Any,
) -> Any:
    if primary.get(key) is not None:
        return primary[key]
    if fallback.get(key) is not None:
        return fallback[key]
    return default


def _collect_quality_warnings(data_quality: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    warnings.extend(str(item) for item in data_quality.get("warnings") or [])
    for key in ("l2", "coinglass"):
        nested = data_quality.get(key) or {}
        warnings.extend(f"{key}: {item}" for item in nested.get("warnings") or [])
    return warnings


def _overall_status(score: int, checks: List[Dict[str, Any]]) -> str:
    if any(check["status"] == "fail" for check in checks) or score < 50:
        return "fail"
    if any(check["status"] == "warning" for check in checks) or score < 90:
        return "warning"
    return "pass"


def _grade(score: int) -> str:
    thresholds: Tuple[Tuple[int, str], ...] = (
        (90, "A"),
        (80, "B"),
        (65, "C"),
        (50, "D"),
    )
    for threshold, grade in thresholds:
        if score >= threshold:
            return grade
    return "F"


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
