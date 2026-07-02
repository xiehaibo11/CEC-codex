"""Static guards: platform presets + credibility card stay wired into the UI."""
from pathlib import Path

FRONTEND_BACKTEST = Path(__file__).resolve().parents[2] / "frontend" / "app" / "components" / "backtest"


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(FRONTEND_BACKTEST.rglob("*.ts*")))


def test_platform_selector_present():
    src = _source()
    assert "binance_event" in src
    assert "PLATFORM_FORM_PRESETS" in src


def test_credibility_card_wired():
    src = _source()
    assert "CredibilityCard" in src
    assert "win_rate_ci_low" in src
    assert "createEventContractHoldoutTask" in src


def test_non_overlapping_toggle_present():
    assert "non_overlapping_only" in _source()
