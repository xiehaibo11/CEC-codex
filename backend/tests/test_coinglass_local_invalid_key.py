from types import SimpleNamespace


def test_subscription_reports_invalid_server_key(monkeypatch):
    from api import coinglass_routes

    monkeypatch.setattr(
        coinglass_routes,
        "_effective_key",
        lambda db, user: ("bad-key", "server", "bad****key"),
    )
    monkeypatch.setattr(coinglass_routes, "_user_key_record", lambda db, user_id: None)
    monkeypatch.setattr(coinglass_routes, "_server_coinglass_key", lambda: "bad-key")
    monkeypatch.setattr(
        coinglass_routes,
        "_coinglass_request",
        lambda *args, **kwargs: {
            "ok": False,
            "msg": "Invalid API key provided",
            "data": None,
            "fetched_at": 123,
        },
    )

    result = coinglass_routes.get_subscription(
        current_user=SimpleNamespace(id=1),
        db=object(),
    )

    assert result["configured"] is False
    assert result["server_key_configured"] is True
    assert result["key_source"] == "server"
    assert result["ok"] is False
    assert result["status"] == "invalid_key"
    assert result["reason"] == "Invalid API key provided"


def test_coinglass_view_uses_authenticated_api_request_and_rejects_unsuccessful_payload():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/components/coinglass/CoinGlassView.tsx"
    ).read_text()

    assert "import { apiRequest } from '@/lib/api'" in source
    assert "const endpoint = url.startsWith('/api/') ? url.slice(4) : url" in source
    assert "const response = await apiRequest(endpoint, init)" in source
    assert "payload && typeof payload === 'object' && 'ok' in payload && payload.ok === false" in source
    assert "throw new Error(displayError(detail))" in source
