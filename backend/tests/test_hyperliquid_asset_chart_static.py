from pathlib import Path


def test_terminal_dot_renderer_sets_stable_group_key():
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/components/hyperliquid/HyperliquidAssetChart.tsx"
    ).read_text()

    assert "key={`terminal-dot-${account.key}-${index}`}" in source
