"""Prediction and historical settlement loop for 5-minute event contracts."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from services.event_contract.constants import ENGINE_VERSION, PERIOD_SECONDS
from services.event_contract.tasks import EventBacktestPaused, build_ai_reviewer_statuses

logger = logging.getLogger(__name__)


class EventContractBacktestMixin:
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
        rule_analysis = self._analyze_snapshot(history, cfg, source="system_30_ai")
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
            "reason": analysis["reason_summary"],
            "entry_warning": "; ".join(analysis["blocked_reasons"]),
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
        expected_ai_reviews = cfg["max_ai_evaluations"] * 30 if cfg["consensus_mode"] == "ai_confirmed" else 0
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
            entry_idx = idx
            entry_delay_lag = 0
            if cfg["delay_seconds"] > 0:
                target_entry_ts = self._decision_timestamp(candle, cfg) + cfg["delay_seconds"]
                target_entry_open_ts = target_entry_ts - interval
                entry_idx = self._first_index_at_or_after(klines, target_entry_open_ts)
                if entry_idx is None or entry_idx >= len(klines):
                    skipped["entry_delay_skipped_count"] += 1
                    continue
                entry_delay_lag = int(self._decision_timestamp(klines[entry_idx], cfg) - target_entry_ts)
                if entry_delay_lag > cfg["max_entry_lag_seconds"]:
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
            analysis = self._analyze_snapshot(history, cfg, source="system_30_ai")
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
                        "ai_reviewer_statuses": build_ai_reviewer_statuses(status="running"),
                        "message": f"Running 30 AI reviewers for candidate {ai_evaluations + 1}",
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
                        "ai_reviewer_statuses": build_ai_reviewer_statuses(ai_decisions),
                        "message": f"Completed 30 AI reviewers for candidate {ai_evaluations}",
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

            raw_entry_price = klines[entry_idx]["close"]
            raw_expiry_price = klines[expiry_idx]["close"]
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
                "entry_time": self._to_iso(self._decision_timestamp(klines[entry_idx], cfg)),
                "entry_price": round(entry_price, 6),
                "expiry_time": self._to_iso(self._decision_timestamp(klines[expiry_idx], cfg)),
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

        summary = self._build_summary(cfg, trades, equity, max_drawdown, skipped, data_quality)
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
        # New trades just landed - drop the learning cache so the next predict/backtest
        # call refits reviewer posteriors against the freshest outcomes.
        try:
            from services.event_contract.reviewer_learning import clear_reviewer_cache
            clear_reviewer_cache()
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

    def _build_summary(
        self,
        cfg: Dict[str, Any],
        trades: List[Dict[str, Any]],
        final_equity: float,
        max_drawdown: float,
        skipped: Dict[str, int],
        data_quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        total = len(trades)
        wins = sum(1 for t in trades if t["result"] == "win")
        losses = sum(1 for t in trades if t["result"] == "loss")
        draws = sum(1 for t in trades if t["result"] == "draw")
        gross_profit = sum(t["profit_loss"] for t in trades if t["profit_loss"] > 0)
        gross_loss = abs(sum(t["profit_loss"] for t in trades if t["profit_loss"] < 0))
        long_trades = [t for t in trades if t["direction"] == "long"]
        short_trades = [t for t in trades if t["direction"] == "short"]

        def rate(items: List[Dict[str, Any]]) -> float:
            return round(sum(1 for item in items if item["result"] == "win") / len(items) * 100, 2) if items else 0
        fee = cfg["stake_amount"] * cfg["fee_rate"]
        break_even_win_rate = (
            (cfg["stake_amount"] + fee) / (cfg["stake_amount"] * (cfg["win_payout_ratio"] + 1)) * 100
            if cfg["win_payout_ratio"] > -1
            else 100
        )
        target_win_rate = cfg.get("target_win_rate", 75)
        nested_quality_warnings = any(
            bool((data_quality.get(key) or {}).get("warnings"))
            for key in ("coinglass", "l2")
        )
        partial = (
            skipped.get("ai_skipped_cap_count", 0) > 0
            or skipped.get("missing_expiry_count", 0) > 0
            or skipped.get("expiry_lag_skipped_count", 0) > 0
            or skipped.get("entry_delay_skipped_count", 0) > 0
            or bool(data_quality.get("warnings"))
            or nested_quality_warnings
        )
        win_rate = round(wins / total * 100, 2) if total else 0
        target_min_trades = int(cfg.get("target_min_trades", 10))
        target_sample_met = total >= target_min_trades
        target_win_rate_met = not partial and target_sample_met and win_rate >= target_win_rate

        streak_w = streak_l = max_w = max_l = 0
        for trade in trades:
            if trade["result"] == "win":
                streak_w += 1
                streak_l = 0
            elif trade["result"] == "loss":
                streak_l += 1
                streak_w = 0
            max_w = max(max_w, streak_w)
            max_l = max(max_l, streak_l)

        return {
            "engine_version": ENGINE_VERSION,
            "config_hash": self._config_hash(cfg),
            "data_quality": data_quality,
            "consensus_mode": cfg["consensus_mode"],
            "consensus_source": "llm_ai" if cfg["consensus_mode"] == "ai_confirmed" else "system_30_ai",
            "ai_confirmed": cfg["consensus_mode"] == "ai_confirmed",
            "max_ai_evaluations": cfg["max_ai_evaluations"],
            "target_win_rate": round(target_win_rate, 2),
            "target_min_trades": target_min_trades,
            "target_sample_met": target_sample_met,
            "target_win_rate_met": target_win_rate_met,
            "break_even_win_rate": round(break_even_win_rate, 2),
            "partial": partial,
            "audit_status": "partial" if partial else "complete",
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": win_rate,
            "loss_rate": round(losses / total * 100, 2) if total else 0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (round(gross_profit, 4) if gross_profit else 0),
            "expectancy": round(sum(t["profit_loss"] for t in trades) / total, 4) if total else 0,
            "initial_balance": cfg["initial_balance"],
            "final_equity": round(final_equity, 4),
            "total_pnl": round(final_equity - cfg["initial_balance"], 4),
            "total_pnl_percent": round((final_equity - cfg["initial_balance"]) / cfg["initial_balance"] * 100, 4),
            "max_drawdown": round(max_drawdown, 4),
            "max_consecutive_wins": max_w,
            "max_consecutive_losses": max_l,
            "average_signal_strength": round(self._avg(t["signal_strength"] for t in trades), 2),
            "average_trap_risk": round(self._avg(t["trap_risk"] for t in trades), 2),
            "long_win_rate": rate(long_trades),
            "short_win_rate": rate(short_trades),
            "trend_market_win_rate": rate([t for t in trades if t["market_state"] in ("trend_up", "trend_down")]),
            "range_market_win_rate": rate([t for t in trades if t["market_state"] == "range"]),
            "breakout_win_rate": rate([t for t in trades if t["market_state"] == "breakout"]),
            "pullback_win_rate": rate([t for t in trades if t["market_state"] == "pullback"]),
            **skipped,
        }

    def _find_similar_patterns(
        self,
        klines: List[Dict[str, Any]],
        current: Dict[str, Any],
        cfg: Dict[str, Any],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        if len(klines) < cfg["warmup_bars"] + cfg["expiry_bars"] + 20:
            return []
        target_state = current["market_state"]
        target_direction = current["final_direction"]
        matches = []
        ts_to_index = {item["timestamp"]: idx for idx, item in enumerate(klines)}
        max_scan = min(len(klines) - cfg["expiry_bars"] - 1, 1500)
        start = max(cfg["warmup_bars"], len(klines) - max_scan)
        for idx in range(start, len(klines) - cfg["expiry_bars"] - 1):
            snapshot = self._analyze_snapshot(klines[: idx + 1], cfg)
            if snapshot["market_state"] != target_state:
                continue
            if target_direction != "hold" and snapshot["final_direction"] != target_direction:
                continue
            direction = snapshot["final_direction"]
            if direction not in ("long", "short"):
                continue
            expiry_ts = klines[idx]["timestamp"] + cfg["expiry_minutes"] * 60
            expiry_idx, expiry_lag = self._resolve_expiry_index(klines, ts_to_index, expiry_ts, cfg)
            if expiry_idx is None:
                continue
            expiry = klines[expiry_idx]
            outcome = self._settle_event_contract(direction, klines[idx]["close"], expiry["close"], cfg["draw_result"])
            matches.append(
                {
                    "direction": direction,
                    "market_state": snapshot["market_state"],
                    "signal_strength": snapshot["signal_strength"],
                    "result": outcome,
                    "entry_price": round(klines[idx]["close"], 6),
                    "expiry_price": round(expiry["close"], 6),
                    "entry_time": self._to_iso(self._decision_timestamp(klines[idx], cfg)),
                    "expiry_time": self._to_iso(self._decision_timestamp(expiry, cfg)),
                    "expiry_lag_seconds": expiry_lag or 0,
                }
            )
        recent = matches[-limit:]
        win_rate = round(sum(1 for item in matches if item["result"] == "win") / len(matches) * 100, 2) if matches else 0
        return [{"sample_size": len(matches), "historical_win_rate": win_rate, "matches": recent}]

    def _first_index_at_or_after(self, klines: List[Dict[str, Any]], target_ts: int) -> Optional[int]:
        for idx, item in enumerate(klines):
            if item["timestamp"] >= target_ts:
                return idx
        return None

    def _settle_event_contract(self, direction: str, entry: float, expiry: float, draw_result: str) -> str:
        if expiry == entry:
            return "draw" if draw_result == "draw" else "loss"
        if direction == "long":
            return "win" if expiry > entry else "loss"
        if direction == "short":
            return "win" if expiry < entry else "loss"
        return "loss"

    def _apply_slippage(self, price: float, direction: str, bps: float) -> float:
        if not bps:
            return price
        multiplier = bps / 10000
        return price * (1 + multiplier) if direction == "long" else price * (1 - multiplier)
