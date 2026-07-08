from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ai_review_routes_declared():
    text = (ROOT / "api" / "ai_review_routes.py").read_text()
    assert 'router = APIRouter(prefix="/api/ai-review", tags=["AI Review"])' in text
    assert "def list_review_runs" in text
    assert "def get_review_run" in text


def test_ai_review_router_registered_in_live_main():
    text = (ROOT / "main.py").read_text()
    assert "from api.ai_review_routes import router as ai_review_router" in text
    assert "app.include_router(ai_review_router)" in text


def test_ai_review_router_registered_in_split_router_module():
    text = (ROOT / "app_routers.py").read_text()
    assert "from api.ai_review_routes import router as ai_review_router" in text
    assert "app.include_router(ai_review_router)" in text
