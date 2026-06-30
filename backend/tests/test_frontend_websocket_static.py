from pathlib import Path


def test_dev_websocket_url_targets_backend_port():
    main_source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/main.tsx"
    ).read_text()
    websocket_hook_source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/hooks/useTradingWebSocket.ts"
    ).read_text()

    assert "useTradingWebSocket" in main_source
    assert "import.meta.env.DEV" in websocket_hook_source
    assert "import.meta.env.VITE_BACKEND_PORT || '5611'" in websocket_hook_source
    assert "`${protocol}//${window.location.hostname}:${backendPort}/ws`" in websocket_hook_source
