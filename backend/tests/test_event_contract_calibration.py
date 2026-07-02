"""Predicted expected_win_rate must be scored against realized outcomes."""
from services.event_contract.backtest_stats import calibration_report


def _trade(predicted, won):
    return {
        "result": "win" if won else "loss",
        "event_signal": {"expected_win_rate": predicted},
    }


def test_insufficient_sample():
    assert calibration_report([_trade(75, True)] * 10)["status"] == "insufficient_sample"


def test_perfect_calibration_bucket():
    trades = [_trade(80, i < 40) for i in range(50)]  # 80% predicted, 80% realized
    report = calibration_report(trades, min_samples=50)
    assert report["status"] == "ok"
    bucket = next(b for b in report["buckets"] if b["n"] == 50)
    assert bucket["actual_win_rate"] == 80.0
    assert abs(report["brier_score"] - (0.8 * 0.2)) < 0.01  # p(1-p) for perfect calibration
