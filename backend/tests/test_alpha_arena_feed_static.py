from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def test_expandable_feed_cards_do_not_wrap_nested_controls_in_native_buttons():
    source = (FRONTEND_ROOT / "app/components/portfolio/AlphaArenaFeed.tsx").read_text()

    assert 'role="button"' in source
    assert "onKeyDown={handleFeedCardKeyDown" in source
    assert (
        '<button\n'
        "                          type=\"button\"\n"
        "                          className=\"w-full text-left border border-border rounded bg-muted/30 p-4 space-y-2"
    ) not in source
    assert (
        '<button\n'
        "                        key={log.id}\n"
        "                        type=\"button\"\n"
        "                        className=\"w-full text-left border border-border rounded bg-muted/30 p-4 space-y-2"
    ) not in source


def test_vite_dev_proxy_defaults_to_local_backend_port():
    source = (FRONTEND_ROOT / "vite.config.ts").read_text()

    assert "const backendPort = parseInt(process.env.BACKEND_PORT || '5611')" in source
