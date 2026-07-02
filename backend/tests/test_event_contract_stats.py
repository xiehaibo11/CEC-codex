"""Wilson CI, binomial significance and settlement sensitivity."""
from services.event_contract.backtest_stats import (
    binomial_p_value,
    settlement_sensitivity,
    wilson_interval,
)


def test_wilson_interval_known_value():
    lo, hi = wilson_interval(24, 30)
    assert 62.0 < lo < 64.0
    assert 90.0 < hi < 91.0


def test_wilson_empty_sample():
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_binomial_p_value_extremes():
    # 30/30 wins vs p0=0.5556 is overwhelming evidence
    assert binomial_p_value(30, 30, 0.5556) < 1e-6
    # 5/10 wins vs 0.5556 is not significant
    assert binomial_p_value(5, 10, 0.5556) > 0.05


def _trade(entry, expiry, direction="long"):
    result = "win" if (expiry > entry) == (direction == "long") and expiry != entry else ("draw" if expiry == entry else "loss")
    return {"entry_price": entry, "expiry_price": expiry, "direction": direction, "result": result}


def test_settlement_sensitivity_counts_flips():
    # 1bp winning margin: flips at 2bps shift; 100bp margin: never flips
    trades = [_trade(100.0, 100.01), _trade(100.0, 101.0)]
    report = settlement_sensitivity(trades)
    assert report["bps_2"] == 50.0
    assert report["bps_10"] == 50.0
    assert report["trades_evaluated"] == 2
