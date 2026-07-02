"""Shared feature helper methods for event-contract analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from services.event_contract.localization import localize_direction

from services.event_contract.constants import CRITICAL_REVIEWER_PREFIXES


class EventContractFeatureMixin:
    def _is_critical_reviewer(self, name: str) -> bool:
        return any(name.startswith(prefix) for prefix in CRITICAL_REVIEWER_PREFIXES)

    def _build_factor_snapshot(self, f: Dict[str, Any]) -> List[Dict[str, Any]]:
        cvd_name = "CoinGlass CVD" if f["cvd_source"] == "CoinGlass" else "CVD proxy"
        factor_defs = [
            ("1m EMA direction", "short_trend", f["ema_diff_pct"], f["trend_score"]),
            ("3m momentum", "momentum", f["ret3"], f["ret3"]),
            ("5m momentum", "momentum", f["ret5"], f["ret5"]),
            ("15m filter", "multi_timeframe", f["ret15"], f["ret15"]),
            ("Volume Spike", "volume", f["volume_ratio"], f["volume_ratio"] - 1),
            ("VWAP deviation", "volume", (f["close"] - f["vwap"]) / f["close"] * 100 if f["close"] else 0, f["close"] - f["vwap"]),
            ("Range Middle Risk", "structure", f["range_risk"], -f["range_risk"]),
            ("Fake Breakout", "trap", f["fake_breakout_risk"], -f["fake_breakout_risk"]),
            ("Bull Trap", "trap", f["bull_trap_risk"], -f["bull_trap_risk"]),
            ("Bear Trap", "trap", f["bear_trap_risk"], -f["bear_trap_risk"]),
            (cvd_name, "active_flow", f["cvd_proxy"], f["cvd_proxy"]),
            ("Support distance", "structure", (f["close"] - f["support"]) / f["close"] * 100 if f["close"] else 0, f["range_pos"] - 0.5),
            ("Resistance distance", "structure", (f["resistance"] - f["close"]) / f["close"] * 100 if f["close"] else 0, 0.5 - f["range_pos"]),
        ]
        if f["coinglass_available_metrics"]:
            factor_defs.extend(
                [
                    ("CoinGlass Taker Delta", "active_flow", f["taker_delta"], f["taker_delta"]),
                    ("CoinGlass OI change %", "open_interest", f["oi_change_pct"], f["oi_change_pct"] / 3),
                    ("CoinGlass Funding", "funding", f["funding_rate"], -f["funding_rate"] * 1000),
                    ("CoinGlass Liquidation Imbalance", "liquidation", f["liquidation_imbalance"], f["liquidation_imbalance"]),
                ]
            )
        if f["l2_available"]:
            depth_score = max(-1, min(1, (f["depth_ratio"] - 1) / 4))
            factor_defs.extend(
                [
                    ("L2 Orderbook Imbalance", "orderbook", f["orderbook_imbalance"], f["orderbook_imbalance"]),
                    ("L2 Depth Ratio", "orderbook", f["depth_ratio"], depth_score),
                    ("L2 Spread bps", "execution", f["spread_bps"], -f["spread_bps"] / 5),
                ]
            )
        factors = []
        for name, category, value, score in factor_defs:
            bias = self._dir_from_value(score, 0.03)
            normalized = max(-100, min(100, score * 100 if abs(score) < 5 else score))
            factors.append(
                {
                    "factor_name": name,
                    "category": category,
                    "timeframe": "1m",
                    "value": round(float(value), 6),
                    "normalized_score": round(normalized, 2),
                    "direction_bias": "neutral" if bias == "hold" else bias,
                    "confidence": round(min(100, 50 + abs(normalized) * 0.45), 2),
                    "weight": 1,
                    "explanation": (
                        f"{name} computed from CoinGlass historical data before entry time."
                        if name.startswith("CoinGlass")
                        else f"{name} computed from local L2 orderbook snapshot before entry time."
                        if name.startswith("L2")
                        else f"{name} computed from OHLCV snapshot before entry time."
                    ),
                }
            )
        return factors

    def _return_pct(self, values: List[float], periods: int) -> float:
        if len(values) <= periods or values[-periods - 1] == 0:
            return 0.0
        return (values[-1] - values[-periods - 1]) / values[-periods - 1] * 100

    def _ema(self, values: List[float], period: int) -> float:
        if not values:
            return 0.0
        alpha = 2 / (period + 1)
        result = values[0]
        for value in values[1:]:
            result = value * alpha + result * (1 - alpha)
        return result

    def _rsi(self, values: List[float], period: int = 14) -> float:
        if len(values) <= period:
            return 50.0
        gains = []
        losses = []
        for prev, cur in zip(values[-period - 1 : -1], values[-period:]):
            delta = cur - prev
            gains.append(max(delta, 0))
            losses.append(abs(min(delta, 0)))
        avg_gain = self._mean(gains)
        avg_loss = self._mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _atr_pct(self, history: List[Dict[str, Any]]) -> float:
        if not history:
            return 0.0
        ranges = [(item["high"] - item["low"]) / item["close"] * 100 for item in history if item["close"]]
        return self._mean(ranges)

    def _vwap(self, history: List[Dict[str, Any]]) -> float:
        total_volume = sum(item["volume"] for item in history)
        if total_volume <= 0:
            return history[-1]["close"] if history else 0.0
        return sum(((item["high"] + item["low"] + item["close"]) / 3) * item["volume"] for item in history) / total_volume

    def _signed_volume_delta(self, history: List[Dict[str, Any]]) -> float:
        total = sum(item["volume"] for item in history) or 1
        signed = 0.0
        for item in history:
            if item["close"] > item["open"]:
                signed += item["volume"]
            elif item["close"] < item["open"]:
                signed -= item["volume"]
        return signed / total

    def _probability_from_votes(
        self,
        direction: str,
        long_votes: int,
        short_votes: int,
        hold_votes: int,
        f: Dict[str, Any],
        confidence: float,
    ) -> float:
        votes = long_votes if direction == "long" else short_votes
        opposing = short_votes if direction == "long" else long_votes
        risk = max(f["trap_risk"], f["fake_breakout_risk"] * 0.8, f["range_risk"] * 0.6)
        score = 35 + votes * 2.0 - opposing * 1.4 - hold_votes * 0.9 + confidence * 0.12 - risk * 0.22
        return max(1, min(99, score))

    def _build_reason_summary(
        self,
        f: Dict[str, Any],
        direction: str,
        votes: int,
        blocked: List[str],
        reviewer_count: int,
        professional: Dict[str, Any] | None = None,
    ) -> str:
        if professional:
            score_text = (
                f"优势={professional['edge_score']:.1f}，"
                f"风险={professional['risk_score']:.1f}，"
                f"执行={professional['execution_score']:.1f}，"
                f"等级={professional['decision_grade']}"
            )
            if blocked:
                return f"{localize_direction(direction)}：专业评分未通过（{score_text}）：{blocked[0]}"
            return (
                f"{localize_direction(direction)}：专业评分通过（{score_text}）。"
                f"市场状态={f['market_state']}，趋势={f['trend_score']:.4f}，"
                f"成交量={f['volume_ratio']:.2f}，假突破={f['fake_breakout_risk']:.1f}，"
                f"陷阱={f['trap_risk']:.1f}。"
            )
        if blocked:
            return f"{localize_direction(direction)}被阻断：{blocked[0]}"
        return (
            f"{localize_direction(direction)}，获得 {votes}/{reviewer_count} 个评审投票。"
            f"市场状态={f['market_state']}，趋势={f['trend_score']:.4f}，"
            f"成交量={f['volume_ratio']:.2f}，假突破={f['fake_breakout_risk']:.1f}，"
            f"陷阱={f['trap_risk']:.1f}。"
        )

    def _mean(self, values: Iterable[float]) -> float:
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    def _avg(self, values: Iterable[float]) -> float:
        return self._mean(list(values))
