"""Event-contract signal payloads and document-level signal taxonomy."""

from __future__ import annotations

from typing import Any, Dict, List

from services.event_contract.localization import join_chinese_reasons, localize_direction


class EventContractSignalMixin:
    def _build_event_signal(
        self,
        cfg: Dict[str, Any],
        latest: Dict[str, Any],
        final_direction: str,
        allow_trade: bool,
        signal_type: str,
        confidence: float,
        signal_strength: float,
        probabilities: Dict[str, float],
        risks: Dict[str, float],
        blocked_reasons: List[str],
        factors: List[Dict[str, Any]],
        ai_consensus: Dict[str, Any],
    ) -> Dict[str, Any]:
        event_signal_type = self._event_signal_type(
            final_direction,
            allow_trade,
            signal_type,
            risks,
            blocked_reasons,
        )
        exhaustion_reversal = bool(ai_consensus.get("exhaustion_reversal")) or bool(
            ai_consensus.get("range_boundary_reversal")
        )
        if exhaustion_reversal:
            # The vote-based probabilities describe the momentum side the trade
            # is deliberately fading; reporting them as this bet's win rate is
            # dishonest (live it produced expected_win_rate=1 on A-grade bets).
            # No calibrated reversal model exists yet, so report no estimate.
            expected_win_rate = None
        else:
            expected_win_rate = (
                probabilities["long"] if final_direction == "long"
                else probabilities["short"] if final_direction == "short"
                else max(probabilities["long"], probabilities["short"])
            )
        entry_ts = self._decision_timestamp(latest, cfg)
        entry_time = self._to_iso(entry_ts)
        expiry_time = self._to_iso(entry_ts + cfg["expiry_minutes"] * 60)
        avoid_condition = join_chinese_reasons(blocked_reasons) if blocked_reasons else ""

        return {
            "signal_id": f"{cfg['symbol']}-{entry_ts}-{event_signal_type}",
            "symbol": cfg["symbol"],
            "signal_type": event_signal_type,
            "direction": final_direction,
            "entry_time": entry_time,
            "entry_price": latest["close"],
            "expiry_time": expiry_time,
            "expiry_minutes": cfg["expiry_minutes"],
            "confidence": round(confidence, 2),
            "signal_strength": round(signal_strength, 2),
            "expected_win_rate": None if expected_win_rate is None else round(expected_win_rate, 2),
            "expected_win_rate_basis": (
                "reversal_flip_unmodeled" if exhaustion_reversal else "vote_consensus"
            ),
            "decision_policy": ai_consensus.get("decision_policy"),
            "edge_score": ai_consensus.get("edge_score"),
            "edge_score_raw": ai_consensus.get("edge_score_raw"),
            "exhaustion_reversal": bool(ai_consensus.get("exhaustion_reversal")),
            "reversal_evidence_score": ai_consensus.get("reversal_evidence_score"),
            "indicator_reversal_score": ai_consensus.get("indicator_reversal_score"),
            "risk_score": ai_consensus.get("risk_score"),
            "execution_score": ai_consensus.get("execution_score"),
            "decision_grade": ai_consensus.get("decision_grade"),
            "trade_readiness": ai_consensus.get("trade_readiness"),
            "veto_reasons": ai_consensus.get("veto_reasons") or [],
            "decision_diagnostics": ai_consensus.get("decision_diagnostics") or {},
            "trap_risk": round(risks["trap"], 2),
            "fake_breakout_risk": round(risks["fake_breakout"], 2),
            "range_risk": round(risks["range"], 2),
            "valid_seconds": 30,
            "entry_condition": self._entry_condition(allow_trade, final_direction, ai_consensus),
            "avoid_condition": avoid_condition,
            "reason": ai_consensus["reason_summary"],
            # Strongest 12 by |normalized_score| - positional truncation hid
            # factors appended late in the list (flow, L2, MA cross).
            "related_factors": [
                item["factor_name"]
                for item in sorted(
                    factors,
                    key=lambda f: abs(f.get("normalized_score") or 0),
                    reverse=True,
                )[:12]
            ],
            "ai_consensus": ai_consensus,
        }

    def _event_signal_type(
        self,
        final_direction: str,
        allow_trade: bool,
        signal_type: str,
        risks: Dict[str, float],
        blocked_reasons: List[str],
    ) -> str:
        if allow_trade and final_direction == "long":
            return "LONG_5M_EVENT"
        if allow_trade and final_direction == "short":
            return "SHORT_5M_EVENT"
        if risks["fake_breakout"] > 60:
            return "FAKE_BREAKOUT_WARNING"
        if risks["bull_trap"] > 50:
            return "BULL_TRAP_WARNING"
        if risks["bear_trap"] > 50:
            return "BEAR_TRAP_WARNING"
        if risks["range"] > 70:
            return "RANGE_MIDDLE_WARNING"
        if any(self._is_critical_hold_reason(reason) for reason in blocked_reasons):
            return "NO_TRADE_ZONE"
        if signal_type == "watch_signal" and final_direction == "long":
            return "WATCH_LONG"
        if signal_type == "watch_signal" and final_direction == "short":
            return "WATCH_SHORT"
        return "HOLD"

    def _entry_condition(
        self,
        allow_trade: bool,
        final_direction: str,
        ai_consensus: Dict[str, Any],
    ) -> str:
        if not allow_trade:
            return "暂无立即入场条件：事件信号不是交易信号。"
        if ai_consensus.get("decision_policy") == "professional_v1":
            return (
                f"专业决策通过：优势 {ai_consensus.get('edge_score', 0):.2f}；"
                f"风险 {ai_consensus.get('risk_score', 0):.2f}；"
                f"执行 {ai_consensus.get('execution_score', 0):.2f}；"
                f"等级 {ai_consensus.get('decision_grade', '-') }。"
            )
        votes = ai_consensus.get("top_votes", 0)
        total = ai_consensus.get("reviewer_count", 0)
        required = ai_consensus.get("required_votes", 0)
        direction = localize_direction(final_direction)
        if ai_consensus.get("exhaustion_reversal"):
            momentum = localize_direction("long" if final_direction == "short" else "short")
            return (
                f"{votes}/{total} 票动量{momentum}，衰竭反手{direction}"
                f"（要求 {required}/{total}）；"
                f"信号强度 {ai_consensus['signal_strength']:.2f}；"
                f"共识率 {ai_consensus['consensus_rate']:.2f}%。"
            )
        return (
            f"{votes}/{total} 票支持{direction}（要求 {required}/{total}）；"
            f"信号强度 {ai_consensus['signal_strength']:.2f}；"
            f"共识率 {ai_consensus['consensus_rate']:.2f}%。"
        )

    @staticmethod
    def _is_critical_hold_reason(reason: str) -> bool:
        return (
            "Critical" in reason
            or ("关键" in reason and "选择观望" in reason)
        )
