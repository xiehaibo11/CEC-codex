"""Static guard: the live event-contract paper trader dashboard card stays
wired into the portfolio UI (spec module 3)."""
from pathlib import Path

FRONTEND_PORTFOLIO = Path(__file__).resolve().parents[2] / "frontend" / "app" / "components" / "portfolio"


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(FRONTEND_PORTFOLIO.rglob("*.ts*")))


def test_event_paper_trader_card_present():
    src = _source()
    assert "EventPaperTraderCard" in src


def test_event_paper_trader_api_functions_wired():
    src = _source()
    assert "getEventPaperTraders" in src
    assert "getEventPaperTraderBets" in src
    assert "getEventPaperTraderStats" in src


def test_event_paper_trader_credibility_fields_present():
    src = _source()
    assert "break_even_win_rate" in src
    assert "win_rate_ci_low" in src
