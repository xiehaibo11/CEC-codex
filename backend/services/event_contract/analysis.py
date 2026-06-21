"""Feature computation and snapshot analysis for event-contract signals."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from services.event_contract.constants import CRITICAL_REVIEWER_PREFIXES


class EventContractAnalysisMixin:
    def _analyze_snapshot(
        self,
        history: List[Dict[str, Any]],
        cfg: Dict[str, Any],
        decisions_override: Optional[List[Dict[str, Any]]] = None,
        source: str = "system_30_ai",
        ai_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        features = self._compute_features(history)
        ai_decisions = decisions_override or self._build_rule_decisions(features, cfg)
        long_votes = sum(1 for item in ai_decisions if item["direction"] == "long")
        short_votes = sum(1 for item in ai_decisions if item["direction"] == "short")
        hold_votes = sum(1 for item in ai_decisions if item["direction"] == "hold")
        reviewer_count = len(ai_decisions)
        top_votes = max(long_votes, short_votes)
        top_direction = "long" if long_votes > short_votes else "short" if short_votes > long_votes else "hold"
        consensus_rate = round(top_votes / reviewer_count * 100, 2)
        avg_confidence = sum(item["confidence"] for item in ai_decisions) / reviewer_count
        source_label = "LLM AI" if source == "llm_ai" else "30 AI"
        ai_participated = reviewer_count == 30

        blocked_reasons: List[str] = []
        critical_holds = [
            item["ai_name"]
            for item in ai_decisions
            if self._is_critical_reviewer(item.get("ai_name", "")) and item["direction"] == "hold"
        ]
        if critical_holds:
            blocked_reasons.append(f"Critical {source_label} hold: {', '.join(critical_holds)}")
        watch_threshold = min(max(cfg["consensus_threshold"], 28), 30)
        if top_votes < watch_threshold:
            blocked_reasons.append(f"{source_label} consensus below watch threshold: {top_votes}/30 < {watch_threshold}/30")
        if top_votes < 30 and top_direction in ("long", "short"):
            blocked_reasons.append(f"{source_label} not unanimous: {top_votes}/30. Trade signals require 30/30.")
        if cfg["enable_fake_breakout_filter"] and features["fake_breakout_risk"] > 60:
            blocked_reasons.append("Fake breakout risk above 60")
        if cfg["enable_trap_filter"] and features["trap_risk"] > 60:
            blocked_reasons.append("Trap risk above 60")
        if cfg["enable_range_filter"] and features["range_risk"] > 70:
            blocked_reasons.append("Current price is in range middle / no-trade zone")
        if cfg["enable_volume_filter"] and features["volume_ratio"] < 0.75:
            blocked_reasons.append("Volume confirmation is weak")
        if cfg["enable_multi_timeframe_filter"] and features["mtf_conflict"]:
            blocked_reasons.append("1m/3m/5m/15m directions conflict")
        if cfg["enable_cvd_filter"] and abs(features["cvd_proxy"]) < 0.08:
            blocked_reasons.append(f"{features['cvd_source']} CVD does not confirm direction")

        risk_penalty = (features["trap_risk"] + features["fake_breakout_risk"] + features["range_risk"]) / 3
        signal_strength = max(0, min(100, consensus_rate * 0.72 + avg_confidence * 0.28 - risk_penalty * 0.12))
        confidence = max(0, min(100, consensus_rate * 0.68 + avg_confidence * 0.32 - risk_penalty * 0.08))
        if signal_strength < 85:
            blocked_reasons.append("Signal strength below 85")
        if confidence < 85:
            blocked_reasons.append("Confidence below 85")

        allow_trade = (
            top_direction in ("long", "short")
            and not critical_holds
            and top_votes == 30
            and signal_strength >= 85
            and confidence >= 70
            and not blocked_reasons
        )
        signal_type = "trade_signal" if allow_trade else "watch_signal" if top_votes >= watch_threshold and top_direction != "hold" and not critical_holds else "hold_signal"
        final_direction = top_direction if signal_type in ("trade_signal", "watch_signal") else "hold"
        if critical_holds:
            final_direction = "hold"
            signal_type = "hold_signal"
        if not allow_trade and signal_type == "hold_signal":
            final_direction = "hold"

        long_probability = self._probability_from_votes("long", long_votes, short_votes, hold_votes, features, avg_confidence)
        short_probability = self._probability_from_votes("short", long_votes, short_votes, hold_votes, features, avg_confidence)
        hold_probability = max(0, min(100, 100 - max(long_probability, short_probability)))

        reason_summary = self._build_reason_summary(features, final_direction, top_votes, blocked_reasons)
        factors = self._build_factor_snapshot(features)

        entry_ts = self._decision_timestamp(history[-1], cfg)
        ai_consensus = {
            "symbol": cfg["symbol"],
            "contract_type": "5m_event_contract",
            "consensus_mode": cfg["consensus_mode"],
            "consensus_source": source,
            "ai_participated": ai_participated,
            "ai_model": (ai_meta or {}).get("model"),
            "ai_account_name": (ai_meta or {}).get("account_name"),
            "entry_time": self._to_iso(entry_ts),
            "expiry_time": self._to_iso(entry_ts + cfg["expiry_minutes"] * 60),
            "entry_price": history[-1]["close"],
            "final_direction": final_direction,
            "long_votes": long_votes,
            "short_votes": short_votes,
            "hold_votes": hold_votes,
            "consensus_rate": consensus_rate,
            "allow_trade": allow_trade,
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
            "blocked_reasons": blocked_reasons,
            "reason_summary": reason_summary,
            "factors": factors,
            "ai_decisions": ai_decisions,
            "ai_participated": ai_participated,
            "ai_model": (ai_meta or {}).get("model"),
            "ai_account_name": (ai_meta or {}).get("account_name"),
            "ai_consensus": ai_consensus,
        }

    def _compute_features(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        closes = [k["close"] for k in history]
        opens = [k["open"] for k in history]
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
        support = min(lows[-31:-1]) if len(lows) > 31 else min(lows[:-1] or lows)
        resistance = max(highs[-31:-1]) if len(highs) > 31 else max(highs[:-1] or highs)
        range_width_pct = (resistance - support) / close * 100 if close else 0
        range_pos = (close - support) / max(resistance - support, close * 0.000001)
        range_pos = max(0, min(1, range_pos))
        vwap = self._vwap(history[-60:])
        cvd_proxy_raw = self._signed_volume_delta(history[-30:])
        flow = last.get("coinglass") or {}
        cvd_value = flow.get("cvd_delta_norm")
        cvd_proxy = cvd_value if cvd_value is not None else cvd_proxy_raw
        cvd_source = "CoinGlass" if cvd_value is not None else "OHLCV proxy"
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
            "l2_available": l2_available,
            "l2_source": l2_source,
            "l2_lag_seconds": l2.get("lag_seconds"),
            "orderbook_imbalance": orderbook_imbalance,
            "depth_ratio": depth_ratio,
            "spread_bps": spread_bps,
            "bid_depth_10": l2.get("bid_depth_10"),
            "ask_depth_10": l2.get("ask_depth_10"),
            "trend_score": trend_score,
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

    def _build_reason_summary(self, f: Dict[str, Any], direction: str, votes: int, blocked: List[str]) -> str:
        if blocked:
            return f"{direction.upper()} blocked: {blocked[0]}"
        return (
            f"{direction.upper()} with {votes}/30 reviewer votes. "
            f"State={f['market_state']}, trend={f['trend_score']:.4f}, "
            f"volume={f['volume_ratio']:.2f}, fake={f['fake_breakout_risk']:.1f}, trap={f['trap_risk']:.1f}."
        )

    def _mean(self, values: Iterable[float]) -> float:
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    def _avg(self, values: Iterable[float]) -> float:
        return self._mean(list(values))
