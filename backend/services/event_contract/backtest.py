"""Prediction and historical settlement loop for 5-minute event contracts."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from services.event_contract.ai_trader_team import (
    build_ai_trader_team_state,
    finalize_ai_trader_team_report,
    record_ai_trader_team_decisions,
)
from services.event_contract.backtest_helpers import EventContractBacktestHelperMixin
from services.event_contract.constants import ENGINE_VERSION, MAX_REVIEWER_PANEL_SIZE, PERIOD_SECONDS, reviewer_names_for_panel
from services.event_contract.localization import join_chinese_reasons
from services.event_contract.tasks import EventBacktestPaused, build_ai_reviewer_statuses

logger = logging.getLogger(__name__)


class EventContractBacktestMixin(EventContractBacktestHelperMixin):
    def _load_reviewer_weights(self, db: Session, cfg: Dict[str, Any]) -> Dict[str, float]:
        """Reviewer weights with temporal isolation.

        pre_window: fit only on trades before the window start (no leakage).
        static: expertise base weights only (fully deterministic).
        unsafe_legacy: old behavior (fits on ALL trade logs) - comparison only.
        """
        mode = str(cfg.get("reviewer_weights_mode") or "pre_window")
        try:
            if mode == "static":
                from services.event_contract.reviewer_expertise import get_base_weight
                from services.event_contract.constants import EVENT_AI_NAMES
                return {name: get_base_weight(name) for name in EVENT_AI_NAMES}
            from services.event_contract.reviewer_learning import compute_reviewer_weights
            if mode == "unsafe_legacy":
                return compute_reviewer_weights(db)
            return compute_reviewer_weights(db, before_ts=cfg["start_time"])
        except Exception as exc:  # noqa: BLE001 - weights are optional
            logger.warning("reviewer_learning weight load failed (%s) - using neutral weights", exc)
            return {}

    def predict(self, db: Session, config: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self._normalize_config(config, prediction=True)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        lookback_start = now_ts - 3 * 24 * 3600
        klines = self._load_klines(
            db,
            cfg["exchange"],
            cfg["symbol"],
            cfg["period"],
            lookback_start,
            now_ts,
            cfg["environment"],
            min_bars=cfg["warmup_bars"] + 5,
        )
        original_count = len(klines)
        klines = self._closed_klines(klines, cfg["period"], now_ts)
        if len(klines) < cfg["warmup_bars"]:
            raise ValueError(
                f"Not enough {cfg['period']} K-line data for {cfg['exchange']} {cfg['symbol']}. "
                f"Need at least {cfg['warmup_bars']} bars, got {len(klines)}."
            )

        data_quality = self._audit_kline_series(
            klines,
            cfg,
            self._decision_timestamp(klines[-cfg["warmup_bars"]], cfg),
            self._decision_timestamp(klines[-1], cfg),
        )
        data_quality["unclosed_bars_dropped"] = original_count - len(klines)
        self._validate_data_quality(data_quality, cfg)
        coinglass_bundle = self._load_coinglass_feature_bundle(
            cfg,
            klines[0]["timestamp"],
            klines[-1]["timestamp"],
            klines[-cfg["warmup_bars"]]["timestamp"],
            klines[-1]["timestamp"],
        )
        if coinglass_bundle.get("enabled"):
            data_quality["coinglass"] = coinglass_bundle["audit"]
            klines = self._attach_coinglass_features(klines, coinglass_bundle, cfg)
        l2_bundle = self._load_l2_feature_bundle(
            db,
            cfg,
            klines[0]["timestamp"],
            self._decision_timestamp(klines[-1], cfg),
        )
        if l2_bundle.get("enabled"):
            klines = self._attach_l2_features(klines, l2_bundle, cfg)
            latest_decision_ts = self._decision_timestamp(klines[-1], cfg)
            data_quality["l2"] = self._audit_l2_features(
                klines,
                l2_bundle,
                cfg,
                latest_decision_ts,
                latest_decision_ts,
            )
        history = klines[-cfg["warmup_bars"] :]
        # Load learned reviewer weights once per predict call - _analyze_snapshot
        # reads them out of cfg to apply weighted consensus without new plumbing.
        cfg = {**cfg, "reviewer_weights": self._load_reviewer_weights(db, cfg)}
        rule_analysis = self._analyze_snapshot(history, cfg, source="system_panel")
        analysis = rule_analysis
        if cfg["consensus_mode"] == "ai_confirmed":
            ai_decisions, ai_meta = self._call_llm_consensus(db, cfg, history, rule_analysis)
            analysis = self._analyze_snapshot(
                history,
                cfg,
                decisions_override=ai_decisions,
                source="llm_ai",
                ai_meta=ai_meta,
            )
        latest = history[-1]
        similar = self._find_similar_patterns(klines, analysis, cfg)

        return {
            "symbol": cfg["symbol"],
            "engine_version": ENGINE_VERSION,
            "exchange": cfg["exchange"],
            "period": cfg["period"],
            "consensus_mode": cfg["consensus_mode"],
            "decision_policy": analysis["decision_policy"],
            "ai_participated": analysis["ai_participated"],
            "ai_model": analysis.get("ai_model"),
            "ai_account_name": analysis.get("ai_account_name"),
            "current_time": self._to_iso(self._decision_timestamp(latest, cfg)),
            "current_price": latest["close"],
            "expiry_time": self._to_iso(self._expiry_timestamp(latest, cfg)),
            "market_state": analysis["market_state"],
            "long_5m_probability": analysis["long_probability"],
            "short_5m_probability": analysis["short_probability"],
            "hold_probability": analysis["hold_probability"],
            "best_action": analysis["final_direction"],
            "allow_trade": analysis["allow_trade"],
            "confidence": analysis["confidence"],
            "signal_strength": analysis["signal_strength"],
            "signal_type": analysis["signal_type"],
            "event_signal_type": analysis["event_signal_type"],
            "trap_risk": analysis["trap_risk"],
            "fake_breakout_risk": analysis["fake_breakout_risk"],
            "range_risk": analysis["range_risk"],
            "edge_score": analysis["edge_score"],
            "risk_score": analysis["risk_score"],
            "execution_score": analysis["execution_score"],
            "decision_grade": analysis["decision_grade"],
            "trade_readiness": analysis["trade_readiness"],
            "veto_reasons": analysis["veto_reasons"],
            "decision_diagnostics": analysis["decision_diagnostics"],
            "reason": analysis["reason_summary"],
            "entry_warning": join_chinese_reasons(analysis["blocked_reasons"]),
            "similar_patterns": similar,
            "event_signal": analysis["event_signal"],
            "data_quality": data_quality,
            "ai_consensus": analysis["ai_consensus"],
            "ai_decisions": analysis["ai_decisions"],
            "factors": analysis["factors"],
        }

    def run_backtest(
        self,
        db: Session,
        config: Dict[str, Any],
        *,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        pause_checker: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        cfg = self._normalize_config(config, prediction=False)
        start_ts = int(cfg["start_time"].timestamp())
        end_ts = int(cfg["end_time"].timestamp())
        interval = PERIOD_SECONDS[cfg["period"]]
        load_start = start_ts - cfg["warmup_bars"] * interval
        load_end = end_ts + cfg["expiry_minutes"] * 60 + interval

        def report(event: Dict[str, Any]) -> None:
            if progress_callback:
                progress_callback(event)
            if pause_checker and pause_checker():
                raise EventBacktestPaused("Event backtest paused by user")

        report({"phase": "loading_data", "message": "Loading market data"})

        klines = self._load_klines(
            db,
            cfg["exchange"],
            cfg["symbol"],
            cfg["period"],
            load_start,
            load_end,
            cfg["environment"],
            min_bars=cfg["warmup_bars"] + cfg["expiry_bars"] + 1,
        )
        data_quality = self._audit_kline_series(klines, cfg, start_ts, end_ts)
        self._validate_data_quality(data_quality, cfg)
        if len(klines) < cfg["warmup_bars"] + cfg["expiry_bars"] + 1:
            raise ValueError(
                f"Not enough {cfg['period']} K-line data for backtest. "
                f"Need warmup and expiry data, got {len(klines)} bars."
            )
        coinglass_bundle = self._load_coinglass_feature_bundle(
            cfg,
            load_start,
            load_end,
            start_ts,
            end_ts,
        )
        if coinglass_bundle.get("enabled"):
            data_quality["coinglass"] = coinglass_bundle["audit"]
            klines = self._attach_coinglass_features(klines, coinglass_bundle, cfg)
        l2_bundle = self._load_l2_feature_bundle(
            db,
            cfg,
            load_start,
            self._decision_timestamp(klines[-1], cfg),
        )
        if l2_bundle.get("enabled"):
            klines = self._attach_l2_features(klines, l2_bundle, cfg)
            data_quality["l2"] = self._audit_l2_features(klines, l2_bundle, cfg, start_ts, end_ts)

        decision_candles = [k for k in klines if start_ts <= self._decision_timestamp(k, cfg) <= end_ts]
        total_decision_bars = len(decision_candles)
        if total_decision_bars > cfg["max_bars"]:
            raise ValueError(f"Backtest range is too large. Limit is {cfg['max_bars']} decision bars.")
        reviewer_names = reviewer_names_for_panel(cfg["reviewer_panel_size"])
        reviewer_count = len(reviewer_names)
        expected_ai_reviews = cfg["max_ai_evaluations"] * reviewer_count if cfg["consensus_mode"] == "ai_confirmed" else 0
        report(
            {
                "phase": "scanning",
                "data_ready": True,
                "processed_decision_bars": 0,
                "total_decision_bars": total_decision_bars,
                "completed_ai_reviews": 0,
                "expected_ai_reviews": expected_ai_reviews,
                "message": "Scanning decision bars",
            }
        )

        ts_to_index = {item["timestamp"]: idx for idx, item in enumerate(klines)}
        # Learned reviewer weights are computed once per backtest and reused for
        # every _analyze_snapshot call inside the loop (weights don't change mid-run).
        cfg = {**cfg, "reviewer_weights": self._load_reviewer_weights(db, cfg)}
        equity = cfg["initial_balance"]
        peak_equity = equity
        max_drawdown = 0.0
        trades: List[Dict[str, Any]] = []
        equity_curve = [{"timestamp": start_ts * 1000, "equity": round(equity, 4)}]
        skipped = {
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 0,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 0,
            "candidate_signals_count": 0,
        }
        ai_evaluations = 0
        completed_ai_reviews = 0
        ai_trader_team_state = build_ai_trader_team_state(cfg)

        for idx, candle in enumerate(klines):
            decision_ts = self._decision_timestamp(candle, cfg)
            if decision_ts < start_ts or decision_ts > end_ts:
                continue
            if idx < cfg["warmup_bars"]:
                continue

            skipped["decision_bars_count"] += 1
            if skipped["decision_bars_count"] == 1 or skipped["decision_bars_count"] % 25 == 0:
                report(
                    {
                        "phase": "scanning",
                        "data_ready": True,
                        "processed_decision_bars": skipped["decision_bars_count"],
                        "total_decision_bars": total_decision_bars,
                        "completed_ai_reviews": completed_ai_reviews,
                        "expected_ai_reviews": expected_ai_reviews,
                        "message": f"Scanned {skipped['decision_bars_count']}/{total_decision_bars} decision bars",
                    }
                )
            entry_idx, entry_delay_lag = self._resolve_entry_bar(
                klines, decision_ts, cfg["delay_seconds"], interval, cfg["max_entry_lag_seconds"]
            )
            if entry_idx is None:
                skipped["entry_delay_skipped_count"] += 1
                continue

            settlement_entry_ts = klines[entry_idx]["timestamp"]
            expiry_ts = settlement_entry_ts + cfg["expiry_minutes"] * 60
            expiry_idx, expiry_lag = self._resolve_expiry_index(klines, ts_to_index, expiry_ts, cfg)
            if expiry_idx is None:
                if expiry_lag is None:
                    skipped["missing_expiry_count"] += 1
                else:
                    skipped["expiry_lag_skipped_count"] += 1
                continue

            history = klines[: idx + 1]
            team_features = self._compute_features(history)
            team_decisions = self._build_rule_decisions(
                team_features,
                {**cfg, "reviewer_panel_size": MAX_REVIEWER_PANEL_SIZE},
            )
            record_ai_trader_team_decisions(
                state=ai_trader_team_state,
                cfg=cfg,
                decisions=team_decisions,
                signal_time=self._to_iso(self._decision_timestamp(candle, cfg)),
                entry_time=self._to_iso(klines[entry_idx]["timestamp"]),
                expiry_time=self._to_iso(klines[expiry_idx]["timestamp"]),
                entry_price=klines[entry_idx]["open"],
                expiry_price=klines[expiry_idx]["open"],
                market_state=str(team_features.get("market_state") or "unknown"),
            )
            analysis = self._analyze_snapshot(history, cfg, source="system_panel")
            skipped["ai_evaluated_count"] += 1
            if not analysis["allow_trade"]:
                if analysis["fake_breakout_risk"] > 60:
                    skipped["fake_breakout_filtered_count"] += 1
                elif analysis["trap_risk"] > 60:
                    skipped["trap_filtered_count"] += 1
                elif any("edge gate" in reason for reason in analysis["blocked_reasons"]):
                    skipped["edge_quality_filtered_count"] += 1
                else:
                    skipped["no_trade_filtered_count"] += 1
                skipped["rule_prefiltered_count"] += 1
                continue
            skipped["candidate_signals_count"] += 1

            if cfg["consensus_mode"] == "ai_confirmed":
                if ai_evaluations >= cfg["max_ai_evaluations"]:
                    skipped["ai_skipped_cap_count"] += 1
                    continue

                report(
                    {
                        "phase": "ai_review",
                        "data_ready": True,
                        "processed_decision_bars": skipped["decision_bars_count"],
                        "total_decision_bars": total_decision_bars,
                        "completed_ai_reviews": completed_ai_reviews,
                        "expected_ai_reviews": expected_ai_reviews,
                        "ai_reviewer_statuses": build_ai_reviewer_statuses(
                            status="running",
                            reviewer_names=reviewer_names,
                        ),
                        "message": f"Running {reviewer_count} consensus votes for candidate {ai_evaluations + 1}",
                    }
                )
                ai_decisions, ai_meta = self._call_llm_consensus(db, cfg, history, analysis)
                ai_evaluations += 1
                completed_ai_reviews = min(expected_ai_reviews, completed_ai_reviews + len(ai_decisions))
                skipped["llm_evaluated_count"] = ai_evaluations
                report(
                    {
                        "phase": "ai_review",
                        "data_ready": True,
                        "processed_decision_bars": skipped["decision_bars_count"],
                        "total_decision_bars": total_decision_bars,
                        "completed_ai_reviews": completed_ai_reviews,
                        "expected_ai_reviews": expected_ai_reviews,
                        "ai_reviewer_statuses": build_ai_reviewer_statuses(
                            ai_decisions,
                            reviewer_names=reviewer_names,
                        ),
                        "message": f"Completed {len(ai_decisions)}/{reviewer_count} consensus votes for candidate {ai_evaluations}",
                    }
                )
                analysis = self._analyze_snapshot(
                    history,
                    cfg,
                    decisions_override=ai_decisions,
                    source="llm_ai",
                    ai_meta=ai_meta,
                )
                if not analysis["allow_trade"]:
                    skipped["ai_rejected_count"] += 1
                    skipped["no_trade_filtered_count"] += 1
                    continue

            if cfg["consensus_mode"] == "ai_confirmed" and not analysis["ai_participated"]:
                skipped["ai_rejected_count"] += 1
                continue

            direction = analysis["final_direction"]
            if direction not in ("long", "short"):
                skipped["no_trade_filtered_count"] += 1
                continue

            raw_entry_price = klines[entry_idx]["open"]
            raw_expiry_price = klines[expiry_idx]["open"]
            entry_price = self._apply_slippage(raw_entry_price, direction, cfg["slippage_bps"])
            expiry_price = raw_expiry_price
            result = self._settle_event_contract(direction, entry_price, expiry_price, cfg["draw_result"])
            fee = cfg["stake_amount"] * cfg["fee_rate"]
            if result == "win":
                pnl = cfg["stake_amount"] * cfg["win_payout_ratio"] - fee
            elif result == "draw":
                pnl = -fee
            else:
                pnl = -cfg["stake_amount"] - fee

            equity_before = equity
            equity += pnl
            peak_equity = max(peak_equity, equity)
            if peak_equity > 0:
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity * 100)

            trade = {
                "trade_id": f"evt-{len(trades) + 1}",
                "trade_index": len(trades) + 1,
                "symbol": cfg["symbol"],
                "signal_time": self._to_iso(self._decision_timestamp(candle, cfg)),
                "direction": direction,
                "entry_time": self._to_iso(klines[entry_idx]["timestamp"]),
                "entry_price": round(entry_price, 6),
                "expiry_time": self._to_iso(klines[expiry_idx]["timestamp"]),
                "expiry_price": round(expiry_price, 6),
                "entry_delay_lag_seconds": entry_delay_lag,
                "expiry_lag_seconds": expiry_lag or 0,
                "result": result,
                "profit_loss": round(pnl, 6),
                "equity_before": round(equity_before, 4),
                "equity_after": round(equity, 4),
                "signal_strength": analysis["signal_strength"],
                "ai_consensus_rate": analysis["ai_consensus"]["consensus_rate"],
                "consensus_source": analysis["ai_consensus"]["consensus_source"],
                "ai_participated": analysis["ai_participated"],
                "ai_model": analysis.get("ai_model"),
                "ai_account_name": analysis.get("ai_account_name"),
                "signal_type": analysis["event_signal"]["signal_type"],
                "event_signal": analysis["event_signal"],
                "long_votes": analysis["ai_consensus"]["long_votes"],
                "short_votes": analysis["ai_consensus"]["short_votes"],
                "hold_votes": analysis["ai_consensus"]["hold_votes"],
                "market_state": analysis["market_state"],
                "trap_risk": analysis["trap_risk"],
                "fake_breakout_risk": analysis["fake_breakout_risk"],
                "reason": analysis["reason_summary"],
                "factor_snapshot": analysis["factors"],
                "ai_decision_snapshot": analysis["ai_decisions"],
            }
            trades.append(trade)
            equity_curve.append({"timestamp": self._decision_timestamp(klines[expiry_idx], cfg) * 1000, "equity": round(equity, 4)})

        ai_trader_team_report = finalize_ai_trader_team_report(ai_trader_team_state, cfg)
        summary = self._build_summary(
            cfg,
            trades,
            equity,
            max_drawdown,
            skipped,
            data_quality,
            ai_trader_team_report=ai_trader_team_report,
        )
        summary["execution_time_ms"] = int((time.perf_counter() - started) * 1000)
        report(
            {
                "phase": "saving",
                "data_ready": True,
                "processed_decision_bars": skipped["decision_bars_count"],
                "total_decision_bars": total_decision_bars,
                "completed_ai_reviews": completed_ai_reviews,
                "expected_ai_reviews": expected_ai_reviews,
                "message": "Saving backtest result",
            }
        )
        run_id = self._persist_backtest(db, cfg, summary, trades, equity_curve)
        # New trades just landed - drop the "__latest__" learning cache entry so
        # get_reviewer_evolution_snapshot / unsafe_legacy mode refit against the
        # freshest outcomes. before_ts-keyed (pre_window) entries are left alone -
        # refitting them from in-window trades would reintroduce leakage.
        try:
            from services.event_contract.reviewer_learning import invalidate_latest_reviewer_cache
            invalidate_latest_reviewer_cache()
        except Exception as exc:  # noqa: BLE001 - cache reset is best-effort
            logger.warning("reviewer_learning cache reset failed: %s", exc)

        return {
            "run_id": run_id,
            "config": self._public_config(cfg),
            "summary": summary,
            "data_quality": data_quality,
            "equity_curve": equity_curve,
            "trades": trades[: cfg["return_trade_limit"]],
            "trades_returned": min(len(trades), cfg["return_trade_limit"]),
            "total_trade_logs": len(trades),
        }
