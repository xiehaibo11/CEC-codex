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


def _patch_analysis_dependencies(monkeypatch, service, features):
    monkeypatch.setattr(service, "_compute_features", lambda history: features)
    monkeypatch.setattr(service, "_build_rule_decisions", lambda f, cfg: _all_long_decisions())
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
    assert any("75% edge gate" in reason for reason in analysis["blocked_reasons"])


def test_target_edge_gate_blocks_high_range_risk_before_trade(monkeypatch):
    service = EventContractService()
    cfg = _base_cfg(enable_edge_quality_gate=True, target_win_rate=75, max_trade_range_risk=45)
    _patch_analysis_dependencies(
        monkeypatch,
        service,
        _trade_ready_features(market_state="trend_up", range_risk=46),
    )

    analysis = service._analyze_snapshot([{"timestamp": 1, "close": 100}], cfg)

    assert analysis["allow_trade"] is False
    assert analysis["final_direction"] == "hold"
    assert any("strict range risk" in reason for reason in analysis["blocked_reasons"])


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

    small_sample = service._build_summary(cfg, [base_trade] * 9, 10_720, 0, skipped, {"warnings": []})
    enough_sample = service._build_summary(cfg, [base_trade] * 10, 10_800, 0, skipped, {"warnings": []})

    assert small_sample["win_rate"] == 100
    assert small_sample["target_sample_met"] is False
    assert small_sample["target_win_rate_met"] is False
    assert enough_sample["target_sample_met"] is True
    assert enough_sample["target_win_rate_met"] is True


def test_large_stake_fee_summary_matches_event_contract_pnl_formula():
    service = EventContractService()
    cfg = _base_cfg(
        initial_balance=100_000_000,
        stake_amount=1_000_000,
        win_payout_ratio=0.8,
        fee_rate=0.0004,
        target_min_trades=10,
    )
    win_pnl = cfg["stake_amount"] * cfg["win_payout_ratio"] - cfg["stake_amount"] * cfg["fee_rate"]
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
    assert summary["target_win_rate_met"] is True


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
