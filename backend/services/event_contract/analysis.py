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

        # Exhaustion reversal gate: momentum + overextension + trap detection + high signal quality.
        # signal_strength >= 89 filters out noisy exhaustion signals (88.8-88.9 were empirical loss points).
        exhaustion_reversal = False
        if allow_trade and final_direction in ("long", "short") and not professional_policy:
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
