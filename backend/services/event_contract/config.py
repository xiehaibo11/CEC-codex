"""Configuration normalization for event-contract runs."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from services.event_contract.constants import CONSENSUS_MODES, PERIOD_SECONDS


class EventContractConfigMixin:
    def _normalize_config(self, config: Dict[str, Any], prediction: bool) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        end_time = self._parse_datetime(config.get("end_time")) if config.get("end_time") else now
        start_time = self._parse_datetime(config.get("start_time")) if config.get("start_time") else end_time - timedelta(days=1)
        if end_time > now and not prediction:
            end_time = now
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        period = str(config.get("period") or "1m")
        if period not in PERIOD_SECONDS:
            raise ValueError(f"Unsupported period: {period}")
        expiry_minutes = int(config.get("expiry_minutes") or 5)
        if expiry_minutes <= 0 or expiry_minutes > 60:
            raise ValueError("expiry_minutes must be between 1 and 60")
        if PERIOD_SECONDS[period] > expiry_minutes * 60:
            raise ValueError(
                f"period {period} is too coarse for a {expiry_minutes}m event contract. "
                "Use a K-line period less than or equal to the expiry window."
            )

        cfg = {
            "symbol": self.normalize_symbol(config.get("symbol") or "BTC"),
            "exchange": str(config.get("exchange") or "binance").lower(),
            "environment": str(config.get("environment") or "mainnet").lower(),
            "period": period,
            "consensus_mode": str(config.get("consensus_mode") or "ai_confirmed").lower(),
            "ai_trader_id": int(config["ai_trader_id"]) if config.get("ai_trader_id") else None,
            "max_ai_evaluations": int(config.get("max_ai_evaluations") or (1 if prediction else 20)),
            "ai_temperature": float(config.get("ai_temperature") or 0.2),
            "llm_timeout_seconds": int(config.get("llm_timeout_seconds") or 180),
            "ai_max_retries": int(config.get("ai_max_retries") or 2),
            "start_time": start_time,
            "end_time": end_time,
            "expiry_minutes": expiry_minutes,
            "expiry_bars": max(1, math.ceil(expiry_minutes * 60 / PERIOD_SECONDS[period])),
            "initial_balance": float(config.get("initial_balance") or 10000),
            "stake_amount": float(config.get("stake_amount") or 100),
            "win_payout_ratio": float(config.get("win_payout_ratio") or 0.8),
            "fee_rate": float(config.get("fee_rate") or 0),
            "slippage_bps": float(config.get("slippage_bps") or 0),
            "delay_seconds": int(config.get("delay_seconds") or 0),
            "max_entry_lag_seconds": int(config.get("max_entry_lag_seconds") or PERIOD_SECONDS[period]),
            "max_expiry_lag_seconds": int(config.get("max_expiry_lag_seconds") or PERIOD_SECONDS[period]),
            "min_data_coverage_pct": float(config.get("min_data_coverage_pct") or 95),
            "strict_data_quality": bool(config.get("strict_data_quality", False)),
            "enable_l2_features": bool(config.get("enable_l2_features", False)),
            "min_l2_coverage_pct": float(config.get("min_l2_coverage_pct") or 96),
            "strict_l2_quality": bool(
                config.get("strict_l2_quality", True if config.get("enable_l2_features") else False)
            ),
            "max_l2_lag_seconds": int(config.get("max_l2_lag_seconds") or min(PERIOD_SECONDS[period], 60)),
            "enable_coinglass_features": bool(config.get("enable_coinglass_features", False)),
            "min_coinglass_coverage_pct": float(config.get("min_coinglass_coverage_pct") or 96),
            "strict_coinglass_quality": bool(
                config.get("strict_coinglass_quality", True if config.get("enable_coinglass_features") else False)
            ),
            "coinglass_metrics": config.get("coinglass_metrics"),
            "coinglass_interval": config.get("coinglass_interval"),
            "coinglass_no_future_leakage": bool(config.get("coinglass_no_future_leakage", True)),
            "max_coinglass_lag_seconds": int(
                config.get("max_coinglass_lag_seconds")
                or PERIOD_SECONDS.get(str(config.get("coinglass_interval") or period), PERIOD_SECONDS[period]) * 2
            ),
            "max_coinglass_pages_per_metric": int(config.get("max_coinglass_pages_per_metric") or 80),
            "_coinglass_api_key": str(config.get("_coinglass_api_key") or "").strip(),
            "_coinglass_key_source": str(config.get("_coinglass_key_source") or "server"),
            "consensus_threshold": int(config.get("consensus_threshold") or 30),
            "target_win_rate": float(config["target_win_rate"] if config.get("target_win_rate") is not None else 75),
            "target_min_trades": int(config.get("target_min_trades") or 10),
            "enable_edge_quality_gate": bool(config.get("enable_edge_quality_gate", True)),
            "max_trade_range_risk": float(
                config["max_trade_range_risk"] if config.get("max_trade_range_risk") is not None else 45
            ),
            "allow_pullback_trades": bool(config.get("allow_pullback_trades", False)),
            "enable_fake_breakout_filter": bool(config.get("enable_fake_breakout_filter", True)),
            "enable_trap_filter": bool(config.get("enable_trap_filter", True)),
            "enable_range_filter": bool(config.get("enable_range_filter", True)),
            "enable_multi_timeframe_filter": bool(config.get("enable_multi_timeframe_filter", True)),
            "enable_volume_filter": bool(config.get("enable_volume_filter", True)),
            "enable_cvd_filter": bool(config.get("enable_cvd_filter", False)),
            "draw_result": str(config.get("draw_result") or "loss"),
            "warmup_bars": int(config.get("warmup_bars") or 80),
            "max_bars": int(config.get("max_bars") or 50000),
            "return_trade_limit": int(config.get("return_trade_limit") or 300),
        }
        if cfg["consensus_mode"] not in CONSENSUS_MODES:
            raise ValueError(f"Unsupported consensus_mode: {cfg['consensus_mode']}")
        cfg["max_ai_evaluations"] = min(max(cfg["max_ai_evaluations"], 1), 200)
        cfg["llm_timeout_seconds"] = min(max(cfg["llm_timeout_seconds"], 30), 600)
        cfg["ai_max_retries"] = min(max(cfg["ai_max_retries"], 1), 5)
        cfg["max_entry_lag_seconds"] = min(max(cfg["max_entry_lag_seconds"], 0), PERIOD_SECONDS[period] * 3)
        cfg["max_expiry_lag_seconds"] = min(max(cfg["max_expiry_lag_seconds"], 0), PERIOD_SECONDS[period] * 3)
        cfg["min_data_coverage_pct"] = min(max(cfg["min_data_coverage_pct"], 0), 100)
        cfg["min_l2_coverage_pct"] = min(max(cfg["min_l2_coverage_pct"], 0), 100)
        cfg["max_l2_lag_seconds"] = min(max(cfg["max_l2_lag_seconds"], 0), PERIOD_SECONDS[period] * 3)
        cfg["min_coinglass_coverage_pct"] = min(max(cfg["min_coinglass_coverage_pct"], 0), 100)
        # CoinGlass max-lag scales off the CG sampling interval (which may be coarser than
        # the K-line period - e.g. 30m CG on 1m bars needs >= 1800s lag for forward-fill).
        cg_lag_unit = PERIOD_SECONDS.get(str(cfg.get("coinglass_interval") or period), PERIOD_SECONDS[period])
        cfg["max_coinglass_lag_seconds"] = min(max(cfg["max_coinglass_lag_seconds"], 0), cg_lag_unit * 10)
        cfg["max_coinglass_pages_per_metric"] = min(max(cfg["max_coinglass_pages_per_metric"], 1), 500)
        cfg["consensus_threshold"] = min(max(cfg["consensus_threshold"], 28), 30)
        cfg["target_win_rate"] = min(max(cfg["target_win_rate"], 0), 100)
        cfg["target_min_trades"] = min(max(cfg["target_min_trades"], 1), 10000)
        cfg["max_trade_range_risk"] = min(max(cfg["max_trade_range_risk"], 0), 100)
        cfg["stake_amount"] = max(cfg["stake_amount"], 1)
        cfg["initial_balance"] = max(cfg["initial_balance"], cfg["stake_amount"])
        cfg["return_trade_limit"] = min(max(cfg["return_trade_limit"], 1), 1000)
        return cfg
