"""Feature computation and snapshot analysis for event-contract signals."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.event_contract.constants import (
    DEFAULT_REVIEWER_PANEL_SIZE,
    MAIN_LOGIC_REVIEWER_NAME,
)
from services.event_contract.features import EventContractFeatureMixin
from services.event_contract.localization import (
    localize_cvd_source,
    localize_reviewer_names,
    localize_source_label,
)


class EventContractAnalysisMixin(EventContractFeatureMixin):
    def _analyze_snapshot(
        self,
        history: List[Dict[str, Any]],
        cfg: Dict[str, Any],
        decisions_override: Optional[List[Dict[str, Any]]] = None,
        source: str = "system_panel",
        ai_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        features = self._compute_features(history)
        production_mtf = cfg.get("_production_mtf_snapshot")
        if isinstance(production_mtf, dict):
            # The production desk is driven by completed 1m bars aggregated at
            # UTC boundaries. Replace the legacy short-horizon proxy directions
            # only for this path; historical runs keep their old semantics.
            features["production_mtf"] = production_mtf
            features["mtf_dirs"] = dict(production_mtf.get("directions") or {})
            features["mtf_conflict"] = bool(production_mtf.get("conflict", True))
        raw_decisions = list(decisions_override) if decisions_override is not None else self._build_rule_decisions(features, cfg)
        ai_decisions = self._ensure_main_logic_vote(features, cfg, raw_decisions)
        long_votes = sum(1 for item in ai_decisions if item["direction"] == "long")
        short_votes = sum(1 for item in ai_decisions if item["direction"] == "short")
        hold_votes = sum(1 for item in ai_decisions if item["direction"] == "hold")
        reviewer_count = len(ai_decisions)
        panel_size = int(cfg.get("reviewer_panel_size") or DEFAULT_REVIEWER_PANEL_SIZE)
        required_votes = min(max(int(cfg.get("consensus_threshold") or 1), 1), max(reviewer_count, 1))
        # Weighted consensus (Bayesian-learned reviewer weights). Weights default
        # to neutral 1.0 when reviewer_learning hasn't seen enough trades, so cold
        # start behaves identically to the old unweighted vote.
        reviewer_weights = cfg.get("reviewer_weights") or {}
        weighted_long = 0.0
        weighted_short = 0.0
        for item in ai_decisions:
            w = float(reviewer_weights.get(item.get("ai_name"), 1.0))
            if item["direction"] == "long":
                weighted_long += w
            elif item["direction"] == "short":
                weighted_short += w
        weighted_total = weighted_long + weighted_short
        if weighted_total > 0:
            weighted_direction = "long" if weighted_long > weighted_short else "short"
            weighted_consensus_rate = round(
                max(weighted_long, weighted_short) / weighted_total * 100, 2
            )
        else:
            weighted_direction = "hold"
            weighted_consensus_rate = 0.0
        # Simple-majority tally is surfaced, while weighted values can still tilt
        # direction when learned reviewer weights are available.
        top_votes = max(long_votes, short_votes)
        simple_direction = "long" if long_votes > short_votes else "short" if short_votes > long_votes else "hold"
        top_direction = weighted_direction if weighted_direction != "hold" else simple_direction
        consensus_rate = round(top_votes / reviewer_count * 100, 2) if reviewer_count else 0.0
        threshold_consensus_score = min(100.0, round(top_votes / required_votes * 100, 2))
        avg_confidence = sum(item["confidence"] for item in ai_decisions) / reviewer_count
        decision_policy = str(cfg.get("decision_policy") or "professional_v1")
        professional_policy = decision_policy == "professional_v1"
        source_label = localize_source_label(source)
        main_logic_participated = any(item.get("ai_name") == MAIN_LOGIC_REVIEWER_NAME for item in ai_decisions)
        llm_vote_count = sum(1 for item in ai_decisions if item.get("source") == "llm_ai")
        ai_participated = source == "llm_ai" and llm_vote_count >= max(panel_size - 1, 0)

        blocked_reasons: List[str] = []
        veto_reasons: List[str] = []
        critical_holds = [
            item["ai_name"]
            for item in ai_decisions
            if self._is_critical_reviewer(item.get("ai_name", "")) and item["direction"] == "hold"
        ]
        if critical_holds and not professional_policy:
            critical_hold_reason = f"关键{source_label}选择观望：{localize_reviewer_names(critical_holds)}"
            blocked_reasons.append(critical_hold_reason)
            veto_reasons.append(critical_hold_reason)
        watch_threshold = required_votes
        if top_votes < watch_threshold and not professional_policy:
            blocked_reasons.append(
                f"{source_label}共识低于观察阈值："
                f"{top_votes}/{reviewer_count} < {watch_threshold}/{reviewer_count}"
            )
        if cfg["enable_fake_breakout_filter"] and features["fake_breakout_risk"] > 60:
            reason = "假突破风险高于 60"
            blocked_reasons.append(reason)
            veto_reasons.append(reason)
        if cfg["enable_trap_filter"] and features["trap_risk"] > 60:
            reason = "陷阱风险高于 60"
            blocked_reasons.append(reason)
            veto_reasons.append(reason)
        if cfg["enable_range_filter"] and features["range_risk"] > 70:
            reason = "当前价格处于震荡区间中部，属于禁止交易区域"
            blocked_reasons.append(reason)
            veto_reasons.append(reason)
        if cfg["enable_volume_filter"] and features["volume_ratio"] < 0.75 and not professional_policy:
            blocked_reasons.append("成交量确认偏弱")
        if cfg["enable_multi_timeframe_filter"] and features["mtf_conflict"] and not professional_policy:
            blocked_reasons.append("1m/3m/5m/15m 多周期方向冲突")
        if cfg["enable_cvd_filter"] and abs(features["cvd_proxy"]) < 0.08 and not professional_policy:
            cvd_source = localize_cvd_source(str(features["cvd_source"]))
            blocked_reasons.append(f"{cvd_source} CVD 未确认方向")
        factor_gate_reason = self._factor_gate_block_reason(
            history, features, cfg, direction=top_direction
        )
        if factor_gate_reason:
            blocked_reasons.append(factor_gate_reason)
            veto_reasons.append(factor_gate_reason)
        edge_quality_blocked = False
        if cfg.get("enable_edge_quality_gate"):
            target_win_rate = cfg.get("target_win_rate", 75)
            if not cfg.get("allow_pullback_trades", False) and features["market_state"] == "pullback":
                reason = f"{target_win_rate:.0f}% 胜率质量门排除回调行情状态"
                blocked_reasons.append(reason)
                veto_reasons.append(reason)
                edge_quality_blocked = True
            max_range_risk = cfg.get("max_trade_range_risk", 45)
            if features["range_risk"] > max_range_risk:
                reason = (
                    f"{target_win_rate:.0f}% 胜率质量门：震荡区间风险 "
                    f"{features['range_risk']:.2f} > {max_range_risk:.2f}"
                )
                blocked_reasons.append(reason)
                veto_reasons.append(reason)
                edge_quality_blocked = True

        risk_penalty = (features["trap_risk"] + features["fake_breakout_risk"] + features["range_risk"]) / 3
        signal_strength = max(0, min(100, threshold_consensus_score * 0.72 + avg_confidence * 0.28 - risk_penalty * 0.12))
        confidence = max(0, min(100, threshold_consensus_score * 0.68 + avg_confidence * 0.32 - risk_penalty * 0.08))
        professional = self._build_professional_decision(
            cfg=cfg,
            features=features,
            top_direction=top_direction,
            top_votes=top_votes,
            reviewer_count=reviewer_count,
            avg_confidence=avg_confidence,
            veto_reasons=veto_reasons,
            edge_quality_blocked=edge_quality_blocked,
        )
        if professional_policy:
            signal_strength = professional["edge_score"]
            confidence = professional["confidence"]
        if signal_strength < 85 and not professional_policy:
            blocked_reasons.append("信号强度低于 85")
        if confidence < 85 and not professional_policy:
            blocked_reasons.append("置信度低于 85")

        if professional_policy:
            allow_trade = professional["trade_readiness"] == "tradable"
            signal_type = (
                "trade_signal"
                if allow_trade
                else "watch_signal"
                if professional["trade_readiness"] == "watch"
                else "hold_signal"
            )
            final_direction = top_direction if signal_type in ("trade_signal", "watch_signal") else "hold"
        else:
            allow_trade = (
                top_direction in ("long", "short")
                and not critical_holds
                and top_votes >= watch_threshold
                and signal_strength >= 85
                and confidence >= 70
                and not blocked_reasons
            )
            signal_type = "trade_signal" if allow_trade else "watch_signal" if top_votes >= watch_threshold and top_direction != "hold" and not critical_holds else "hold_signal"
            final_direction = top_direction if signal_type in ("trade_signal", "watch_signal") else "hold"
            if critical_holds:
                final_direction = "hold"
                signal_type = "hold_signal"
            if edge_quality_blocked:
                final_direction = "hold"
                signal_type = "hold_signal"
            if not allow_trade and signal_type == "hold_signal":
                final_direction = "hold"

        # Signal-mode dispatch. "exhaustion_fade" (default) is the legacy gate
        # below: momentum + overextension + trap detection flip the direction
        # (fade the move). "trend_follow" is the customer-mandated 只顺大趋势
        # mode: the momentum consensus direction is never flipped; instead the
        # bet must agree with the 60-minute trend and must not chase an RSI
        # overextension (底部顺势做多、高位顺势做空). exhaustion_reversal stays
        # False in trend_follow so reason/entry_condition reporting stays
        # truthful automatically.
        signal_mode = str(cfg.get("signal_mode") or "exhaustion_fade")
        exhaustion_reversal = False
        range_boundary_reversal = False
        if signal_mode == "range_boundary":
            # Tier-2 box strategy: direction comes from the range STRUCTURE
            # (fade the boundary), not from the momentum consensus. Shares the
            # flip machinery with exhaustion_fade but the condition is
            # structural; mid-range and trending tapes are hard-blocked.
            if allow_trade and final_direction in ("long", "short"):
                boundary_direction, boundary_block = self._range_boundary_verdict(
                    features,
                    min_trap_risk=cfg.get("range_min_trap_risk"),
                    min_trend_mag=cfg.get("range_min_trend_mag"),
                )
                if boundary_direction is None:
                    allow_trade = False
                    signal_type = "hold_signal"
                    final_direction = "hold"
                    blocked_reasons.append(boundary_block)
                else:
                    # L2 microstructure confirmation (only when the knobs are
                    # explicitly configured; fail-closed on missing data).
                    l2_block = self._l2_range_filters(boundary_direction, features, cfg)
                    if l2_block is not None:
                        allow_trade = False
                        signal_type = "hold_signal"
                        final_direction = "hold"
                        blocked_reasons.append(l2_block)
                    else:
                        if boundary_direction != final_direction:
                            range_boundary_reversal = True
                        final_direction = boundary_direction
        elif signal_mode == "trend_follow":
            if allow_trade and final_direction in ("long", "short"):
                trend_block = self._trend_follow_block_reason(final_direction, features)
                if trend_block:
                    allow_trade = False
                    signal_type = "hold_signal"
                    final_direction = "hold"
                    blocked_reasons.append(trend_block)
        # Exhaustion reversal gate: momentum + overextension + trap detection + high signal quality.
        # signal_strength >= 89 filters out noisy exhaustion signals (88.8-88.9 were empirical loss points).
        elif allow_trade and final_direction in ("long", "short") and not professional_policy:
            ex_long = features.get("exhaustion_long", False)
            ex_short = features.get("exhaustion_short", False)
            has_exhaustion = (final_direction == "long" and ex_long) or (final_direction == "short" and ex_short)
            if has_exhaustion and signal_strength >= 89.0:
                # High-quality exhaustion: flip direction (fade the momentum)
                final_direction = "short" if final_direction == "long" else "long"
                exhaustion_reversal = True
            else:
                # Either no exhaustion extreme, or signal quality below 89: skip
                allow_trade = False
                signal_type = "hold_signal"
                final_direction = "hold"
                if not has_exhaustion:
                    blocked_reasons.append("未出现衰竭极值：5m 动量信号被阻断")
                else:
                    blocked_reasons.append(
                        f"衰竭信号强度 {signal_strength:.1f} < 89：质量门阻断"
                    )
        elif allow_trade and final_direction in ("long", "short") and professional_policy:
            ex_long = features.get("exhaustion_long", False)
            ex_short = features.get("exhaustion_short", False)
            has_exhaustion = (final_direction == "long" and ex_long) or (final_direction == "short" and ex_short)
            if has_exhaustion and signal_strength >= 89.0:
                final_direction = "short" if final_direction == "long" else "long"
                exhaustion_reversal = True

        long_probability = self._probability_from_votes("long", long_votes, short_votes, hold_votes, features, avg_confidence)
        short_probability = self._probability_from_votes("short", long_votes, short_votes, hold_votes, features, avg_confidence)
        hold_probability = max(0, min(100, 100 - max(long_probability, short_probability)))

        reason_summary = self._build_reason_summary(
            features,
            final_direction,
            top_votes,
            blocked_reasons,
            reviewer_count,
            professional if professional_policy else None,
            exhaustion_reversal=exhaustion_reversal,
            range_boundary_reversal=range_boundary_reversal,
        )
        factors = self._build_factor_snapshot(features)

        entry_ts = self._decision_timestamp(history[-1], cfg)
        ai_consensus = {
            "symbol": cfg["symbol"],
            "contract_type": "5m_event_contract",
            "consensus_mode": cfg["consensus_mode"],
            "decision_policy": decision_policy,
            "consensus_source": source,
            "ai_participated": ai_participated,
            "main_logic_participated": main_logic_participated,
            "main_logic_direction": next(
                (item.get("direction") for item in ai_decisions if item.get("ai_name") == MAIN_LOGIC_REVIEWER_NAME),
                None,
            ),
            "ai_model": (ai_meta or {}).get("model"),
            "ai_account_name": (ai_meta or {}).get("account_name"),
            "entry_time": self._to_iso(entry_ts),
            "expiry_time": self._to_iso(entry_ts + cfg["expiry_minutes"] * 60),
            "entry_price": history[-1]["close"],
            "final_direction": final_direction,
            "long_votes": long_votes,
            "short_votes": short_votes,
            "hold_votes": hold_votes,
            "top_votes": top_votes,
            "top_direction": top_direction,
            "required_votes": watch_threshold,
            "reviewer_count": reviewer_count,
            "reviewer_panel_size": panel_size,
            "weighted_consensus_rate": weighted_consensus_rate,
            "consensus_rate": consensus_rate,
            "edge_score": professional["edge_score"],
            "edge_score_raw": professional["edge_score_raw"],
            "risk_score": professional["risk_score"],
            "execution_score": professional["execution_score"],
            "decision_grade": professional["decision_grade"],
            "trade_readiness": professional["trade_readiness"],
            "veto_reasons": veto_reasons,
            "decision_diagnostics": professional["decision_diagnostics"],
            "allow_trade": allow_trade,
            "exhaustion_reversal": exhaustion_reversal,
            "range_boundary_reversal": range_boundary_reversal,
            "reversal_evidence_score": features.get("coinglass_reversal_score", 0.0),
            "indicator_reversal_score": features.get("indicator_reversal_score", 0.0),
            "signal_type": signal_type,
            "signal_strength": round(signal_strength, 2),
            "future_5m_long_probability": round(long_probability, 2),
            "future_5m_short_probability": round(short_probability, 2),
            "fake_breakout_risk": round(features["fake_breakout_risk"], 2),
            "trap_risk": round(features["trap_risk"], 2),
            "range_risk": round(features["range_risk"], 2),
            "reason_summary": reason_summary,
        }
        event_signal = self._build_event_signal(
            cfg,
            history[-1],
            final_direction,
            allow_trade,
            signal_type,
            confidence,
            signal_strength,
            {
                "long": long_probability,
                "short": short_probability,
                "hold": hold_probability,
            },
            {
                "fake_breakout": features["fake_breakout_risk"],
                "bull_trap": features["bull_trap_risk"],
                "bear_trap": features["bear_trap_risk"],
                "trap": features["trap_risk"],
                "range": features["range_risk"],
            },
            blocked_reasons,
            factors,
            ai_consensus,
        )
        ai_consensus["event_signal_type"] = event_signal["signal_type"]

        return {
            "decision_policy": decision_policy,
            "final_direction": final_direction,
            "allow_trade": allow_trade,
            "signal_type": signal_type,
            "event_signal_type": event_signal["signal_type"],
            "event_signal": event_signal,
            "signal_strength": round(signal_strength, 2),
            "confidence": round(confidence, 2),
            "long_probability": round(long_probability, 2),
            "short_probability": round(short_probability, 2),
            "hold_probability": round(hold_probability, 2),
            "fake_breakout_risk": round(features["fake_breakout_risk"], 2),
            "trap_risk": round(features["trap_risk"], 2),
            "range_risk": round(features["range_risk"], 2),
            "market_state": features["market_state"],
            "edge_score": professional["edge_score"],
            "risk_score": professional["risk_score"],
            "execution_score": professional["execution_score"],
            "decision_grade": professional["decision_grade"],
            "trade_readiness": professional["trade_readiness"],
            "veto_reasons": veto_reasons,
            "decision_diagnostics": professional["decision_diagnostics"],
            "blocked_reasons": blocked_reasons,
            "reason_summary": reason_summary,
            "factors": factors,
            "ai_decisions": ai_decisions,
            "ai_participated": ai_participated,
            "main_logic_participated": main_logic_participated,
            "ai_model": (ai_meta or {}).get("model"),
            "ai_account_name": (ai_meta or {}).get("account_name"),
            "ai_consensus": ai_consensus,
            "exhaustion_reversal": exhaustion_reversal,
        }

    def _build_professional_decision(
        self,
        *,
        cfg: Dict[str, Any],
        features: Dict[str, Any],
        top_direction: str,
        top_votes: int,
        reviewer_count: int,
        avg_confidence: float,
        veto_reasons: List[str],
        edge_quality_blocked: bool,
    ) -> Dict[str, Any]:
        """Score a setup like a trade desk: edge first, then risk veto, then execution realism."""
        vote_rate = (top_votes / reviewer_count * 100) if reviewer_count else 0.0
        trend_component = min(abs(float(features.get("trend_score") or 0.0)) * 100, 35.0)
        volume_component = min(float(features.get("volume_ratio") or 0.0), 3.0) * 6.0
        directional_bonus = 6.0 if top_direction in ("long", "short") else -12.0

        risk_score = self._professional_risk_score(features)
        execution_score = self._professional_execution_score(cfg, features)
        # MA-cross textbook confirmation trio: a fully confirmed cross that
        # agrees with the setup direction is corroboration; a confirmed cross
        # against it is a contradiction; a whipsaw (re-cross inside the
        # lookback) means the direction is undecidable and reads as noise.
        ma_cross_component = 0.0
        ma_dir = features.get("ma_cross_direction")
        if features.get("ma_cross_whipsaw"):
            ma_cross_component = -6.0
        elif features.get("ma_cross_confirmed"):
            if ma_dir == top_direction:
                ma_cross_component = 6.0
            elif top_direction in ("long", "short"):
                ma_cross_component = -10.0
        # Component sum can reach ~146, so the clamped score saturates at 100
        # for nearly every accepted setup. Keep the clamped score for all
        # existing gates (behavior unchanged) but record the raw score too -
        # it is the only version with enough spread to measure whether the
        # scoring model actually rank-orders outcomes (edge monotonicity).
        edge_score_raw = (
            38.0
            + vote_rate * 0.45
            + avg_confidence * 0.20
            + trend_component * 0.55
            + volume_component
            + max(0.0, 45.0 - risk_score) * 0.10
            + directional_bonus
            + ma_cross_component
            - len(veto_reasons) * 32.0
        )
        edge_score = self._clamp_score(edge_score_raw)
        confidence = self._clamp_score(edge_score * 0.72 + execution_score * 0.18 + (100.0 - risk_score) * 0.10)

        hard_veto_count = len(veto_reasons)
        composite_score = self._clamp_score(
            edge_score * 0.50
            + execution_score * 0.25
            + (100.0 - risk_score) * 0.25
            - hard_veto_count * 22.0
        )
        decision_grade = self._grade_from_score(composite_score)

        if (
            top_direction in ("long", "short")
            and hard_veto_count == 0
            and not edge_quality_blocked
            and edge_score >= 75
            and risk_score <= 45
            and execution_score >= 65
            and confidence >= 70
        ):
            trade_readiness = "tradable"
        elif (
            top_direction in ("long", "short")
            and hard_veto_count == 0
            and edge_score >= 62
            and risk_score <= 65
            and execution_score >= 50
        ):
            trade_readiness = "watch"
        else:
            trade_readiness = "blocked"

        diagnostics = {
            "vote_rate": round(vote_rate, 2),
            "top_direction": top_direction,
            "trend_component": round(trend_component, 2),
            "volume_component": round(volume_component, 2),
            "avg_confidence": round(avg_confidence, 2),
            "ma_cross_component": round(ma_cross_component, 2),
            "risk_veto_count": hard_veto_count,
            "composite_score": round(composite_score, 2),
            "edge_threshold": 75,
            "risk_threshold": 45,
            "execution_threshold": 65,
            "readiness_rule": "edge>=75, risk<=45, execution>=65, no hard veto",
        }
        return {
            "edge_score": round(edge_score, 2),
            "edge_score_raw": round(edge_score_raw, 2),
            "risk_score": round(risk_score, 2),
            "execution_score": round(execution_score, 2),
            "confidence": round(confidence, 2),
            "decision_grade": decision_grade,
            "trade_readiness": trade_readiness,
            "decision_diagnostics": diagnostics,
        }

    def _professional_risk_score(self, features: Dict[str, Any]) -> float:
        max_structural_risk = max(
            float(features.get("fake_breakout_risk") or 0.0),
            float(features.get("trap_risk") or 0.0),
            float(features.get("range_risk") or 0.0),
        )
        risk_score = (
            max_structural_risk * 0.70
            + float(features.get("range_risk") or 0.0) * 0.15
            + float(features.get("fake_breakout_risk") or 0.0) * 0.10
            + float(features.get("trap_risk") or 0.0) * 0.10
        )
        if bool(features.get("mtf_conflict")):
            risk_score += 18.0
        if bool(features.get("ma_cross_whipsaw")):
            risk_score += 8.0
        if float(features.get("volume_ratio") or 0.0) < 0.75:
            risk_score += 12.0
        if abs(float(features.get("cvd_proxy") or 0.0)) < 0.08:
            risk_score += 4.0
        return self._clamp_score(risk_score)

    def _professional_execution_score(
        self,
        cfg: Dict[str, Any],
        features: Dict[str, Any],
    ) -> float:
        expiry_seconds = max(float(cfg.get("expiry_minutes") or 5) * 60.0, 1.0)
        fee_bps = float(cfg.get("fee_rate") or 0.0) * 10_000.0
        delay_ratio = float(cfg.get("delay_seconds") or 0.0) / expiry_seconds
        score = (
            100.0
            - float(cfg.get("slippage_bps") or 0.0) * 1.2
            - fee_bps * 0.8
            - min(delay_ratio, 1.0) * 25.0
        )
        if cfg.get("enable_l2_features") and not features.get("l2_available"):
            score -= 10.0
        if cfg.get("enable_coinglass_features") and not features.get("coinglass_available_metrics"):
            score -= 10.0
        return self._clamp_score(score)

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _grade_from_score(score: float) -> str:
        if score >= 85:
            return "A"
        if score >= 75:
            return "B"
        if score >= 65:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    def _ensure_main_logic_vote(
        self,
        features: Dict[str, Any],
        cfg: Dict[str, Any],
        decisions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        panel_size = int(cfg.get("reviewer_panel_size") or DEFAULT_REVIEWER_PANEL_SIZE)
        if any(item.get("ai_name") == MAIN_LOGIC_REVIEWER_NAME for item in decisions):
            return decisions[:panel_size]
        main_decision = self._build_main_logic_decision(features, cfg, decisions)
        return [main_decision, *decisions[: max(panel_size - 1, 0)]]

    def _build_main_logic_decision(
        self,
        features: Dict[str, Any],
        cfg: Dict[str, Any],
        decisions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        long_votes = sum(1 for item in decisions if item.get("direction") == "long")
        short_votes = sum(1 for item in decisions if item.get("direction") == "short")
        top_votes = max(long_votes, short_votes)
        if long_votes > short_votes:
            direction = "long"
        elif short_votes > long_votes:
            direction = "short"
        else:
            direction = "hold"

        risk_flags: List[str] = []
        if features["fake_breakout_risk"] > 60:
            risk_flags.append("fake_breakout_high")
        if features["trap_risk"] > 60:
            risk_flags.append("trap_high")
        if features["range_risk"] > 70:
            risk_flags.append("range_middle")
        if risk_flags:
            direction = "hold"

        avg_confidence = (
            sum(float(item.get("confidence") or 0) for item in decisions) / len(decisions)
            if decisions
            else 0.0
        )
        required_votes = max(int(cfg.get("consensus_threshold") or 1), 1)
        vote_score = min(100.0, top_votes / required_votes * 100)
        confidence = max(0.0, min(100.0, avg_confidence * 0.55 + vote_score * 0.45))
        return {
            "ai_name": MAIN_LOGIC_REVIEWER_NAME,
            "source": "main_logic",
            "direction": direction,
            "confidence": round(confidence, 2),
            "reason": (
                f"Main logic vote from rule ensemble: long={long_votes}, "
                f"short={short_votes}, risk={max(features['fake_breakout_risk'], features['trap_risk'], features['range_risk']):.1f}"
            ),
            "risk_flags": risk_flags,
            "evidence": [
                f"trend_score={features['trend_score']:.4f}",
                f"volume_ratio={features['volume_ratio']:.2f}",
                f"range_risk={features['range_risk']:.1f}",
            ],
            "timeframes": ["1m", "3m", "5m", "15m"],
            "invalid_conditions": risk_flags if direction == "hold" else [],
        }

    def _main_logic_decision_from_rule_analysis(
        self,
        rule_analysis: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        for item in rule_analysis.get("ai_decisions") or []:
            if item.get("ai_name") == MAIN_LOGIC_REVIEWER_NAME:
                return dict(item)
        factors = {
            "trend_score": 0.0,
            "volume_ratio": 0.0,
            "range_risk": rule_analysis.get("range_risk", 0.0),
            "fake_breakout_risk": rule_analysis.get("fake_breakout_risk", 0.0),
            "trap_risk": rule_analysis.get("trap_risk", 0.0),
        }
        return {
            "ai_name": MAIN_LOGIC_REVIEWER_NAME,
            "source": "main_logic",
            "direction": rule_analysis.get("final_direction") if rule_analysis.get("allow_trade") else "hold",
            "confidence": float(rule_analysis.get("confidence") or 0),
            "reason": rule_analysis.get("reason_summary") or "Main logic rule prefilter",
            "risk_flags": list(rule_analysis.get("blocked_reasons") or []),
            "evidence": [
                f"signal_strength={float(rule_analysis.get('signal_strength') or 0):.2f}",
                f"range_risk={factors['range_risk']:.1f}",
            ],
            "timeframes": ["1m", "3m", "5m", "15m"],
            "invalid_conditions": list(rule_analysis.get("blocked_reasons") or []),
        }

    def _factor_gate_block_reason(
        self,
        history: List[Dict[str, Any]],
        features: Dict[str, Any],
        cfg: Dict[str, Any],
        direction: str = "long",
    ) -> Optional[str]:
        """Factor-combination entry gate (opt-in via enable_factor_gate),
        mirrored by consensus direction.

        Long consensus: BOTH "5m momentum" (ret5) and "VWAP deviation" must sit
        at/above their trailing upper quantile (p60 default) — the original,
        historically validated rule (2026-07-05 run-2027 forensics: the only
        filter whose train/test win rates agreed, 56.0%/56.2% vs 50.4% base).
        Short consensus: the mirror — both must sit at/below the LOWER quantile
        (p40 for the p60 default). 2026-07-09 forensics: the unmirrored gate
        demanded upper-quantile values from every signal, which a
        short-consensus bar (both features negative) can never satisfy —
        500/500 gated trades were long and every surviving short died here.
        Thresholds are recomputed from bars available at decision time only, so
        the gate stays leakage-free and regime-adaptive.
        """
        if not cfg.get("enable_factor_gate"):
            return None
        quantile = float(cfg.get("factor_gate_quantile") or 0.6)
        lookback = int(cfg.get("factor_gate_lookback") or 60)
        min_history = int(cfg.get("factor_gate_min_history") or 40)
        closes = [k["close"] for k in history]
        if len(closes) < max(min_history, 6):
            return "因子门控：历史样本不足，禁止入场"

        n = min(lookback, len(closes))
        start = len(closes) - n
        ret5_series: List[float] = []
        vwap_dev_series: List[float] = []
        for i in range(start, len(closes)):
            if i >= 5 and closes[i - 5]:
                ret5_series.append((closes[i] - closes[i - 5]) / closes[i - 5] * 100)
            close_i = closes[i]
            if close_i:
                vwap_i = self._vwap(history[max(0, i - 59) : i + 1])
                vwap_dev_series.append((close_i - vwap_i) / close_i * 100)
        if len(ret5_series) < min_history or len(vwap_dev_series) < min_history:
            return "因子门控：历史样本不足，禁止入场"

        effective_quantile = quantile if direction != "short" else 1.0 - quantile

        def trailing_quantile(values: List[float]) -> float:
            ordered = sorted(values)
            idx = min(len(ordered) - 1, max(0, int(effective_quantile * len(ordered))))
            return ordered[idx]

        ret5_threshold = trailing_quantile(ret5_series)
        vwap_dev_threshold = trailing_quantile(vwap_dev_series)
        close = features.get("close") or 0.0
        vwap_dev_now = (close - (features.get("vwap") or 0.0)) / close * 100 if close else 0.0
        ret5_now = float(features.get("ret5") or 0.0)
        if direction == "short":
            blocked = ret5_now > ret5_threshold or vwap_dev_now > vwap_dev_threshold
            comparator = "低于"
        else:
            blocked = ret5_now < ret5_threshold or vwap_dev_now < vwap_dev_threshold
            comparator = "达到"
        if blocked:
            return (
                f"因子门控（{direction}）：5m动量 {ret5_now:.4f}（阈值 {ret5_threshold:.4f}）与 "
                f"VWAP偏离 {vwap_dev_now:.4f}（阈值 {vwap_dev_threshold:.4f}）"
                f"未同时{comparator} trailing p{int(effective_quantile * 100)}"
            )
        return None

    @staticmethod
    def _range_boundary_verdict(
        features: Dict[str, Any],
        min_trap_risk: Optional[float] = None,
        min_trend_mag: Optional[float] = None,
    ) -> tuple:
        """Tier-2 box strategy verdict: (direction | None, block_reason | None).

        触碰上沿押跌、触碰下沿押涨、区间中部绝对禁止；区间太窄（噪音）或
        60 分钟趋势过强（可能真突破）时整个模式停用。Base thresholds are
        a-priori design values from the strategy doc. The optional tightening
        knobs (declared 2026-07-09 from the run-2043/2044 stratification, to
        be judged on the untouched 5/1-5/29 holdout) demand the price be truly
        pinned at the extreme (trap risk) with real pressure into the boundary
        (trend magnitude)."""
        width = float(features.get("range_width_pct") or 0.0)
        atr = float(features.get("atr_pct") or 0.0)
        ret60 = float(features.get("ret60") or 0.0)
        pos = features.get("range_pos")
        if width < max(3 * atr, 0.15):
            return None, f"区间边界模式：区间宽度 {width:.3f}% 不足（需 ≥ max(3×ATR, 0.15%)），非可交易震荡区间"
        if abs(ret60) > 0.30:
            return None, f"区间边界模式：60 分钟趋势 {ret60:+.3f}% 过强，疑似真突破，模式停用"
        if min_trap_risk is not None:
            trap = float(features.get("trap_risk") or 0.0)
            if trap < min_trap_risk:
                return None, f"区间边界模式：陷阱风险 {trap:.1f} < {min_trap_risk:.1f}，价格未被真正困在极端"
        if min_trend_mag is not None:
            trend = float(features.get("trend_score") or 0.0)
            if abs(trend) < min_trend_mag:
                return None, f"区间边界模式：趋势强度 |{trend:.4f}| < {min_trend_mag:.4f}，缺少顶向边界的压力"
        if pos is None:
            return None, "区间边界模式：区间位置不可用"
        pos = float(pos)
        if pos >= 0.85:
            return "short", None
        if pos <= 0.15:
            return "long", None
        return None, f"区间边界模式：价格处于区间中部（pos {pos:.2f}），属于禁止交易区域"

    @staticmethod
    def _l2_range_filters(
        direction: str,
        features: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> Optional[str]:
        """L2 microstructure filters for signal_mode="range_boundary".

        The boundary fade measured exactly break-even, so exactly TWO filters
        (feature count capped at 2 by design to prevent overfitting) demand
        microstructure confirmation of the fade:
        1. range_require_obi — the REVERSE-side depth skew at the touch:
           long needs l2_obi >= +threshold, short needs l2_obi <= -threshold
           (l2_obi = (bid_depth_5 - ask_depth_5) / (bid_depth_5 + ask_depth_5),
           real orderbook snapshots only, depth-10 fallback).
        2. range_require_large_flow — recent aggressive large-order flow must
           agree with the bet: the bet-side large-notional share over the
           trailing window must reach the threshold.
        FAIL-CLOSED: when a knob is set and its feature is unavailable
        (missing/stale book or flow data) the trade is blocked — this is a
        live-money filter, missing data must never silently pass.
        Returns a Chinese blocked-reason string, or None when the bet passes.
        """
        obi_threshold = cfg.get("range_require_obi")
        if obi_threshold is not None:
            obi = features.get("l2_obi")
            if obi is None:
                return "L2过滤：盘口数据不可用"
            obi = float(obi)
            required = float(obi_threshold) if direction == "long" else -float(obi_threshold)
            if (direction == "long" and obi < required) or (direction == "short" and obi > required):
                return f"L2过滤：盘口深度倾斜 {obi:+.3f} 未达到 {required:+.2f}（方向 {direction}）"
        flow_threshold = cfg.get("range_require_large_flow")
        if flow_threshold is not None:
            buy_share = features.get("large_flow_buy_share")
            if buy_share is None:
                return "L2过滤：盘口数据不可用"
            aligned_share = float(buy_share) if direction == "long" else 1.0 - float(buy_share)
            if aligned_share < float(flow_threshold):
                return (
                    f"L2过滤：大单流向占比 {aligned_share:.2f} < {float(flow_threshold):.2f}，"
                    f"资金方向不支持（方向 {direction}）"
                )
        return None

    @staticmethod
    def _trend_follow_block_reason(direction: str, features: Dict[str, Any]) -> Optional[str]:
        """Trend-follow mode gates (signal_mode="trend_follow"), pure function.

        Customer mandate: 只顺大趋势开单，坚决不逆势；优先识别行情底部顺势做多、
        高位顺势做空. Two checks, applied after all existing quality gates:
        1. Higher-timeframe alignment: the bet must agree with the 60-minute
           return (long needs ret60 > +0.10%, short needs ret60 < -0.10%).
           ret60 is 0.0 when history is shorter than 61 bars, which blocks
           both sides - no trend evidence, no trade.
        2. Anti-chase: RSI overextension in the bet direction means the move
           is already stretched; wait for a pullback instead of chasing.
        Returns a Chinese blocked-reason string, or None when the trade passes.
        """
        production_mtf = features.get("production_mtf")
        if isinstance(production_mtf, dict):
            if bool(production_mtf.get("conflict", True)):
                return "顺势模式：4H/30M/15M/10M/5M 多周期未完成或方向冲突，拒绝开单"
            aligned_direction = production_mtf.get("aligned_direction")
            if aligned_direction != direction:
                return (
                    f"顺势模式：多周期方向 {aligned_direction or 'hold'} 与 {direction} 不一致，拒绝逆势单"
                )

        ret60 = float(features.get("ret60") or 0.0)
        if direction == "long" and ret60 <= 0.10:
            return (
                f"顺势模式：方向与 60 分钟大趋势不一致"
                f"（ret60 {ret60:.4f}% ≤ +0.10%），拒绝逆势单"
            )
        if direction == "short" and ret60 >= -0.10:
            return (
                f"顺势模式：方向与 60 分钟大趋势不一致"
                f"（ret60 {ret60:.4f}% ≥ -0.10%），拒绝逆势单"
            )
        rsi = float(features.get("rsi") or 50.0)
        if direction == "long" and rsi > 70:
            return f"顺势模式：RSI {rsi:.1f} > 70 高位超买，拒绝追多，等待回调后再顺势做多"
        if direction == "short" and rsi < 30:
            return f"顺势模式：RSI {rsi:.1f} < 30 低位超卖，拒绝追空，等待反弹后再顺势做空"
        return None

    def _compute_features(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        closes = [k["close"] for k in history]
        highs = [k["high"] for k in history]
        lows = [k["low"] for k in history]
        volumes = [k["volume"] for k in history]
        last = history[-1]
        close = closes[-1]
        prev_close = closes[-2] if len(closes) > 1 else close
        candle_range = max(last["high"] - last["low"], close * 0.000001)
        body = abs(last["close"] - last["open"])
        body_ratio = body / candle_range
        upper_wick_ratio = (last["high"] - max(last["open"], last["close"])) / candle_range
        lower_wick_ratio = (min(last["open"], last["close"]) - last["low"]) / candle_range
        ret1 = self._return_pct(closes, 1)
        ret3 = self._return_pct(closes, 3)
        ret5 = self._return_pct(closes, 5)
        ret15 = self._return_pct(closes, 15)
        # 60-minute higher-timeframe trend (warmup_bars=80 keeps it available;
        # _return_pct guards shorter history by returning 0.0).
        ret60 = self._return_pct(closes, 60)
        ema_fast = self._ema(closes[-30:], 5)
        ema_slow = self._ema(closes[-60:], 20)
        ema_diff_pct = (ema_fast - ema_slow) / close * 100 if close else 0
        rsi = self._rsi(closes[-40:], 14)
        vol_avg = self._mean(volumes[-30:-1]) or 1
        volume_ratio = volumes[-1] / vol_avg if vol_avg else 1
        atr_pct = self._atr_pct(history[-30:])
        ma_cross = self._ma_cross_state(closes, atr_pct)
        macd = self._macd_state(closes)
        boll = self._bollinger_state(closes)
        rsi_divergence = self._rsi_divergence(closes)
        obv = self._obv_state(closes, volumes)
        double_pattern = self._double_extreme_state(highs, lows, closes, atr_pct)
        support = min(lows[-31:-1]) if len(lows) > 31 else min(lows[:-1] or lows)
        resistance = max(highs[-31:-1]) if len(highs) > 31 else max(highs[:-1] or highs)
        range_width_pct = (resistance - support) / close * 100 if close else 0
        range_pos = (close - support) / max(resistance - support, close * 0.000001)
        range_pos = max(0, min(1, range_pos))
        vwap = self._vwap(history[-60:])
        cvd_proxy_raw = self._signed_volume_delta(history[-30:])
        # Flow evidence source priority: CoinGlass (paid, includes liquidation)
        # > local market-flow collector (real taker/OI/funding, 15s resolution)
        # > nothing. Field names are interchangeable by design.
        flow = last.get("coinglass") or last.get("flow") or {}
        cvd_value = flow.get("cvd_delta_norm")
        # Keep cvd_proxy at the OHLCV 1m-resolution measure so the 30 rule-based AI
        # votes don't lose fidelity when CG is on (CG is 30m forward-filled, would
        # otherwise pin the same value across 30 consecutive bars and degrade votes).
        # The CG CVD signal still contributes via coinglass_reversal_score below.
        cvd_proxy = cvd_proxy_raw
        cvd_source = "OHLCV proxy"
        if flow.get("source") == "local_market_flow" and cvd_value is not None:
            # Local taker aggregates are 15s resolution - strictly higher
            # fidelity than the OHLCV proxy, so real CVD takes over here
            # (unlike 30m forward-filled CoinGlass, which would pin values).
            cvd_proxy = float(cvd_value)
            cvd_source = "Local flow"
        taker_delta = flow.get("taker_delta_norm")
        taker_buy_sell_ratio = flow.get("taker_buy_sell_ratio")
        oi_change_pct = flow.get("oi_change_pct")
        funding_rate = flow.get("funding_rate")
        liquidation_imbalance = flow.get("liquidation_imbalance")
        l2 = last.get("l2") or {}
        l2_available = bool(l2)
        l2_source = "Binance L2" if l2_available and l2.get("exchange") == "binance" else "Local L2" if l2_available else "OHLCV proxy"
        orderbook_imbalance = l2.get("imbalance_10")
        if orderbook_imbalance is None:
            signed_body = body_ratio if last["close"] >= last["open"] else -body_ratio
            orderbook_imbalance = signed_body * min(volume_ratio, 2.0) / 2
        depth_ratio = l2.get("depth_ratio_10")
        if depth_ratio is None:
            depth_ratio = max(0.1, 1 + orderbook_imbalance)
        spread_bps = l2.get("spread_bps")
        if spread_bps is None:
            spread_bps = max(0.0, atr_pct * 10)
        # Depth-5 order-book imbalance from a REAL L2 snapshot only (depth-10
        # fallback when the 5-level fields are empty). Stays None when no book
        # is attached: the range_boundary L2 filter is fail-closed and must
        # never read the OHLCV-proxy orderbook_imbalance above.
        l2_obi = None
        if l2_available:
            bid5 = float(l2.get("bid_depth_5") or 0.0)
            ask5 = float(l2.get("ask_depth_5") or 0.0)
            if bid5 + ask5 > 0:
                l2_obi = (bid5 - ask5) / (bid5 + ask5)
            elif l2.get("imbalance_10") is not None:
                l2_obi = float(l2["imbalance_10"])
        # Large-order flow alignment share comes from the LOCAL flow bundle
        # specifically (CoinGlass has no large-order feed and takes priority in
        # the shared `flow` dict above). None when unavailable -> fail-closed.
        large_flow_buy_share = (last.get("flow") or {}).get("large_flow_buy_share")
        trend_score = ret3 * 0.35 + ret5 * 0.35 + ema_diff_pct * 0.3
        mtf_dirs = {
            "1m": self._dir_from_value(ret1, 0.015),
            "3m": self._dir_from_value(ret3, 0.025),
            "5m": self._dir_from_value(ret5, 0.035),
            "15m": self._dir_from_value(ret15, 0.06),
        }
        non_hold_dirs = {value for value in mtf_dirs.values() if value != "hold"}
        mtf_conflict = len(non_hold_dirs) > 1

        breakout_up = close > resistance and prev_close <= resistance
        breakout_down = close < support and prev_close >= support
        upside_fakeout = last["high"] > resistance and close < resistance
        downside_fakeout = last["low"] < support and close > support
        volume_weak_breakout = (breakout_up or breakout_down) and volume_ratio < 1.15
        fake_breakout_risk = 0.0
        fake_breakout_risk += 35 if upside_fakeout or downside_fakeout else 0
        fake_breakout_risk += 25 if volume_weak_breakout else 0
        fake_breakout_risk += 20 if upper_wick_ratio > 0.45 or lower_wick_ratio > 0.45 else 0
        fake_breakout_risk += 20 if mtf_conflict else 0
        fake_breakout_risk = min(100, fake_breakout_risk)

        bull_trap_risk = min(
            100,
            (30 if upper_wick_ratio > 0.38 else 0)
            + (25 if range_pos > 0.82 else 0)
            + (20 if rsi > 68 else 0)
            + (15 if ret5 > 0.08 and close < last["high"] else 0)
            + (10 if volume_ratio > 1.6 and ret1 <= 0 else 0),
        )
        bear_trap_risk = min(
            100,
            (30 if lower_wick_ratio > 0.38 else 0)
            + (25 if range_pos < 0.18 else 0)
            + (20 if rsi < 32 else 0)
            + (15 if ret5 < -0.08 and close > last["low"] else 0)
            + (10 if volume_ratio > 1.6 and ret1 >= 0 else 0),
        )
        range_middle = 1 - min(1, abs(range_pos - 0.5) * 2)
        range_risk = min(100, range_middle * 70 + (20 if range_width_pct < max(atr_pct * 2.2, 0.08) else 0) + (10 if body_ratio < 0.25 else 0))
        trap_risk = max(fake_breakout_risk * 0.8, bull_trap_risk, bear_trap_risk)

        # CoinGlass-derived reversal evidence. Positive = supports LONG exhaustion (fade up).
        # Negative = supports SHORT exhaustion (fade down). 0 when CoinGlass is disabled.
        # Each component is a directional vote in [-30, +30]; we cap the sum at +/-60.
        cg_components: List[float] = []
        cg_available = bool(flow.get("available_metrics"))
        if cg_available:
            # 1. Funding extremes mean one side is paying the other heavily -> crowded -> fade.
            #    +0.02%/8h (mainstream "high") = strong long crowding -> fade up (positive)
            #    -0.005%/8h = strong short crowding -> fade down (negative)
            if funding_rate is not None:
                fr_bp = funding_rate * 10_000  # convert to basis points per 8h
                if fr_bp > 1.5:
                    cg_components.append(min(30, fr_bp * 10))
                elif fr_bp < -0.5:
                    cg_components.append(max(-30, fr_bp * 30))

            # 2. OI change + same-direction price = positions piling in -> reversal risk.
            #    OI +1% with price up = late longs -> fade up.
            if oi_change_pct is not None:
                if oi_change_pct > 0.8 and trend_score > 0:
                    cg_components.append(min(25, oi_change_pct * 15))
                elif oi_change_pct > 0.8 and trend_score < 0:
                    cg_components.append(-min(25, oi_change_pct * 15))

            # 3. Liquidation cascade *opposite* to current move = capitulation -> fade
            #    More longs liquidated (imbalance < 0) during downtrend = capitulation low -> short exhaustion (fade down)
            #    More shorts liquidated (imbalance > 0) during uptrend = squeeze high -> long exhaustion (fade up)
            if liquidation_imbalance is not None:
                if liquidation_imbalance > 0.3 and trend_score > 0:
                    cg_components.append(min(30, liquidation_imbalance * 60))
                elif liquidation_imbalance < -0.3 and trend_score < 0:
                    cg_components.append(max(-30, liquidation_imbalance * 60))

            # 4. CVD vs price divergence. Price up + CVD weakening = buy power waning.
            if cvd_value is not None:
                # CVD < 0.15 means buy/sell roughly balanced; price up with weak CVD = divergence.
                if trend_score > 0.05 and cvd_value < 0.10:
                    cg_components.append(15)
                elif trend_score < -0.05 and cvd_value > -0.10:
                    cg_components.append(-15)

            # 5. Taker ratio extremes (75% one side).
            if taker_buy_sell_ratio is not None:
                if taker_buy_sell_ratio > 2.5 and trend_score > 0:
                    cg_components.append(15)
                elif taker_buy_sell_ratio < 0.4 and trend_score < 0:
                    cg_components.append(-15)

        coinglass_reversal_score = max(-60.0, min(60.0, sum(cg_components))) if cg_components else 0.0

        # Indicator-based reversal evidence from real OHLCV+volume, same sign
        # convention as coinglass_reversal_score: positive supports LONG
        # exhaustion (fade a top), negative supports SHORT exhaustion (fade a
        # bottom). RSI divergence, an OBV/MA cross, and W/M patterns are the
        # classic early-reversal reads; each votes independently, capped +/-60.
        ind_components: List[float] = []
        if rsi_divergence == "bearish":
            ind_components.append(20.0)
        elif rsi_divergence == "bullish":
            ind_components.append(-20.0)
        if obv["cross"] == "down":
            ind_components.append(15.0)
        elif obv["cross"] == "up":
            ind_components.append(-15.0)
        if double_pattern["pattern"] == "double_top":
            ind_components.append(25.0 if double_pattern["confirmed"] else 10.0)
        elif double_pattern["pattern"] == "double_bottom":
            ind_components.append(-25.0 if double_pattern["confirmed"] else -10.0)
        indicator_reversal_score = (
            max(-60.0, min(60.0, sum(ind_components))) if ind_components else 0.0
        )
        # Exhaustion detection: strong consensus plus overextension can mark an extreme likely to reverse.
        # trap_risk > 28: price getting "trapped" at extremes. signal_strength >= 89 gate applied later.
        # range_pos extremes are implicit via max_trade_range_risk=45 edge quality gate.
        # OHLCV-only exhaustion (works without CoinGlass; this is the 75% baseline).
        ohlcv_exhaustion_long = (
            trend_score > 0.10         # STRONG 3-5m momentum up (the spike, not noise)
            and volume_ratio > 1.1     # volume confirming the push
            and rsi > 63               # overbought
            and ret15 < 0.25           # 15m context not strongly up (spike not sustained trend)
            and trap_risk > 28         # momentum getting "trapped" at extreme
        )
        ohlcv_exhaustion_short = (
            trend_score < -0.10        # STRONG 3-5m momentum down (the spike, not noise)
            and volume_ratio > 1.1     # volume confirming the drop
            and rsi < 37               # oversold
            and ret15 > -0.25          # 15m context not strongly down (spike not sustained trend)
            and trap_risk > 28         # momentum getting "trapped" at extreme
        )

        # CoinGlass is PURELY ADDITIVE - it can let extra signals through but never
        # cancels OHLCV ones. This keeps the 75% OHLCV baseline intact.
        #
        # Boost: when CG reversal_score >= +/-25 confirms the same direction as the
        # OHLCV exhaustion shape, we relax trap_risk (28 -> 18). This admits marginal
        # OHLCV setups that CG independently corroborates with funding/liq/CVD evidence.
        #
        # No veto: the 30-day test showed cg_veto erased many winning shorts during a
        # net-down market (lots of short-side liquidation makes cg_score skew long).
        # Direction is decided by OHLCV; CG only widens the gate when it agrees.
        cg_boost_long  = cg_available and coinglass_reversal_score >=  25
        cg_boost_short = cg_available and coinglass_reversal_score <= -25

        # Indicator evidence (RSI divergence / OBV cross / W-M pattern) widens
        # the gate under the same additive rule: corroborate, never cancel.
        evidence_boost_long = cg_boost_long or indicator_reversal_score >= 25
        evidence_boost_short = cg_boost_short or indicator_reversal_score <= -25

        evidence_boosted_long = (
            evidence_boost_long
            and trend_score > 0.10 and volume_ratio > 1.1
            and rsi > 63 and ret15 < 0.25
            and trap_risk > 18
        )
        evidence_boosted_short = (
            evidence_boost_short
            and trend_score < -0.10 and volume_ratio > 1.1
            and rsi < 37 and ret15 > -0.25
            and trap_risk > 18
        )

        exhaustion_long  = ohlcv_exhaustion_long  or evidence_boosted_long
        exhaustion_short = ohlcv_exhaustion_short or evidence_boosted_short

        if fake_breakout_risk > 60:
            market_state = "fake_breakout"
        elif bull_trap_risk > 60:
            market_state = "bull_trap"
        elif bear_trap_risk > 60:
            market_state = "bear_trap"
        elif breakout_up or breakout_down:
            market_state = "breakout"
        elif range_risk > 65:
            market_state = "range"
        elif trend_score > 0.04:
            market_state = "trend_up"
        elif trend_score < -0.04:
            market_state = "trend_down"
        else:
            market_state = "pullback"

        return {
            "close": close,
            "ret1": ret1,
            "ret3": ret3,
            "ret5": ret5,
            "ret15": ret15,
            "ret60": ret60,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_diff_pct": ema_diff_pct,
            "rsi": rsi,
            "volume_ratio": volume_ratio,
            "atr_pct": atr_pct,
            "body_ratio": body_ratio,
            "upper_wick_ratio": upper_wick_ratio,
            "lower_wick_ratio": lower_wick_ratio,
            "support": support,
            "resistance": resistance,
            "range_width_pct": range_width_pct,
            "range_pos": range_pos,
            "vwap": vwap,
            "cvd_proxy": cvd_proxy,
            "cvd_source": cvd_source,
            "taker_delta": taker_delta if taker_delta is not None else cvd_proxy,
            "taker_buy_sell_ratio": taker_buy_sell_ratio if taker_buy_sell_ratio is not None else 1.0,
            "oi_change_pct": oi_change_pct if oi_change_pct is not None else 0.0,
            "funding_rate": funding_rate if funding_rate is not None else 0.0,
            "liquidation_imbalance": liquidation_imbalance if liquidation_imbalance is not None else 0.0,
            "coinglass_available_metrics": flow.get("available_metrics", []),
            "coinglass_lag_seconds": flow.get("lag_seconds"),
            "flow_source": flow.get("source"),
            "l2_available": l2_available,
            "l2_source": l2_source,
            "l2_lag_seconds": l2.get("lag_seconds"),
            "orderbook_imbalance": orderbook_imbalance,
            "depth_ratio": depth_ratio,
            "spread_bps": spread_bps,
            "bid_depth_10": l2.get("bid_depth_10"),
            "ask_depth_10": l2.get("ask_depth_10"),
            "l2_obi": l2_obi,
            "large_flow_buy_share": large_flow_buy_share,
            "trend_score": trend_score,
            "ma_cross_direction": ma_cross["direction"],
            "ma_cross_bars_since": ma_cross["bars_since"],
            "ma_cross_confirmations": ma_cross["confirmations"],
            "ma_cross_confirmed": ma_cross["confirmed"],
            "ma_cross_whipsaw": ma_cross["whipsaw"],
            "ma_cross_angle_pct_per_bar": ma_cross["angle_pct_per_bar"],
            "ma_cross_score": ma_cross["score"],
            "macd_line": macd["line"],
            "macd_signal_line": macd["signal"],
            "macd_hist": macd["hist"],
            "macd_cross": macd["cross"],
            "bb_percent_b": boll["percent_b"],
            "bb_bandwidth_pct": boll["bandwidth_pct"],
            "bb_band_walk": boll["band_walk"],
            "rsi_divergence": rsi_divergence,
            "obv_above_ma": obv["above_ma"],
            "obv_cross": obv["cross"],
            "double_pattern": double_pattern["pattern"],
            "double_pattern_confirmed": double_pattern["confirmed"],
            "double_pattern_neckline": double_pattern["neckline"],
            "indicator_reversal_score": indicator_reversal_score,
            "exhaustion_long": exhaustion_long,
            "exhaustion_short": exhaustion_short,
            "coinglass_reversal_score": coinglass_reversal_score,
            "ohlcv_exhaustion_long": ohlcv_exhaustion_long,
            "ohlcv_exhaustion_short": ohlcv_exhaustion_short,
            "mtf_dirs": mtf_dirs,
            "mtf_conflict": mtf_conflict,
            "breakout_up": breakout_up,
            "breakout_down": breakout_down,
            "upside_fakeout": upside_fakeout,
            "downside_fakeout": downside_fakeout,
            "fake_breakout_risk": fake_breakout_risk,
            "bull_trap_risk": bull_trap_risk,
            "bear_trap_risk": bear_trap_risk,
            "trap_risk": trap_risk,
            "range_risk": range_risk,
            "market_state": market_state,
        }
