from datetime import datetime, timezone

from services.event_contract_service import EventContractService
from api.event_contract_routes import BacktestRequest


def _base_cfg(**overrides):
    cfg = {
        "symbol": "BTC",
        "exchange": "binance",
        "environment": "mainnet",
        "period": "1m",
        "expiry_minutes": 5,
        "consensus_mode": "rule_only",
        "consensus_threshold": 30,
        "enable_fake_breakout_filter": True,
        "enable_trap_filter": True,
        "enable_range_filter": True,
        "enable_multi_timeframe_filter": True,
        "enable_volume_filter": True,
        "enable_cvd_filter": False,
        "enable_l2_features": False,
        "enable_coinglass_features": False,
        "strict_data_quality": False,
        "strict_l2_quality": False,
        "strict_coinglass_quality": False,
    }
    cfg.update(overrides)
    return EventContractService()._normalize_config(cfg, prediction=True)


def _trade_ready_features(**overrides):
    features = {
        "fake_breakout_risk": 0.0,
        "trap_risk": 10.0,
        "bull_trap_risk": 0.0,
        "bear_trap_risk": 0.0,
        "range_risk": 20.0,
        "market_state": "trend_up",
        "trend_score": 0.12,
        "volume_ratio": 1.8,
        "mtf_conflict": False,
        "cvd_proxy": 0.2,
        "cvd_source": "OHLCV proxy",
    }
    features.update(overrides)
    return features


def _all_long_decisions():
    return [
        {
            "ai_name": f"Reviewer {idx}",
            "direction": "long",
            "confidence": 96,
            "reason": "test",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
        }
        for idx in range(30)
    ]


def _directional_decisions(direction, count, *, start=0, confidence=96):
    return [
        {
            "ai_name": f"Reviewer {idx}",
            "direction": direction,
            "confidence": confidence,
            "reason": "test",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
        }
        for idx in range(start, start + count)
    ]


def _patch_analysis_dependencies(monkeypatch, service, features):
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(
        service, "_build_rule_decisions", lambda f, cfg: _all_long_decisions()
    )
    monkeypatch.setattr(service, "_build_factor_snapshot", lambda f: [])
    monkeypatch.setattr(
        service,
        "_build_event_signal",
        lambda cfg, latest, final_direction, allow_trade, signal_type, confidence, signal_strength, probabilities, risks, blocked_reasons, factors, ai_consensus: {
            "signal_type": "LONG_5M_EVENT" if allow_trade else "HOLD",
            "range_risk": risks["range"],
            "expected_win_rate": probabilities["long"],
        },
    )


def test_backtest_request_accepts_5_of_25_consensus():
    payload = BacktestRequest(
        start_time="2026-06-27T00:00:00+00:00",
        end_time="2026-06-28T00:00:00+00:00",
        consensus_threshold=5,
        reviewer_panel_size=25,
    ).model_dump()

    assert payload["consensus_threshold"] == 5
    assert payload["reviewer_panel_size"] == 25


def test_normalize_config_preserves_5_of_25_consensus():
    cfg = _base_cfg(consensus_threshold=5, reviewer_panel_size=25)

    assert cfg["consensus_threshold"] == 5
    assert cfg["reviewer_panel_size"] == 25


def test_event_contract_defaults_to_professional_rule_workflow():
    payload = BacktestRequest(
        start_time="2026-06-27T00:00:00+00:00",
        end_time="2026-06-28T00:00:00+00:00",
    ).model_dump()
    cfg = EventContractService()._normalize_config(
        {
            "start_time": "2026-06-27T00:00:00+00:00",
            "end_time": "2026-06-28T00:00:00+00:00",
        },
        prediction=False,
    )

    assert payload["consensus_mode"] == "rule_only"
    assert payload["decision_policy"] == "professional_v1"
    assert cfg["consensus_mode"] == "rule_only"
    assert cfg["decision_policy"] == "professional_v1"


def test_professional_policy_forces_rule_only_even_if_ai_confirmed_requested():
    cfg = EventContractService()._normalize_config(
        {
            "start_time": "2026-06-27T00:00:00+00:00",
            "end_time": "2026-06-28T00:00:00+00:00",
            "decision_policy": "professional_v1",
            "consensus_mode": "ai_confirmed",
            "reviewer_panel_size": 25,
        },
        prediction=False,
    )

    assert cfg["decision_policy"] == "professional_v1"
    assert cfg["consensus_mode"] == "rule_only"
    assert cfg["max_ai_evaluations"] == 1


def test_legacy_vote_policy_can_still_use_ai_confirmed_for_old_run_comparison():
    cfg = EventContractService()._normalize_config(
        {
            "start_time": "2026-06-27T00:00:00+00:00",
            "end_time": "2026-06-28T00:00:00+00:00",
            "decision_policy": "legacy_vote",
            "consensus_mode": "ai_confirmed",
            "reviewer_panel_size": 25,
            "max_ai_evaluations": 7,
        },
        prediction=False,
    )

    assert cfg["decision_policy"] == "legacy_vote"
    assert cfg["consensus_mode"] == "ai_confirmed"
    assert cfg["max_ai_evaluations"] == 7


def test_professional_policy_allows_strong_edge_without_unanimous_ai_votes(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(
        decision_policy="professional_v1",
        consensus_threshold=20,
        reviewer_panel_size=25,
        enable_edge_quality_gate=False,
    )
    features = _trade_ready_features(
        trend_score=0.42,
        volume_ratio=2.4,
        range_risk=12,
        trap_risk=8,
        fake_breakout_risk=4,
    )
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(service, "_build_factor_snapshot", lambda f: [])
    decisions = (
        _directional_decisions("long", 8, confidence=96)
        + _directional_decisions("hold", 16, start=8, confidence=82)
    )

    analysis = service._analyze_snapshot(
        [{"timestamp": 1, "close": 100}],
        cfg,
        decisions_override=decisions,
        source="llm_ai",
    )

    assert analysis["decision_policy"] == "professional_v1"
    assert analysis["allow_trade"] is True
    assert analysis["final_direction"] == "long"
    assert analysis["trade_readiness"] == "tradable"
    assert analysis["edge_score"] >= 75
    assert analysis["risk_score"] < 35
    assert analysis["execution_score"] >= 70
    assert analysis["decision_grade"] in {"A", "B"}
    assert analysis["veto_reasons"] == []
    assert analysis["ai_consensus"]["required_votes"] == 20
    assert analysis["ai_consensus"]["top_votes"] < analysis["ai_consensus"]["required_votes"]
    assert "专业评分" in analysis["reason_summary"]
    assert "评审投票" not in analysis["reason_summary"]
    assert "decision_diagnostics" in analysis["event_signal"]


def test_professional_policy_treats_critical_reviewer_holds_as_diagnostics_when_risk_low(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(
        decision_policy="professional_v1",
        consensus_threshold=20,
        reviewer_panel_size=25,
        enable_edge_quality_gate=False,
    )
    features = _trade_ready_features(
        trend_score=0.42,
        volume_ratio=2.4,
        range_risk=12,
        trap_risk=8,
        fake_breakout_risk=4,
    )
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(service, "_build_factor_snapshot", lambda f: [])
    decisions = [
        {
            "ai_name": "Fake Breakout AI",
            "direction": "hold",
            "confidence": 80,
            "reason": "diagnostic caution",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        {
            "ai_name": "Trap Detection AI",
            "direction": "hold",
            "confidence": 80,
            "reason": "diagnostic caution",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        {
            "ai_name": "Final Risk AI",
            "direction": "hold",
            "confidence": 80,
            "reason": "diagnostic caution",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        *_directional_decisions("long", 18, start=1, confidence=96),
        *_directional_decisions("hold", 3, start=19, confidence=82),
    ]
    for item in decisions:
        item["source"] = "llm_ai"

    analysis = service._analyze_snapshot(
        [{"timestamp": 1, "close": 100}],
        cfg,
        decisions_override=decisions,
        source="llm_ai",
    )

    assert analysis["decision_policy"] == "professional_v1"
    assert analysis["allow_trade"] is True
    assert analysis["final_direction"] == "long"
    assert analysis["trade_readiness"] == "tradable"
    assert analysis["veto_reasons"] == []
    assert not any("关键大模型评审选择观望" in reason for reason in analysis["blocked_reasons"])
    assert not any("信号强度低于 85" in reason for reason in analysis["blocked_reasons"])
    assert not any("置信度低于 85" in reason for reason in analysis["blocked_reasons"])
    assert analysis["decision_diagnostics"]["risk_veto_count"] == 0
    assert analysis["event_signal"]["trade_readiness"] == "tradable"


def test_professional_policy_feature_risk_still_vetoes_trade(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(
        decision_policy="professional_v1",
        consensus_threshold=20,
        reviewer_panel_size=25,
        enable_edge_quality_gate=False,
    )
    features = _trade_ready_features(
        trend_score=0.42,
        volume_ratio=2.4,
        range_risk=12,
        trap_risk=8,
        fake_breakout_risk=72,
    )
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(service, "_build_factor_snapshot", lambda f: [])
    decisions = _directional_decisions("long", 22, confidence=96)

    analysis = service._analyze_snapshot(
        [{"timestamp": 1, "close": 100}],
        cfg,
        decisions_override=decisions,
        source="llm_ai",
    )

    assert analysis["decision_policy"] == "professional_v1"
    assert analysis["allow_trade"] is False
    assert analysis["final_direction"] == "hold"
    assert analysis["trade_readiness"] == "blocked"
    assert any("假突破风险高于 60" in reason for reason in analysis["veto_reasons"])


def test_load_klines_backfills_recent_internal_gap(monkeypatch):
    service = EventContractService()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = now_ts - 6 * 60
    end_ts = now_ts
    incomplete = [
        {"timestamp": start_ts + offset * 60, "close": 100 + offset}
        for offset in (0, 1, 2, 4, 5, 6)
    ]
    complete = [
        {"timestamp": start_ts + offset * 60, "close": 100 + offset}
        for offset in range(7)
    ]
    calls = []
    backfills = []

    def fake_query(*args):
        calls.append(args)
        return incomplete if len(calls) == 1 else complete

    def fake_backfill(db, symbol, period, min_bars, environment):
        backfills.append((symbol, period, min_bars, environment))

    monkeypatch.setattr(service, "_query_klines", fake_query)
    monkeypatch.setattr(service, "_backfill_recent_binance_klines", fake_backfill)

    klines = service._load_klines(
        object(),
        "binance",
        "BTC",
        "1m",
        start_ts,
        end_ts,
        "mainnet",
        min_bars=5,
    )

    assert len(calls) == 2
    assert backfills == [("BTC", "1m", 7, "mainnet")]
    assert [item["timestamp"] for item in klines] == [
        item["timestamp"] for item in complete
    ]


def test_audit_kline_series_reports_missing_bar_count():
    service = EventContractService()
    cfg = _base_cfg(period="1m")
    start_ts = 1_000
    klines = [{"timestamp": start_ts + offset * 60} for offset in (0, 1, 4)]

    audit = service._audit_kline_series(klines, cfg, start_ts + 60, start_ts + 5 * 60)

    assert audit["gap_count"] == 1
    assert audit["missing_bar_count"] == 2
    assert audit["sample_gaps"][0]["missing_bars"] == 2


def test_main_logic_vote_is_included_in_final_consensus(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(consensus_threshold=5, reviewer_panel_size=25)
    _patch_analysis_dependencies(monkeypatch, service, _trade_ready_features())

    llm_decisions = _directional_decisions(
        "long", 4, confidence=96
    ) + _directional_decisions("hold", 20, start=4, confidence=80)
    analysis = service._analyze_snapshot(
        [{"timestamp": 1, "close": 100}],
        cfg,
        decisions_override=llm_decisions,
        source="llm_ai",
    )

    assert len(analysis["ai_decisions"]) == 25
    assert analysis["ai_decisions"][0]["ai_name"] == "Main Logic"
    assert analysis["ai_consensus"]["main_logic_participated"] is True
    assert analysis["ai_consensus"]["reviewer_count"] == 25
    assert analysis["ai_consensus"]["required_votes"] == 5
    assert analysis["ai_consensus"]["top_votes"] == 5
    assert not any(
        "30/30" in reason or "unanimous" in reason
        for reason in analysis["blocked_reasons"]
    )


def test_llm_hold_block_reasons_are_localized_to_chinese(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(decision_policy="legacy_vote", consensus_threshold=5, reviewer_panel_size=25)
    features = _trade_ready_features(mtf_conflict=True)
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(service, "_build_factor_snapshot", lambda f: [])
    decisions = [
        {
            "ai_name": "Fake Breakout AI",
            "direction": "hold",
            "confidence": 40,
            "reason": "test",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        {
            "ai_name": "Trap Detection AI",
            "direction": "hold",
            "confidence": 40,
            "reason": "test",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        {
            "ai_name": "Final Risk AI",
            "direction": "hold",
            "confidence": 40,
            "reason": "test",
            "risk_flags": [],
            "evidence": [],
            "timeframes": [],
            "invalid_conditions": [],
            "source": "llm_ai",
        },
        *_directional_decisions("long", 22, start=3, confidence=40),
    ]
    for item in decisions:
        item["source"] = "llm_ai"

    analysis = service._analyze_snapshot(
        [{"timestamp": 1, "close": 100}],
        cfg,
        decisions_override=decisions,
        source="llm_ai",
    )

    joined_reasons = "; ".join(analysis["blocked_reasons"])
    assert analysis["event_signal_type"] == "NO_TRADE_ZONE"
    assert analysis["reason_summary"].startswith("观望被阻断：")
    assert "关键大模型评审选择观望：假突破评审、陷阱检测评审、最终风险评审" in joined_reasons
    assert "1m/3m/5m/15m 多周期方向冲突" in joined_reasons
    assert "信号强度低于 85" in joined_reasons
    assert "置信度低于 85" in joined_reasons
    assert analysis["event_signal"]["entry_condition"].startswith("暂无立即入场条件")
    assert "；" in analysis["event_signal"]["avoid_condition"]
    assert "; " not in analysis["event_signal"]["avoid_condition"]
    assert "Critical LLM AI hold" not in joined_reasons
    assert "directions conflict" not in joined_reasons
    assert "Signal strength below 85" not in joined_reasons
    assert "HOLD blocked" not in analysis["reason_summary"]


def test_settlement_direction_rules_are_not_adjusted_to_target_win_rate():
    service = EventContractService()

    assert service._settle_event_contract("long", 100, 101, "loss") == "win"
    assert service._settle_event_contract("long", 100, 99, "loss") == "loss"
    assert service._settle_event_contract("short", 100, 99, "loss") == "win"
    assert service._settle_event_contract("short", 100, 101, "loss") == "loss"
    assert service._settle_event_contract("long", 100, 100, "draw") == "draw"
    assert service._settle_event_contract("short", 100, 100, "loss") == "loss"


def test_target_edge_gate_blocks_pullback_before_trade(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(enable_edge_quality_gate=True, target_win_rate=75)
    _patch_analysis_dependencies(
        monkeypatch,
        service,
        _trade_ready_features(market_state="pullback", range_risk=20),
    )

    analysis = service._analyze_snapshot([{"timestamp": 1, "close": 100}], cfg)

    assert analysis["allow_trade"] is False
    assert analysis["final_direction"] == "hold"
    assert any("75% 胜率质量门" in reason for reason in analysis["blocked_reasons"])


def test_target_edge_gate_blocks_high_range_risk_before_trade(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(
        enable_edge_quality_gate=True, target_win_rate=75, max_trade_range_risk=45
    )
    _patch_analysis_dependencies(
        monkeypatch,
        service,
        _trade_ready_features(market_state="trend_up", range_risk=46),
    )

    analysis = service._analyze_snapshot([{"timestamp": 1, "close": 100}], cfg)

    assert analysis["allow_trade"] is False
    assert analysis["final_direction"] == "hold"
    assert any("震荡区间风险" in reason for reason in analysis["blocked_reasons"])


def test_backtest_request_preserves_edge_gate_fields():
    payload = BacktestRequest(
        start_time="2026-06-27T00:00:00+00:00",
        end_time="2026-06-28T00:00:00+00:00",
        target_win_rate=80,
        target_min_trades=20,
        enable_edge_quality_gate=False,
        max_trade_range_risk=33,
        allow_pullback_trades=True,
    ).model_dump()

    assert payload["target_win_rate"] == 80
    assert payload["target_min_trades"] == 20
    assert payload["enable_edge_quality_gate"] is False
    assert payload["max_trade_range_risk"] == 33
    assert payload["allow_pullback_trades"] is True


def test_summary_marks_partial_for_skipped_settlement_and_nested_warnings():
    service = EventContractService()
    cfg = _base_cfg()
    summary = service._build_summary(
        cfg,
        trades=[
            {
                "result": "win",
                "profit_loss": 80,
                "direction": "long",
                "signal_strength": 90,
                "trap_risk": 10,
                "market_state": "trend_up",
            }
        ],
        final_equity=10_000,
        max_drawdown=0,
        skipped={
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 0,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 1,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 1,
            "candidate_signals_count": 0,
        },
        data_quality={
            "warnings": [],
            "coinglass": {"warnings": ["coverage low"]},
        },
    )

    assert summary["partial"] is True
    assert summary["audit_status"] == "partial"
    assert summary["decision_policy"] == "professional_v1"
    assert summary["win_rate"] == 100
    assert summary["target_sample_met"] is False
    assert summary["target_win_rate_met"] is False


def test_summary_requires_minimum_sample_before_target_is_met():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=10)
    base_trade = {
        "result": "win",
        "profit_loss": 80,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
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
        "decision_bars_count": 10,
        "candidate_signals_count": 10,
    }

    small_sample = service._build_summary(
        cfg, [base_trade] * 9, 10_720, 0, skipped, {"warnings": []}
    )
    enough_sample = service._build_summary(
        cfg, [base_trade] * 10, 10_800, 0, skipped, {"warnings": []}
    )

    assert small_sample["win_rate"] == 100
    assert small_sample["target_sample_met"] is False
    assert small_sample["target_win_rate_met"] is False
    assert enough_sample["target_sample_met"] is True
    assert enough_sample["target_win_rate_met"] is True


def test_validation_report_flags_walk_forward_regime_and_decay_risk():
    service = EventContractService()
    cfg = _base_cfg(
        target_min_trades=12,
        target_win_rate=65,
        fee_rate=0,
        slippage_bps=0,
    )
    trades = []
    for idx in range(12):
        weak_regime = idx >= 8
        trades.append(
            {
                "trade_index": idx + 1,
                "entry_time": f"2026-06-01T00:{idx:02d}:00+00:00",
                "direction": "long" if idx % 2 == 0 else "short",
                "result": "loss" if weak_regime else "win",
                "profit_loss": -100 if weak_regime else 80,
                "signal_strength": 88,
                "trap_risk": 55 if weak_regime else 10,
                "market_state": "range" if weak_regime else "trend_up",
            }
        )

    summary = service._build_summary(
        cfg,
        trades=trades,
        final_equity=cfg["initial_balance"] + sum(item["profit_loss"] for item in trades),
        max_drawdown=400,
        skipped={},
        data_quality={"warnings": []},
    )

    report = summary["validation_report"]
    assert report["walk_forward"]["window_count"] >= 3
    assert report["walk_forward"]["worst_window_pnl"] < 0
    assert report["monte_carlo"]["simulations"] == 200
    assert 0 <= report["monte_carlo"]["profitable_ratio"] <= 100
    assert report["regime_stability"]["weakest_regime"] == "range"
    assert report["regime_stability"]["unstable_regime_count"] >= 1
    assert report["live_decay_estimate"]["expected_decay_pct"] >= 50
    assert report["live_decay_estimate"]["conservative_pnl"] < summary["total_pnl"]
    assert report["verdict"] in {"pass", "warning", "fail"}


def test_research_report_detects_oos_decay_candidates_and_missing_data():
    service = EventContractService()
    cfg = _base_cfg(
        target_min_trades=10,
        target_win_rate=75,
        fee_rate=0,
        slippage_bps=0,
        enable_l2_features=True,
        enable_coinglass_features=True,
    )

    def trade(idx: int, result: str, direction: str, momentum: float, vwap: float):
        return {
            "trade_index": idx,
            "result": result,
            "profit_loss": 80 if result == "win" else -100,
            "direction": direction,
            "signal_strength": 88,
            "trap_risk": 15,
            "market_state": "trend_up" if direction == "long" else "trend_down",
            "factor_snapshot": [
                {
                    "factor_name": "3m momentum",
                    "category": "momentum",
                    "value": momentum,
                    "normalized_score": momentum * 100,
                },
                {
                    "factor_name": "VWAP deviation",
                    "category": "volume",
                    "value": vwap,
                    "normalized_score": vwap * 100,
                },
            ],
        }

    trades = [
        trade(idx, "win", "long", 0.25, 0.3)
        for idx in range(1, 13)
    ] + [
        trade(idx, "loss", "short", -0.03, -0.02)
        for idx in range(13, 21)
    ]

    summary = service._build_summary(
        cfg,
        trades=trades,
        final_equity=cfg["initial_balance"] + sum(item["profit_loss"] for item in trades),
        max_drawdown=800,
        skipped={
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 20,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 20,
            "candidate_signals_count": 20,
        },
        data_quality={
            "warnings": [],
            "l2": {"enabled": True, "coverage_pct": 0, "warnings": ["no local L2 orderbook snapshots found"]},
            "coinglass": {"enabled": True, "coverage_pct": 0, "warnings": ["CoinGlass unavailable"]},
        },
    )

    report = summary["research_report"]
    assert report["version"] == "research-v1"
    assert report["oos_validation"]["train_win_rate"] > report["oos_validation"]["oos_win_rate"]
    assert report["oos_validation"]["overfit_risk"] in {"high", "critical"}
    assert any(item["candidate_id"] == "baseline_all" for item in report["strategy_candidates"])
    assert any(item["factor_name"] == "3m momentum" for item in report["factor_insights"])
    assert any("样本外" in item["message"] for item in report["overfitting_warnings"])
    assert any(item["data_type"] == "L2 orderbook" for item in report["missing_data_recommendations"])
    assert any(item["data_type"] == "CoinGlass derivatives" for item in report["missing_data_recommendations"])


def test_ai_trader_team_report_tracks_30_independent_traders_without_consensus():
    from services.event_contract.ai_trader_team import (
        build_ai_trader_team_state,
        finalize_ai_trader_team_report,
        record_ai_trader_team_decisions,
    )
    from services.event_contract.constants import EVENT_AI_NAMES

    cfg = _base_cfg(
        target_min_trades=2,
        stake_amount=100,
        win_payout_ratio=0.8,
        fee_rate=0,
        slippage_bps=0,
    )
    state = build_ai_trader_team_state(cfg)
    decisions = [
        {
            "ai_name": name,
            "source": "system_panel",
            "direction": "long" if idx % 2 == 0 else "short",
            "confidence": 82,
            "reason": "unit-test independent trader",
            "risk_flags": [],
            "evidence": ["unit=test"],
            "timeframes": ["1m", "3m", "5m", "15m"],
            "invalid_conditions": [],
        }
        for idx, name in enumerate(EVENT_AI_NAMES)
    ]

    record_ai_trader_team_decisions(
        state=state,
        cfg=cfg,
        decisions=decisions,
        signal_time="2026-07-02T00:00:00+00:00",
        entry_time="2026-07-02T00:00:00+00:00",
        expiry_time="2026-07-02T00:05:00+00:00",
        entry_price=100,
        expiry_price=101,
        market_state="trend_up",
    )
    record_ai_trader_team_decisions(
        state=state,
        cfg=cfg,
        decisions=decisions,
        signal_time="2026-07-02T00:01:00+00:00",
        entry_time="2026-07-02T00:01:00+00:00",
        expiry_time="2026-07-02T00:06:00+00:00",
        entry_price=100,
        expiry_price=99,
        market_state="trend_down",
    )

    report = finalize_ai_trader_team_report(state, cfg)

    assert report["mode"] == "independent_traders"
    assert report["total_traders"] == 30
    assert report["total_team_trades"] == 60
    assert len(report["traders"]) == 30
    assert "consensus_vote" not in report

    first = report["traders"][0]
    assert first["trader_id"] == "trend_micro_ai"
    assert first["name"] == "趋势微结构AI交易员"
    assert first["trade_count"] == 2
    assert first["wins"] == 1
    assert first["win_rate"] == 50.0
    assert first["pnl"] == -20
    assert first["train_trade_count"] == 1
    assert first["train_win_rate"] == 100.0
    assert first["oos_trade_count"] == 1
    assert first["oos_win_rate"] == 0.0
    assert all("consensus_rate" not in trader for trader in report["traders"])


def test_summary_attaches_ai_trader_team_inside_research_report():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=1, fee_rate=0, slippage_bps=0)
    team_report = {
        "mode": "independent_traders",
        "total_traders": 30,
        "traders": [],
    }

    summary = service._build_summary(
        cfg,
        trades=[],
        final_equity=cfg["initial_balance"],
        max_drawdown=0,
        skipped={},
        data_quality={"warnings": []},
        ai_trader_team_report=team_report,
    )

    assert summary["research_report"]["ai_trader_team"] == team_report
    assert summary["research_report"]["ai_trader_team"]["mode"] == "independent_traders"


def test_summary_quality_gate_flags_low_sample_partial_and_nested_warnings():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=10, fee_rate=0.0004, slippage_bps=5)
    trade = {
        "result": "win",
        "profit_loss": 80,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    summary = service._build_summary(
        cfg,
        [trade] * 3,
        10_240,
        0,
        {
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 0,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 1,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 3,
            "candidate_signals_count": 3,
        },
        {
            "warnings": [],
            "l2": {"warnings": ["L2 coverage 70% below target"]},
        },
    )

    quality_gate = summary["quality_gate"]
    checks = {check["id"]: check for check in quality_gate["checks"]}
    assert quality_gate["grade"] in {"D", "F"}
    assert quality_gate["status"] == "fail"
    assert checks["sample_size"]["status"] == "fail"
    assert checks["audit_completeness"]["status"] == "fail"
    assert checks["data_quality"]["status"] == "warning"
    assert any("Increase the backtest window" in item for item in quality_gate["recommendations"])


def test_summary_quality_gate_warns_when_fee_and_slippage_are_zero():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=2, fee_rate=0, slippage_bps=0)
    trade = {
        "result": "win",
        "profit_loss": 80,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    summary = service._build_summary(
        cfg,
        [trade] * 2,
        10_160,
        0,
        {
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
            "decision_bars_count": 2,
            "candidate_signals_count": 2,
        },
        {"warnings": []},
    )

    quality_gate = summary["quality_gate"]
    checks = {check["id"]: check for check in quality_gate["checks"]}
    # Now expects "fail" because 2/2 wins (CI lower bound 34.24%) is below breakeven (50%),
    # so target_win_rate_status is "not_met" and target_edge check fails. Combined with
    # execution_costs warning, overall status becomes "fail" per new stricter semantics.
    assert quality_gate["status"] == "fail"
    assert checks["execution_costs"]["status"] == "warning"
    assert any("Set non-zero fee and slippage" in item for item in quality_gate["recommendations"])


def test_summary_quality_gate_passes_complete_costed_backtest():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=10, fee_rate=0.0004, slippage_bps=5)
    trade = {
        "result": "win",
        "profit_loss": 79.96,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    summary = service._build_summary(
        cfg,
        [trade] * 10,
        10_799.6,
        0,
        {
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 10,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 10,
            "candidate_signals_count": 10,
        },
        {"warnings": []},
    )

    quality_gate = summary["quality_gate"]
    assert quality_gate["grade"] == "A"
    assert quality_gate["score"] >= 90
    assert quality_gate["status"] == "pass"
    assert quality_gate["warnings"] == []


def test_summary_quality_gate_preserves_zero_target_win_rate_message():
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=1, target_win_rate=0, fee_rate=0.0004, slippage_bps=5)
    trade = {
        "result": "loss",
        "profit_loss": -100.04,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    summary = service._build_summary(
        cfg,
        [trade],
        9_899.96,
        1,
        {
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 1,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 1,
            "candidate_signals_count": 1,
        },
        {"warnings": []},
    )

    target_edge = next(
        check for check in summary["quality_gate"]["checks"] if check["id"] == "target_edge"
    )
    assert summary["target_win_rate"] == 0
    # Now expects False because with 0 wins out of 1 decided trade, CI lower bound is 0%
    # which is below breakeven (~50%). New semantics require CI lower bound >= breakeven.
    assert summary["target_win_rate_met"] is False
    assert summary["target_win_rate_status"] == "not_met"
    # The target_edge check status reflects the new stricter semantics
    assert target_edge["status"] == "fail"


def test_summary_quality_gate_uses_decided_trades_for_draw_heavy_sample():
    # Draw-heavy run: 4W/1L/15D with target_min_trades=10. Only 5 trades are
    # decided, well below the target, even though total_trades (20) clears
    # it. The quality gate must key sample sufficiency off decided trades so
    # it doesn't contradict summary["target_win_rate_status"] ==
    # "insufficient_sample" by reporting a complete sample and a misleading
    # "win rate below target" message.
    service = EventContractService()
    cfg = _base_cfg(target_min_trades=10, fee_rate=0.0004, slippage_bps=5)
    win_trade = {
        "result": "win",
        "profit_loss": 80,
        "direction": "long",
        "signal_strength": 90,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    loss_trade = {
        "result": "loss",
        "profit_loss": -100,
        "direction": "long",
        "signal_strength": 85,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    draw_trade = {
        "result": "draw",
        "profit_loss": 0,
        "direction": "long",
        "signal_strength": 80,
        "trap_risk": 10,
        "market_state": "trend_up",
    }
    trades = [win_trade] * 4 + [loss_trade] * 1 + [draw_trade] * 15
    summary = service._build_summary(
        cfg,
        trades,
        final_equity=cfg["initial_balance"] + 4 * 80 - 100,
        max_drawdown=0,
        skipped={
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 0,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 0,
            "ai_evaluated_count": 20,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 20,
            "candidate_signals_count": 20,
        },
        data_quality={"warnings": []},
    )

    assert summary["total_trades"] == 20
    assert summary["decided_trades"] == 5
    assert summary["target_win_rate_status"] == "insufficient_sample"

    quality_gate = summary["quality_gate"]
    checks = {check["id"]: check for check in quality_gate["checks"]}

    # Sample-size check must key off decided trades (5), not total (20), so
    # it no longer falsely reports a "complete"/"pass" sample.
    assert checks["sample_size"]["status"] == "fail"
    assert "5 decided trades" in checks["sample_size"]["message"]

    # Target-edge check must surface the insufficient decided sample instead
    # of a misleading "win rate below target" verdict.
    target_edge = checks["target_edge"]
    assert target_edge["status"] == "warning"
    assert "decided trades" in target_edge["message"]
    assert "below target" not in target_edge["message"]

    assert quality_gate["status"] == "fail"


def test_large_stake_fee_summary_matches_event_contract_pnl_formula():
    service = EventContractService()
    cfg = _base_cfg(
        initial_balance=100_000_000,
        stake_amount=1_000_000,
        win_payout_ratio=0.8,
        fee_rate=0.0004,
        target_min_trades=10,
    )
    win_pnl = (
        cfg["stake_amount"] * cfg["win_payout_ratio"]
        - cfg["stake_amount"] * cfg["fee_rate"]
    )
    loss_pnl = -cfg["stake_amount"] - cfg["stake_amount"] * cfg["fee_rate"]
    trades = [
        {
            "result": "win",
            "profit_loss": win_pnl,
            "direction": "long",
            "signal_strength": 90,
            "trap_risk": 10,
            "market_state": "trend_up",
        }
        for _ in range(11)
    ] + [
        {
            "result": "loss",
            "profit_loss": loss_pnl,
            "direction": "short",
            "signal_strength": 88,
            "trap_risk": 20,
            "market_state": "range",
        }
        for _ in range(3)
    ]
    expected_total_pnl = 11 * win_pnl + 3 * loss_pnl
    summary = service._build_summary(
        cfg,
        trades,
        final_equity=cfg["initial_balance"] + expected_total_pnl,
        max_drawdown=0,
        skipped={
            "fake_breakout_filtered_count": 0,
            "trap_filtered_count": 0,
            "edge_quality_filtered_count": 962,
            "no_trade_filtered_count": 0,
            "rule_prefiltered_count": 962,
            "ai_evaluated_count": 976,
            "llm_evaluated_count": 0,
            "ai_rejected_count": 0,
            "ai_skipped_cap_count": 0,
            "missing_expiry_count": 0,
            "expiry_lag_skipped_count": 0,
            "entry_delay_skipped_count": 0,
            "decision_bars_count": 1412,
            "candidate_signals_count": 14,
        },
        data_quality={"warnings": []},
    )

    assert summary["total_trades"] == 14
    assert summary["wins"] == 11
    assert summary["losses"] == 3
    assert summary["win_rate"] == 78.57
    assert summary["total_pnl"] == expected_total_pnl
    assert summary["final_equity"] == cfg["initial_balance"] + expected_total_pnl
    assert summary["profit_factor"] == round(abs(11 * win_pnl / (3 * loss_pnl)), 4)
    assert summary["expectancy"] == round(expected_total_pnl / 14, 4)
    assert summary["break_even_win_rate"] == 55.58
    assert summary["target_sample_met"] is True
    # Now expects False: CI lower bound (52.41%) is below breakeven (55.58%), so target_status
    # is "not_met" per new stricter semantics requiring CI lower bound >= breakeven.
    assert summary["target_win_rate_met"] is False
    assert summary["target_win_rate_status"] == "not_met"


class _InsertResult:
    def scalar_one(self):
        return 42


class _FakeDb:
    def __init__(self):
        self.calls = []
        self.committed = False

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return _InsertResult()

    def commit(self):
        self.committed = True


def test_persist_backtest_marks_partial_run_status():
    service = EventContractService()
    cfg = _base_cfg()
    cfg["start_time"] = datetime(2026, 6, 27, tzinfo=timezone.utc)
    cfg["end_time"] = datetime(2026, 6, 28, tzinfo=timezone.utc)
    summary = {
        "total_trades": 0,
        "win_rate": 0,
        "final_equity": 10_000,
        "partial": True,
    }
    db = _FakeDb()

    run_id = service._persist_backtest(db, cfg, summary, [], [])

    assert run_id == 42
    assert db.calls[0][1]["status"] == "partial"
    assert db.committed is True
