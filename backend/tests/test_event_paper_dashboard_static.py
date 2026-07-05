"""Static guard: the live event-contract paper trader dashboard card stays
wired into the analytics UI (spec module 3)."""
from pathlib import Path

FRONTEND_ANALYTICS = Path(__file__).resolve().parents[2] / "frontend" / "app" / "components" / "analytics"
FRONTEND_LIB = Path(__file__).resolve().parents[2] / "frontend" / "app" / "lib"


def _source(*paths: Path) -> str:
    """Load all TypeScript source from given directories."""
    lines: list[str] = []
    for p in paths:
        if not p.is_dir():
            continue
        for f in sorted(p.rglob("*.ts*")):
            lines.append(f.read_text(encoding="utf-8"))
    return "\n".join(lines)


def test_event_paper_trader_card_present():
    src = _source(FRONTEND_ANALYTICS)
    assert "EventPaperTraderCard" in src, "EventPaperTraderCard not found in analytics components"


def test_event_paper_trader_api_functions_wired():
    src = _source(FRONTEND_LIB)
    assert "getEventPaperTraders" in src, "getEventPaperTraders not found in lib"
    assert "getEventPaperTraderBets" in src, "getEventPaperTraderBets not found in lib"
    assert "getEventPaperTraderStats" in src, "getEventPaperTraderStats not found in lib"


def test_event_paper_trader_credibility_fields_present():
    src = _source(FRONTEND_ANALYTICS, FRONTEND_LIB)
    assert "break_even_win_rate" in src, "break_even_win_rate not found"
    assert "win_rate_ci_low" in src, "win_rate_ci_low not found"
