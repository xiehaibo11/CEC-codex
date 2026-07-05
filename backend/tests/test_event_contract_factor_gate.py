"""Factor-combination entry gate (enable_factor_gate).

Gate rule: entry only when both "5m momentum" (ret5) and "VWAP deviation"
sit at/above their trailing-window quantile, computed from bars available
at decision time only. Evidence basis: 2026-07-05 run-2027 forensics.
"""
import pytest

from services.event_contract_service import EventContractService


def _bar(close, volume=10.0):
    return {
        "open": close,
        "high": close * 1.0005,
        "low": close * 0.9995,
        "close": close,
        "volume": volume,
        "timestamp": 0,
    }


def _history_flat_then_spike(n=120, base=100.0, spike_pct=0.02):
    """Flat tape with a strong final 5-bar ramp: ret5 and VWAP deviation both
    end far above any trailing quantile."""
    bars = [_bar(base) for _ in range(n - 5)]
    for i in range(5):
        bars.append(_bar(base * (1 + spike_pct * (i + 1) / 5)))
    return bars


def _history_flat(n=120, base=100.0):
    return [_bar(base) for _ in range(n)]


@pytest.fixture()
def svc():
    return EventContractService()


def _gate_cfg(svc, **overrides):
    raw = {
        "symbol": "BTC",
        "exchange": "binance",
        "period": "1m",
        "enable_factor_gate": True,
        **overrides,
    }
    return svc._normalize_config(raw, prediction=True)


def test_gate_disabled_returns_none(svc):
    cfg = svc._normalize_config(
        {"symbol": "BTC", "exchange": "binance", "period": "1m"}, prediction=True
    )
    history = _history_flat()
    features = svc._compute_features(history)
    assert svc._factor_gate_block_reason(history, features, cfg) is None


def test_insufficient_history_blocks(svc):
    cfg = _gate_cfg(svc)
    history = _history_flat(n=10)
    features = svc._compute_features(history)
    reason = svc._factor_gate_block_reason(history, features, cfg)
    assert reason is not None and "历史样本不足" in reason


def test_spike_passes_gate(svc):
    cfg = _gate_cfg(svc)
    history = _history_flat_then_spike()
    features = svc._compute_features(history)
    assert svc._factor_gate_block_reason(history, features, cfg) is None


def test_flat_tape_blocks(svc):
    """On a perfectly flat tape the current values equal the trailing median,
    so a p60 gate must block (values are not ABOVE the p60 threshold... equal
    values pass >=; use a decaying tape instead to force below-threshold)."""
    cfg = _gate_cfg(svc)
    base = 100.0
    bars = [_bar(base * (1 - 0.0001 * i)) for i in range(115)]
    for i in range(5):
        bars.append(_bar(bars[-1]["close"] * 0.999))  # accelerating decline
    features = svc._compute_features(bars)
    reason = svc._factor_gate_block_reason(bars, features, cfg)
    assert reason is not None and "因子门控" in reason


def test_gate_veto_forces_hold_in_analysis(svc):
    cfg = _gate_cfg(svc)
    bars = [_bar(100.0 * (1 - 0.0001 * i)) for i in range(115)]
    for i in range(5):
        bars.append(_bar(bars[-1]["close"] * 0.999))
    analysis = svc._analyze_snapshot(bars, cfg)
    reasons = " ".join(analysis.get("blocked_reasons") or [])
    assert "因子门控" in reasons


def test_fingerprint_stable_for_ungated_configs(svc):
    """Gate keys must NOT enter the normalized config when the gate is off —
    existing strategies' fingerprints (rolling-validation keys) depend on it."""
    plain = svc._normalize_config(
        {"symbol": "BTC", "exchange": "binance", "period": "1m"}, prediction=True
    )
    assert "enable_factor_gate" not in plain
    assert "factor_gate_quantile" not in plain

    gated = _gate_cfg(svc)
    assert gated["enable_factor_gate"] is True
    assert gated["factor_gate_quantile"] == 0.6
    assert gated["factor_gate_lookback"] == 60
    assert svc._strategy_fingerprint(gated) != svc._strategy_fingerprint(plain)
