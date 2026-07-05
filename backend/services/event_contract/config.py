"""Configuration normalization for event-contract runs."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from services.event_contract.constants import (
    CONSENSUS_MODES,
    DEFAULT_CONSENSUS_THRESHOLD,
    DEFAULT_REVIEWER_PANEL_SIZE,
    MAX_REVIEWER_PANEL_SIZE,
    PERIOD_SECONDS,
)


def _number(config: Dict[str, Any], key: str, default: float) -> float:
    """Extract numeric value from config, respecting explicit zero."""
    value = config.get(key)
    return float(value) if value is not None else float(default)


def _normalize_utc_hours(value: Any) -> Any:
    """Normalize a trading-session hour whitelist: sorted, deduped, 0-23.

    None / empty means no session restriction (trade all hours).
    """
    if not value:
        return None
    hours = sorted({int(h) for h in value})
    for hour in hours:
        if hour < 0 or hour > 23:
            raise ValueError(f"allowed_utc_hours values must be within 0-23, got {hour}")
    return hours


class EventContractConfigMixin:
    def _normalize_config(self, config: Dict[str, Any], prediction: bool) -> Dict[str, Any]:
        from services.event_contract.platforms import apply_platform_preset
        config = apply_platform_preset(config)
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
            "consensus_mode": str(config.get("consensus_mode") or "rule_only").lower(),
            "decision_policy": str(config.get("decision_policy") or "professional_v1").lower(),
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
            "win_payout_ratio": _number(config, "win_payout_ratio", 0.8),
            "fee_rate": _number(config, "fee_rate", 0),
            "slippage_bps": _number(config, "slippage_bps", 0),
            "impact_cost_bps": _number(config, "impact_cost_bps", 1.0),
            "delay_seconds": int(_number(config, "delay_seconds", 3)),
            "max_entry_lag_seconds": int(config.get("max_entry_lag_seconds") or PERIOD_SECONDS[period]),
            "max_expiry_lag_seconds": int(config.get("max_expiry_lag_seconds") or PERIOD_SECONDS[period]),
            "min_data_coverage_pct": float(config.get("min_data_coverage_pct") or 95),
            "strict_data_quality": bool(config.get("strict_data_quality", False)),
            "enable_flow_features": bool(config.get("enable_flow_features", True)),
            "min_flow_coverage_pct": float(config.get("min_flow_coverage_pct") or 90),
            "strict_flow_quality": bool(config.get("strict_flow_quality", False)),
            "max_flow_lag_seconds": int(config.get("max_flow_lag_seconds") or 60),
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
            "reviewer_panel_size": int(config.get("reviewer_panel_size") or DEFAULT_REVIEWER_PANEL_SIZE),
            "consensus_threshold": int(config.get("consensus_threshold") or DEFAULT_CONSENSUS_THRESHOLD),
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
            "platform": config["platform"],
            "min_stake": float(config.get("min_stake") or 1.0),
            "min_seconds_between_trades": int(config.get("min_seconds_between_trades") or 0),
            "daily_loss_cap": float(config["daily_loss_cap"]) if config.get("daily_loss_cap") is not None else None,
            "non_overlapping_only": bool(config.get("non_overlapping_only", True)),
            "allowed_utc_hours": _normalize_utc_hours(config.get("allowed_utc_hours")),
            "reviewer_weights_mode": str(config.get("reviewer_weights_mode") or "pre_window").lower(),
            "warmup_bars": int(config.get("warmup_bars") or 80),
            "max_bars": int(config.get("max_bars") or 50000),
            "return_trade_limit": int(config.get("return_trade_limit") or 300),
        }
        if cfg["consensus_mode"] not in CONSENSUS_MODES:
            raise ValueError(f"Unsupported consensus_mode: {cfg['consensus_mode']}")
        if cfg["decision_policy"] not in {"professional_v1", "legacy_vote"}:
            raise ValueError(f"Unsupported decision_policy: {cfg['decision_policy']}")
        if cfg["reviewer_weights_mode"] not in {"pre_window", "static", "unsafe_legacy"}:
            raise ValueError(f"Unsupported reviewer_weights_mode: {cfg['reviewer_weights_mode']}")
        if cfg["decision_policy"] == "professional_v1":
            # Professional workflow is not a blocking LLM vote.  It uses the
            # deterministic desk policy plus the independent 30-trader research
            # report; keeping ai_confirmed here causes stale/slow consensus
            # tasks and revives the wrong "all AIs must agree" mental model.
            cfg["consensus_mode"] = "rule_only"
            cfg["max_ai_evaluations"] = 1
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
        cfg["reviewer_panel_size"] = min(max(cfg["reviewer_panel_size"], 5), MAX_REVIEWER_PANEL_SIZE)
        cfg["consensus_threshold"] = min(max(cfg["consensus_threshold"], 1), cfg["reviewer_panel_size"])
        cfg["target_win_rate"] = min(max(cfg["target_win_rate"], 0), 100)
        cfg["target_min_trades"] = min(max(cfg["target_min_trades"], 1), 10000)
        cfg["max_trade_range_risk"] = min(max(cfg["max_trade_range_risk"], 0), 100)
        cfg["stake_amount"] = max(cfg["stake_amount"], 1)
        cfg["initial_balance"] = max(cfg["initial_balance"], cfg["stake_amount"])
        # --- Execution-cost floors -------------------------------------------------
        # Zero-cost assumptions make every run optimistic. But the RIGHT cost
        # model depends on the venue's documented product mechanics:
        #
        # Event-contract platforms (hibt, binance_event — sources in
        # platforms.py): stake-based binary contracts with NO separate trading
        # fee (the house edge lives in the 0.8 payout), and the strike is set
        # at the venue index/mark price at confirmation — the stake never
        # crosses an order book, so book slippage and market impact do not
        # apply. Forcing perp-style fee/slippage floors onto these venues
        # would be synthetic data, not conservatism. The honest cost there is
        # TIME: the confirmation delay (floored below) plus next-bar-open
        # entry pricing already enforced by the engine.
        #
        # Custom/unknown venues keep the conservative perp-style floors.
        enforced_cost_floors = []
        event_contract_platform = cfg["platform"] in ("hibt", "binance_event")
        if event_contract_platform:
            # Defaults (not floors) are perp assumptions too — zero them for
            # stake-based binary contracts unless the user explicitly priced
            # some venue-specific cost in.
            if config.get("impact_cost_bps") is None:
                cfg["impact_cost_bps"] = 0.0
            if config.get("slippage_bps") is None:
                cfg["slippage_bps"] = 0.0
        if not event_contract_platform:
            if cfg["slippage_bps"] < 2.0:
                enforced_cost_floors.append(
                    {"param": "slippage_bps", "requested": cfg["slippage_bps"], "floored_to": 2.0}
                )
                cfg["slippage_bps"] = 2.0
            if cfg["impact_cost_bps"] < 0.5:
                enforced_cost_floors.append(
                    {"param": "impact_cost_bps", "requested": cfg["impact_cost_bps"], "floored_to": 0.5}
                )
                cfg["impact_cost_bps"] = 0.5
            if cfg["fee_rate"] <= 0:
                enforced_cost_floors.append(
                    {"param": "fee_rate", "requested": cfg["fee_rate"], "floored_to": 0.001}
                )
                cfg["fee_rate"] = 0.001
        if cfg["delay_seconds"] < 3:
            enforced_cost_floors.append(
                {"param": "delay_seconds", "requested": cfg["delay_seconds"], "floored_to": 3}
            )
            cfg["delay_seconds"] = 3
        cfg["_platform_cost_model"] = (
            "event_contract_documented" if event_contract_platform else "custom_floored"
        )
        # Underscore prefix keeps the floor audit out of _public_config, so two
        # configs with identical effective costs share a fingerprint regardless
        # of what was originally requested.
        cfg["_enforced_cost_floors"] = enforced_cost_floors
        cfg["return_trade_limit"] = min(max(cfg["return_trade_limit"], 1), 1000)
        # --- Factor combination entry gate ----------------------------------------
        # Evidence (2026-07-05 run-2027 forensics): trades taken while both
        # "5m momentum" and "VWAP deviation" sit above their trailing p60 win
        # 56% on an honest train/test split vs the 50.4% unconditioned baseline.
        # Keys enter the normalized config ONLY when the gate is enabled so
        # existing strategies keep their fingerprints (rolling validation
        # continuity depends on fingerprint stability).
        if config.get("enable_factor_gate"):
            cfg["enable_factor_gate"] = True
            cfg["factor_gate_quantile"] = min(
                max(float(config.get("factor_gate_quantile") or 0.6), 0.5), 0.95
            )
            cfg["factor_gate_lookback"] = min(
                max(int(config.get("factor_gate_lookback") or 60), 20), 500
            )
            cfg["factor_gate_min_history"] = min(
                max(int(config.get("factor_gate_min_history") or 40), 10), cfg["factor_gate_lookback"]
            )
        if cfg["draw_result"] not in {"loss", "draw", "refund"}:
            raise ValueError(f"Unsupported draw_result: {cfg['draw_result']}")
        if cfg["stake_amount"] < cfg["min_stake"]:
            raise ValueError(
                f"stake_amount {cfg['stake_amount']} is below the {cfg['platform']} minimum {cfg['min_stake']}"
            )
        return cfg
