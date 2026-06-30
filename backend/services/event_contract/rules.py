"""Deterministic rule-agent decisions for event-contract prefiltering."""

from __future__ import annotations

from typing import Any, Dict, List

from services.event_contract.constants import EVENT_AI_NAMES


class EventContractRuleMixin:
    def _build_rule_decisions(self, f: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        names = EVENT_AI_NAMES
        trend = self._dir_from_value(f["trend_score"], 0.025)
        momentum = self._dir_from_value(f["ret3"] + f["ret5"], 0.04)
        cvd = self._dir_from_value(f["cvd_proxy"], 0.06)
        flow_proxy = f.get("cvd_source") != "CoinGlass"
        l2_proxy = not f.get("l2_available")
        available_flow = set(f.get("coinglass_available_metrics") or [])
        vwap_dir = "long" if f["close"] > f["vwap"] else "short" if f["close"] < f["vwap"] else "hold"
        breakout_dir = "long" if f["breakout_up"] else "short" if f["breakout_down"] else trend
        sweep_dir = "long" if f["downside_fakeout"] or f["lower_wick_ratio"] > 0.5 else "short" if f["upside_fakeout"] or f["upper_wick_ratio"] > 0.5 else "hold"

        decisions = [
            self._decision(names[0], trend, 72 + min(abs(f["trend_score"]) * 120, 20), f"Micro trend score {f['trend_score']:.4f}", f),
            self._decision(names[1], self._structure_dir(f), 70, "Higher/lower structure from recent support and resistance", f),
            self._decision(names[2], momentum, 70 + min(abs(f["ret5"]) * 90, 20), f"Ret3 {f['ret3']:.4f}%, Ret5 {f['ret5']:.4f}%", f),
            self._decision(names[3], trend if f["volume_ratio"] >= 1.05 else "hold", min(90, 55 + f["volume_ratio"] * 18), f"Volume ratio {f['volume_ratio']:.2f}", f),
            self._decision(names[4], trend if 0.015 <= f["atr_pct"] <= 0.8 else "hold", 68, f"ATR% {f['atr_pct']:.4f}", f),
            self._decision(names[5], self._kline_dir(f, trend), 68, f"Body ratio {f['body_ratio']:.2f}", f),
            self._decision(names[6], sweep_dir if sweep_dir != "hold" else trend, 70, "Wick rejection and close location", f),
            self._decision(names[7], breakout_dir, 72, "Breakout / trend continuation check", f),
            self._decision(names[8], "hold" if f["fake_breakout_risk"] > 60 else trend, 88 - f["fake_breakout_risk"] * 0.35, f"Fake breakout risk {f['fake_breakout_risk']:.1f}", f),
            self._decision(names[9], self._pullback_dir(f, trend), 68, "EMA/VWAP pullback continuation", f),
            self._decision(names[10], "hold" if f["range_risk"] > 70 else trend, 85 - f["range_risk"] * 0.35, f"Range risk {f['range_risk']:.1f}", f),
            self._decision(names[11], "hold" if f["trap_risk"] > 60 else trend, 88 - f["trap_risk"] * 0.35, f"Trap risk {f['trap_risk']:.1f}", f),
            self._decision(names[12], "hold" if f["bull_trap_risk"] > 50 else trend, 86 - f["bull_trap_risk"] * 0.35, f"Bull trap risk {f['bull_trap_risk']:.1f}", f),
            self._decision(names[13], "hold" if f["bear_trap_risk"] > 50 else trend, 86 - f["bear_trap_risk"] * 0.35, f"Bear trap risk {f['bear_trap_risk']:.1f}", f),
            self._decision(names[14], sweep_dir if sweep_dir != "hold" else trend, 70, "Liquidity sweep proxy from wick and key levels", f),
            self._decision(names[15], sweep_dir if sweep_dir != "hold" else ("hold" if f["range_risk"] > 70 else trend), 68, "Stop-hunt proxy from level sweep", f),
            self._decision(names[16], self._orderbook_dir(f, trend), 72 if not l2_proxy else 62, f"{f['l2_source']} imbalance {f['orderbook_imbalance']:.3f}", f, proxy=l2_proxy),
            self._decision(names[17], self._spread_dir(f, trend), 70 if not l2_proxy else 65, f"{f['l2_source']} spread {f['spread_bps']:.3f} bps", f, proxy=l2_proxy),
            self._decision(names[18], cvd if cvd != "hold" else trend, 66, f"{f['cvd_source']} CVD {f['cvd_proxy']:.3f}", f, proxy=flow_proxy),
            self._decision(names[19], cvd if cvd != "hold" else momentum, 65, f"Taker flow delta {f['taker_delta']:.3f}", f, proxy="pair_taker_volume" not in available_flow),
            self._decision(names[20], self._oi_flow_dir(f, trend), 58, f"Open interest change {f['oi_change_pct']:.4f}%", f, proxy="open_interest" not in available_flow),
            self._decision(names[21], self._funding_dir(f, trend), 58, f"Funding rate {f['funding_rate']:.6f}", f, proxy="funding_rate" not in available_flow),
            self._decision(names[22], self._liquidation_dir(f, sweep_dir, trend), 60, f"Liquidation imbalance {f['liquidation_imbalance']:.3f}", f, proxy="pair_liquidation" not in available_flow),
            self._decision(names[23], self._support_resistance_dir(f, trend), 70, "Position relative to support/resistance", f),
            self._decision(names[24], vwap_dir, 68, f"Price {'above' if vwap_dir == 'long' else 'below' if vwap_dir == 'short' else 'at'} VWAP", f),
            self._decision(names[25], "hold" if f["mtf_conflict"] else trend, 78, f"MTF directions {f['mtf_dirs']}", f),
            self._decision(names[26], "hold" if f["market_state"] in ("range", "fake_breakout", "bull_trap", "bear_trap") else trend, 76, f"Market state {f['market_state']}", f),
            self._decision(names[27], "hold" if f["body_ratio"] < 0.18 or f["atr_pct"] < 0.01 else trend, 70, "Noise/body/ATR filter", f),
            self._decision(names[28], self._entry_timing_dir(f, trend), 72, "Immediate entry quality check", f),
            self._decision(names[29], "hold" if max(f["trap_risk"], f["fake_breakout_risk"], f["range_risk"]) > 60 else trend, 86, "Final risk gate", f),
        ]
        return decisions

    def _decision(
        self,
        name: str,
        direction: str,
        confidence: float,
        reason: str,
        f: Dict[str, Any],
        proxy: bool = False,
    ) -> Dict[str, Any]:
        direction = direction if direction in ("long", "short", "hold") else "hold"
        risk_flags = []
        if f["fake_breakout_risk"] > 60:
            risk_flags.append("fake_breakout_high")
        if f["trap_risk"] > 60:
            risk_flags.append("trap_high")
        if f["range_risk"] > 70:
            risk_flags.append("range_middle")
        if proxy:
            risk_flags.append("proxy_data")
        invalid = []
        if direction == "hold":
            invalid.append(reason)
        return {
            "ai_name": name,
            "source": "system_30_ai",
            "direction": direction,
            "confidence": round(max(0, min(100, confidence)), 2),
            "reason": reason,
            "risk_flags": risk_flags,
            "evidence": [
                f"trend_score={f['trend_score']:.4f}",
                f"volume_ratio={f['volume_ratio']:.2f}",
                f"range_pos={f['range_pos']:.2f}",
            ],
            "timeframes": ["1m", "3m", "5m", "15m"],
            "invalid_conditions": invalid,
        }

    def _dir_from_value(self, value: float, threshold: float) -> str:
        if value > threshold:
            return "long"
        if value < -threshold:
            return "short"
        return "hold"

    def _structure_dir(self, f: Dict[str, Any]) -> str:
        if f["range_pos"] > 0.62 and f["ema_diff_pct"] > 0:
            return "long"
        if f["range_pos"] < 0.38 and f["ema_diff_pct"] < 0:
            return "short"
        return self._dir_from_value(f["trend_score"], 0.035)

    def _kline_dir(self, f: Dict[str, Any], trend: str) -> str:
        if f["body_ratio"] < 0.18:
            return "hold"
        if f["lower_wick_ratio"] > 0.45:
            return "long"
        if f["upper_wick_ratio"] > 0.45:
            return "short"
        return trend

    def _pullback_dir(self, f: Dict[str, Any], trend: str) -> str:
        near_vwap = abs(f["close"] - f["vwap"]) / f["close"] * 100 < max(f["atr_pct"], 0.03)
        if near_vwap and trend in ("long", "short"):
            return trend
        return "hold" if f["range_risk"] > 70 else trend

    def _orderbook_proxy_dir(self, f: Dict[str, Any], trend: str) -> str:
        if f["body_ratio"] > 0.45 and f["volume_ratio"] > 1.0:
            return trend
        return "hold"

    def _orderbook_dir(self, f: Dict[str, Any], trend: str) -> str:
        if not f.get("l2_available"):
            return self._orderbook_proxy_dir(f, trend)
        imbalance = f.get("orderbook_imbalance", 0.0)
        if imbalance > 0.08:
            return "long"
        if imbalance < -0.08:
            return "short"
        return "hold"

    def _spread_dir(self, f: Dict[str, Any], trend: str) -> str:
        if not f.get("l2_available"):
            return "hold" if f["atr_pct"] > 1.0 else trend
        if f.get("spread_bps", 0.0) > 4.0:
            return "hold"
        return trend

    def _funding_proxy_dir(self, f: Dict[str, Any], trend: str) -> str:
        if f["rsi"] > 76:
            return "hold" if trend == "long" else "short"
        if f["rsi"] < 24:
            return "hold" if trend == "short" else "long"
        return trend

    def _oi_flow_dir(self, f: Dict[str, Any], trend: str) -> str:
        # CG data is consumed via coinglass_reversal_score in analysis.py (boost-only).
        # Keeping rules on the OHLCV fallback preserves the 30/30 consensus baseline
        # validated at 75% on 30 days; otherwise CG enable shaves trades 20 -> 5.
        return trend if f["volume_ratio"] >= 0.8 else "hold"

    def _funding_dir(self, f: Dict[str, Any], trend: str) -> str:
        return self._funding_proxy_dir(f, trend)

    def _liquidation_dir(self, f: Dict[str, Any], sweep_dir: str, trend: str) -> str:
        return sweep_dir if sweep_dir != "hold" else trend

    def _support_resistance_dir(self, f: Dict[str, Any], trend: str) -> str:
        if f["range_pos"] > 0.9 and trend == "long":
            return "hold"
        if f["range_pos"] < 0.1 and trend == "short":
            return "hold"
        return trend

    def _entry_timing_dir(self, f: Dict[str, Any], trend: str) -> str:
        if f["range_risk"] > 70 or f["fake_breakout_risk"] > 60:
            return "hold"
        if f.get("l2_available"):
            imbalance = f.get("orderbook_imbalance", 0.0)
            if f.get("spread_bps", 0.0) > 4.0:
                return "hold"
            if trend == "long" and imbalance < -0.15:
                return "hold"
            if trend == "short" and imbalance > 0.15:
                return "hold"
        if trend == "long" and f["upper_wick_ratio"] > 0.45:
            return "hold"
        if trend == "short" and f["lower_wick_ratio"] > 0.45:
            return "hold"
        return trend
