"""Self-consistency gate for scheduled LLM trading decisions.

Verified research (arXiv 2505.06120, 3-0 adversarial verification): multi-turn
LLM degradation is mostly a RELIABILITY problem - variance across runs - not a
loss of aptitude. Sampling the same decision prompt twice and only acting when
the direction agrees targets exactly that variance. Divergent samples mean the
model itself is unsure; the conservative resolution is hold.
"""
from __future__ import annotations

import pytest

from services.ai_decision_service.self_consistency import (
    configured_samples,
    reconcile_decision_samples,
)


def _entry(operation, symbol="BTC", **extra):
    entry = {
        "operation": operation,
        "symbol": symbol,
        "target_portion_of_balance": 0.2,
        "leverage": 3,
        "reason": f"{operation} thesis",
        "_prompt_snapshot": "p",
        "_reasoning_snapshot": "r",
    }
    entry.update(extra)
    return entry


class TestReconcile:
    def test_single_sample_passes_through(self):
        primary = [_entry("sell")]
        assert reconcile_decision_samples([primary]) == primary

    def test_agreeing_directions_kept_with_annotation(self):
        result = reconcile_decision_samples([[_entry("sell")], [_entry("sell")]])
        assert len(result) == 1
        assert result[0]["operation"] == "sell"
        assert result[0]["_self_consistency"]["agreed"] is True

    def test_divergent_directions_downgraded_to_hold(self):
        result = reconcile_decision_samples([[_entry("sell")], [_entry("buy")]])
        assert result[0]["operation"] == "hold"
        assert "自一致性" in result[0]["reason"]
        assert result[0]["_self_consistency"]["agreed"] is False
        # snapshots preserved for the decision log
        assert result[0]["_prompt_snapshot"] == "p"

    def test_symbol_missing_in_second_sample_counts_as_hold(self):
        # Sample 2 omitted BTC entirely -> implicit hold -> disagreement.
        result = reconcile_decision_samples([[_entry("buy")], [_entry("sell", symbol="ETH")]])
        btc = [e for e in result if e["symbol"] == "BTC"][0]
        assert btc["operation"] == "hold"

    def test_hold_in_primary_never_upgraded(self):
        # Second sample wanting to buy must not create a trade the primary
        # sample did not propose.
        result = reconcile_decision_samples([[_entry("hold")], [_entry("buy")]])
        assert result[0]["operation"] == "hold"

    def test_close_agreement_by_operation(self):
        result = reconcile_decision_samples([[_entry("close")], [_entry("close")]])
        assert result[0]["operation"] == "close"

    def test_close_vs_buy_divergence_holds(self):
        result = reconcile_decision_samples([[_entry("close")], [_entry("buy")]])
        assert result[0]["operation"] == "hold"

    def test_multi_symbol_reconciled_independently(self):
        primary = [_entry("sell", "BTC"), _entry("buy", "ETH")]
        second = [_entry("sell", "BTC"), _entry("hold", "ETH")]
        result = reconcile_decision_samples([primary, second])
        by_symbol = {e["symbol"]: e for e in result}
        assert by_symbol["BTC"]["operation"] == "sell"
        assert by_symbol["ETH"]["operation"] == "hold"


class TestConfig:
    def test_default_is_two_samples(self, monkeypatch):
        monkeypatch.delenv("AI_DECISION_SELF_CONSISTENCY_N", raising=False)
        assert configured_samples() == 2

    def test_env_override_and_clamp(self, monkeypatch):
        monkeypatch.setenv("AI_DECISION_SELF_CONSISTENCY_N", "3")
        assert configured_samples() == 3
        monkeypatch.setenv("AI_DECISION_SELF_CONSISTENCY_N", "1")
        assert configured_samples() == 1
        monkeypatch.setenv("AI_DECISION_SELF_CONSISTENCY_N", "99")
        assert configured_samples() == 3
        monkeypatch.setenv("AI_DECISION_SELF_CONSISTENCY_N", "garbage")
        assert configured_samples() == 2
