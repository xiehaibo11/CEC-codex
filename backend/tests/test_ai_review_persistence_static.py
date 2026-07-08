from pathlib import Path

from database import migration_manager


ROOT = Path(__file__).resolve().parents[1]


def test_ai_review_migration_registered():
    assert "add_ai_review_tables.py" in migration_manager.MIGRATIONS


def test_ai_review_models_declared():
    text = (ROOT / "database" / "models" / "trading.py").read_text()
    assert "class AIReviewRun" in text
    assert "class AIReviewAgentReport" in text
    assert "review_run_id" in text
    assert "review_verdict" in text
    assert "review_blocked_reason" in text


def test_save_ai_decision_persists_review_fields():
    text = (ROOT / "services" / "ai_decision_service" / "persistence.py").read_text()
    assert 'review_run_id=decision.get("review_run_id")' in text
    assert 'review_verdict=decision.get("review_verdict")' in text
    assert 'review_blocked_reason=decision.get("review_blocked_reason")' in text
