from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_hibt_data_tab_uses_binance_collection_skeleton():
    """HiBT data collection must keep the same frontend skeleton as Binance."""
    src = _read("frontend/app/components/settings/SettingsPage.tsx")
    hibt_block = src.split('<TabsContent value="hibt-data"', 1)[1].split(
        '<TabsContent value="news-sources"', 1
    )[0]

    assert "klinePeriods={BINANCE_KLINE_PERIODS}" in hibt_block
    assert "settings.backfillDesc" in hibt_block
    assert "settings.hibtBackfillDesc" not in hibt_block


def test_exchange_data_tab_always_renders_full_card_when_stats_missing():
    """Empty venues should not fall back to a reduced no-data shell."""
    src = _read("frontend/app/components/settings/settings-page/ExchangeDataSettingsTab.tsx")

    assert "const stats = storageStats[exchange] ??" in src
    assert "settings.noData" not in src
    assert "currentStorage" in src
    assert "marketFlowCoverage" in src
    assert "klineCoverage" in src
