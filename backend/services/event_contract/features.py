"""Shared feature helper methods for event-contract analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from services.event_contract.localization import localize_direction

from services.event_contract.constants import CRITICAL_REVIEWER_PREFIXES


class EventContractFeatureMixin:
    def _is_critical_reviewer(self, name: str) -> bool:
        return any(name.startswith(prefix) for prefix in CRITICAL_REVIEWER_PREFIXES)

    def _build_factor_snapshot(self, f: Dict[str, Any]) -> List[Dict[str, Any]]:
        cvd_name = (
            "CoinGlass CVD"
            if f["cvd_source"] == "CoinGlass"
            else "Local CVD" if f["cvd_source"] == "Local flow" else "CVD proxy"
        )
        # Indicator-suite factor values (all real OHLCV+volume derived); score
        # sign follows direction bias: positive = long.
        macd_hist_norm = (
            (f.get("macd_hist") or 0.0) / f["close"] * 10_000 if f.get("close") else 0.0
        )  # histogram in bps of price
        bb_percent_b = f.get("bb_percent_b")
        bb_percent_b = 0.5 if bb_percent_b is None else float(bb_percent_b)
        band_walk_val = {"upper": 1.0, "lower": -1.0}.get(f.get("bb_band_walk"), 0.0)
        divergence_val = {"bullish": 1.0, "bearish": -1.0}.get(f.get("rsi_divergence"), 0.0)
        if f.get("obv_cross") == "up":
            obv_val = 1.0
        elif f.get("obv_cross") == "down":
            obv_val = -1.0
        else:
            obv_val = 0.3 if f.get("obv_above_ma") else -0.3
        pattern_val = {"double_bottom": 1.0, "double_top": -1.0}.get(f.get("double_pattern"), 0.0)
        if pattern_val and not f.get("double_pattern_confirmed"):
            pattern_val *= 0.4  # neckline not reclaimed yet - fragile structure
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
            # Signed by cross direction, scaled by 0-3 textbook confirmations
            # (sharp angle / persistence / slope acceleration); 0 on whipsaw.
            ("MA Cross Confirm", "short_trend", f.get("ma_cross_score") or 0.0, (f.get("ma_cross_score") or 0.0) / 30),
            ("MACD Histogram", "momentum", f.get("macd_hist") or 0.0, max(-1.0, min(1.0, macd_hist_norm / 5))),
            ("Bollinger %B", "structure", bb_percent_b, bb_percent_b - 0.5),
            ("Band Walk", "momentum", band_walk_val, band_walk_val * 0.5),
            ("RSI Divergence", "momentum", divergence_val, divergence_val * 0.6),
            ("OBV Trend", "volume", obv_val, obv_val * 0.5),
            ("W/M Pattern", "structure", pattern_val, pattern_val * 0.6),
        ]
        available_metrics = f["coinglass_available_metrics"] or []
        if available_metrics:
            # Label factors by their actual source; local flow supplies real
            # taker/OI/funding but has no liquidation feed, so that factor is
            # only emitted when the metric truly exists (no fabricated zeros).
            flow_prefix = "Local Flow" if f.get("flow_source") == "local_market_flow" else "CoinGlass"
            derivative_defs = [
                (f"{flow_prefix} Taker Delta", "active_flow", f["taker_delta"], f["taker_delta"]),
                (f"{flow_prefix} OI change %", "open_interest", f["oi_change_pct"], f["oi_change_pct"] / 3),
                (f"{flow_prefix} Funding", "funding", f["funding_rate"], -f["funding_rate"] * 1000),
            ]
            if "pair_liquidation" in available_metrics:
                derivative_defs.append(
                    (f"{flow_prefix} Liquidation Imbalance", "liquidation", f["liquidation_imbalance"], f["liquidation_imbalance"])
                )
            factor_defs.extend(derivative_defs)
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
                        else f"{name} computed from local market-flow records before entry time."
                        if name.startswith("Local Flow") or name == "Local CVD"
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

    def _ema_series(self, values: List[float], period: int) -> List[float]:
        if not values:
            return []
        alpha = 2 / (period + 1)
        out = [values[0]]
        for value in values[1:]:
            out.append(value * alpha + out[-1] * (1 - alpha))
        return out

    def _ma_cross_state(self, closes: List[float], atr_pct: float) -> Dict[str, Any]:
        """Grade the latest fast/slow EMA cross with three confirmations:
        sharp separation angle, persistence for >=2 closed bars without a
        re-cross, and fast-EMA slope acceleration in the cross direction.
        Two crosses inside the lookback means direction is undecidable and
        the state is flagged whipsaw instead of a signal."""
        neutral = {
            "direction": None,
            "bars_since": None,
            "confirmations": 0,
            "confirmed": False,
            "whipsaw": False,
            "angle_pct_per_bar": 0.0,
            "score": 0.0,
        }
        if len(closes) < 25:
            return neutral
        window = closes[-60:]
        fast = self._ema_series(window, 5)
        slow = self._ema_series(window, 20)
        diff = [f - s for f, s in zip(fast, slow)]
        lookback = 12
        start = max(2, len(diff) - lookback)
        crosses = [
            i
            for i in range(start, len(diff))
            if (diff[i] > 0 >= diff[i - 1]) or (diff[i] < 0 <= diff[i - 1])
        ]
        if not crosses:
            return neutral
        if len(crosses) >= 2:
            return {**neutral, "whipsaw": True}
        idx = crosses[-1]
        direction = "long" if diff[idx] > 0 else "short"
        bars_since = len(diff) - 1 - idx
        close = window[-1] or 1.0
        sep_growth = (abs(diff[-1]) - abs(diff[idx])) / max(bars_since, 1)
        angle_pct_per_bar = sep_growth / close * 100
        angle_ok = angle_pct_per_bar > max(atr_pct, 0.01) * 0.05
        persist_ok = bars_since >= 2
        slope_now = fast[-1] - fast[-2]
        slope_before = fast[idx - 1] - fast[idx - 2]
        slope_ok = slope_now > slope_before if direction == "long" else slope_now < slope_before
        confirmations = int(angle_ok) + int(persist_ok) + int(slope_ok)
        signed = 1.0 if direction == "long" else -1.0
        return {
            "direction": direction,
            "bars_since": bars_since,
            "confirmations": confirmations,
            "confirmed": confirmations == 3,
            "whipsaw": False,
            "angle_pct_per_bar": round(angle_pct_per_bar, 6),
            "score": signed * confirmations * 10.0,
        }

    def _macd_state(self, closes: List[float]) -> Dict[str, Any]:
        """MACD(12,26,9) with cross detection over the last 3 closed bars."""
        if len(closes) < 35:
            return {"line": 0.0, "signal": 0.0, "hist": 0.0, "cross": None}
        window = closes[-120:]
        ema12 = self._ema_series(window, 12)
        ema26 = self._ema_series(window, 26)
        macd_line = [a - b for a, b in zip(ema12, ema26)]
        signal = self._ema_series(macd_line, 9)
        hist = [m - s for m, s in zip(macd_line, signal)]
        cross = None
        for i in range(len(hist) - 1, max(len(hist) - 4, 0), -1):
            if hist[i] > 0 >= hist[i - 1]:
                cross = "golden"
                break
            if hist[i] < 0 <= hist[i - 1]:
                cross = "death"
                break
        return {
            "line": macd_line[-1],
            "signal": signal[-1],
            "hist": hist[-1],
            "cross": cross,
        }

    def _bollinger_state(self, closes: List[float]) -> Dict[str, Any]:
        """Bollinger(20,2): %B, bandwidth, and band-walk (3 consecutive closes
        riding a band = strong directional run)."""
        if len(closes) < 22:
            return {"percent_b": 0.5, "bandwidth_pct": 0.0, "band_walk": None}

        def _bands(values: List[float]) -> tuple:
            mid = sum(values) / len(values)
            std = (sum((c - mid) ** 2 for c in values) / len(values)) ** 0.5
            return mid + 2 * std, mid - 2 * std, mid

        upper, lower, mid = _bands(closes[-20:])
        close = closes[-1]
        span = upper - lower
        percent_b = (close - lower) / span if span else 0.5
        bandwidth_pct = span / mid * 100 if mid else 0.0
        checks = []
        for j in (3, 2, 1):
            u, lo, _ = _bands(closes[-19 - j : -(j - 1) or None])
            checks.append((closes[-j], u, lo))
        band_walk = None
        if all(c >= u for c, u, _ in checks):
            band_walk = "upper"
        elif all(c <= lo for c, _, lo in checks):
            band_walk = "lower"
        return {
            "percent_b": round(percent_b, 4),
            "bandwidth_pct": round(bandwidth_pct, 4),
            "band_walk": band_walk,
        }

    def _rsi_divergence(self, closes: List[float]) -> Any:
        """Fresh two-swing divergence: price lower low with RSI higher low ->
        'bullish'; price higher high with RSI lower high -> 'bearish'."""
        if len(closes) < 40:
            return None
        window = closes[-40:]
        swing_lows = [
            i
            for i in range(2, len(window) - 2)
            if window[i] <= min(window[i - 2 : i]) and window[i] <= min(window[i + 1 : i + 3])
        ]
        swing_highs = [
            i
            for i in range(2, len(window) - 2)
            if window[i] >= max(window[i - 2 : i]) and window[i] >= max(window[i + 1 : i + 3])
        ]

        def rsi_at(i: int) -> float:
            return self._rsi(window[: i + 1], 14)

        if len(swing_lows) >= 2:
            a, b = swing_lows[-2], swing_lows[-1]
            if (
                b - a >= 5
                and a >= 14
                and b >= len(window) - 15
                and window[b] < window[a]
                and rsi_at(b) > rsi_at(a) + 2
            ):
                return "bullish"
        if len(swing_highs) >= 2:
            a, b = swing_highs[-2], swing_highs[-1]
            if (
                b - a >= 5
                and a >= 14
                and b >= len(window) - 15
                and window[b] > window[a]
                and rsi_at(b) < rsi_at(a) - 2
            ):
                return "bearish"
        return None

    def _obv_state(self, closes: List[float], volumes: List[float]) -> Dict[str, Any]:
        """OBV vs its 20-bar MA: above/below plus a cross within 3 bars -
        the early-reversal read (OBV reclaiming its MA leads price)."""
        if len(closes) < 25 or len(volumes) < len(closes):
            return {"above_ma": False, "cross": None}
        window_c = closes[-60:]
        window_v = volumes[-len(window_c) :]
        obv = [0.0]
        for prev, cur, vol in zip(window_c, window_c[1:], window_v[1:]):
            step = vol if cur > prev else -vol if cur < prev else 0.0
            obv.append(obv[-1] + step)
        diff = []
        for i, value in enumerate(obv):
            lo = max(0, i - 19)
            diff.append(value - sum(obv[lo : i + 1]) / (i + 1 - lo))
        cross = None
        for i in range(len(diff) - 1, max(len(diff) - 4, 0), -1):
            if diff[i] > 0 >= diff[i - 1]:
                cross = "up"
                break
            if diff[i] < 0 <= diff[i - 1]:
                cross = "down"
                break
        return {"above_ma": diff[-1] > 0, "cross": cross}

    def _double_extreme_state(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        atr_pct: float,
    ) -> Dict[str, Any]:
        """W-bottom / M-top: two swing extremes at a similar level >=5 bars
        apart with the second one recent; the interim opposite extreme is the
        neckline and the pattern only 'confirms' once price closes past it."""
        neutral = {"pattern": None, "confirmed": False, "neckline": None}
        if len(closes) < 30:
            return neutral
        lo_w = lows[-40:]
        hi_w = highs[-40:]
        close = closes[-1]
        tolerance = max(atr_pct, 0.05) / 100 * close * 0.6
        swing_lows = [
            i
            for i in range(2, len(lo_w) - 2)
            if lo_w[i] <= min(lo_w[i - 2 : i]) and lo_w[i] <= min(lo_w[i + 1 : i + 3])
        ]
        swing_highs = [
            i
            for i in range(2, len(hi_w) - 2)
            if hi_w[i] >= max(hi_w[i - 2 : i]) and hi_w[i] >= max(hi_w[i + 1 : i + 3])
        ]
        if len(swing_lows) >= 2:
            a, b = swing_lows[-2], swing_lows[-1]
            if b - a >= 5 and b >= len(lo_w) - 12 and abs(lo_w[b] - lo_w[a]) <= tolerance:
                neckline = max(hi_w[a : b + 1])
                if neckline > max(lo_w[a], lo_w[b]):
                    return {
                        "pattern": "double_bottom",
                        "confirmed": close > neckline,
                        "neckline": neckline,
                    }
        if len(swing_highs) >= 2:
            a, b = swing_highs[-2], swing_highs[-1]
            if b - a >= 5 and b >= len(hi_w) - 12 and abs(hi_w[b] - hi_w[a]) <= tolerance:
                neckline = min(lo_w[a : b + 1])
                if neckline < min(hi_w[a], hi_w[b]):
                    return {
                        "pattern": "double_top",
                        "confirmed": close < neckline,
                        "neckline": neckline,
                    }
        return neutral

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
