from pathlib import Path


def test_terminal_dot_renderer_sets_stable_group_key():
    base = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/components/hyperliquid"
    )
    # The component may be a single file or have been split into a sibling
    # package directory; gather all of its sources so the invariant still holds.
    source = (base / "HyperliquidAssetChart.tsx").read_text()
    split_dir = base / "hyperliquid-asset-chart"
    if split_dir.is_dir():
        source += "\n".join(f.read_text() for f in sorted(split_dir.rglob("*.tsx")))

    assert "key={`terminal-dot-${account.key}-${index}`}" in source
