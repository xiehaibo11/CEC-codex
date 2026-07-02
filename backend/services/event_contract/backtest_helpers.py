"""Helper methods for event-contract prediction and backtest outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.event_contract.backtest_quality import build_backtest_quality_gate
from services.event_contract.backtest_research import build_backtest_research_report
from services.event_contract.backtest_validation import build_backtest_validation_report
from services.event_contract.constants import ENGINE_VERSION


class EventContractBacktestHelperMixin:
    def _build_summary(
        self,
        cfg: Dict[str, Any],
        trades: List[Dict[str, Any]],
        final_equity: float,
        max_drawdown: float,
        skipped: Dict[str, int],
        data_quality: Dict[str, Any],
        ai_trader_team_report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        total = len(trades)
        wins = sum(1 for trade in trades if trade["result"] == "win")
        losses = sum(1 for trade in trades if trade["result"] == "loss")
        draws = sum(1 for trade in trades if trade["result"] == "draw")
        gross_profit = sum(trade["profit_loss"] for trade in trades if trade["profit_loss"] > 0)
        gross_loss = abs(sum(trade["profit_loss"] for trade in trades if trade["profit_loss"] < 0))
        long_trades = [trade for trade in trades if trade["direction"] == "long"]
        short_trades = [trade for trade in trades if trade["direction"] == "short"]

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

        summary = {
            "engine_version": ENGINE_VERSION,
            "config_hash": self._config_hash(cfg),
            "data_quality": data_quality,
            "consensus_mode": cfg["consensus_mode"],
            "decision_policy": cfg["decision_policy"],
            "consensus_source": "llm_ai" if cfg["consensus_mode"] == "ai_confirmed" else "system_panel",
            "ai_confirmed": cfg["consensus_mode"] == "ai_confirmed",
            "max_ai_evaluations": cfg["max_ai_evaluations"],
            "consensus_threshold": cfg["consensus_threshold"],
            "reviewer_panel_size": cfg["reviewer_panel_size"],
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
            "expectancy": round(sum(trade["profit_loss"] for trade in trades) / total, 4) if total else 0,
            "initial_balance": cfg["initial_balance"],
            "final_equity": round(final_equity, 4),
            "total_pnl": round(final_equity - cfg["initial_balance"], 4),
            "total_pnl_percent": round((final_equity - cfg["initial_balance"]) / cfg["initial_balance"] * 100, 4),
            "max_drawdown": round(max_drawdown, 4),
            "max_consecutive_wins": max_w,
            "max_consecutive_losses": max_l,
            "average_signal_strength": round(self._avg(trade["signal_strength"] for trade in trades), 2),
            "average_trap_risk": round(self._avg(trade["trap_risk"] for trade in trades), 2),
            "long_win_rate": rate(long_trades),
            "short_win_rate": rate(short_trades),
            "trend_market_win_rate": rate([trade for trade in trades if trade["market_state"] in ("trend_up", "trend_down")]),
            "range_market_win_rate": rate([trade for trade in trades if trade["market_state"] == "range"]),
            "breakout_win_rate": rate([trade for trade in trades if trade["market_state"] == "breakout"]),
            "pullback_win_rate": rate([trade for trade in trades if trade["market_state"] == "pullback"]),
            **skipped,
        }
        summary["quality_gate"] = build_backtest_quality_gate(
            cfg=cfg,
            trades=trades,
            skipped=skipped,
            data_quality=data_quality,
            summary=summary,
        )
        summary["validation_report"] = build_backtest_validation_report(
            cfg=cfg,
            trades=trades,
            skipped=skipped,
            data_quality=data_quality,
            summary=summary,
        )
        summary["research_report"] = build_backtest_research_report(
            cfg=cfg,
            trades=trades,
            skipped=skipped,
            data_quality=data_quality,
            summary=summary,
        )
        if ai_trader_team_report:
            summary["research_report"]["ai_trader_team"] = ai_trader_team_report
        return summary

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

    def _resolve_entry_bar(
        self,
        klines: List[Dict[str, Any]],
        decision_ts: int,
        delay_seconds: int,
        interval: int,
        max_entry_lag_seconds: int,
    ) -> "tuple[Optional[int], int]":
        """First observable strike bar at/after the decision.

        The strike is the OPEN of the bar containing decision_ts + delay.
        Returns (entry_idx, lag_seconds); lag is how much later than
        decision_ts the strike bar opens (0 for a contiguous series).
        """
        target_ts = decision_ts + max(0, int(delay_seconds))
        entry_idx = self._first_index_at_or_after(klines, decision_ts)
        if entry_idx is None:
            return None, 0
        while (
            entry_idx + 1 < len(klines)
            and klines[entry_idx]["timestamp"] + interval <= target_ts
        ):
            entry_idx += 1
        if entry_idx >= len(klines):
            return None, 0
        if klines[entry_idx]["timestamp"] + interval <= target_ts:
            return None, int(target_ts - klines[entry_idx]["timestamp"])
        lag = int(klines[entry_idx]["timestamp"] - decision_ts)
        if lag > max_entry_lag_seconds:
            return None, lag
        return entry_idx, lag
