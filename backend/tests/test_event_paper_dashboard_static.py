"""Static checks for the production event-contract dashboard boundary."""

from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_backtest_form_exposes_only_production_expiries_and_risk_profile():
    panel = (ROOT / "frontend/app/components/backtest/BacktestConfigPanel.tsx").read_text()
    types = (ROOT / "frontend/app/components/backtest/types.ts").read_text()

    assert "[5, 10]" in panel
    assert "execution_mode" in panel
    assert "max 10/day" in panel or "最多10次" in (ROOT / "frontend/app/locales/zh.json").read_text()
    assert "PERIOD_OPTIONS = ['1m']" in types
    assert "range_boundary" not in panel
    assert "exhaustion_fade" not in panel


def test_arrow_dashboard_filters_to_enabled_trend_follow_traders_and_labels_paper():
    page = (ROOT / "frontend/app/components/event-arrow/EventArrowChartPage.tsx").read_text()
    api = (ROOT / "frontend/app/lib/eventContractApi.ts").read_text()
    locales = (ROOT / "frontend/app/locales/zh.json").read_text()

    assert "trader.enabled" in page
    assert "trader.policy_error" in page
    assert "signal_mode === 'trend_follow'" in page
    assert "[5, 10]" in page
    assert "paperSimulationNotice" in page
    assert "execution_capabilities" in api
    assert "Paper 价格模拟" in locales
