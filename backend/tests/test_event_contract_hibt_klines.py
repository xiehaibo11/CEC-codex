"""HIBT venue kline backfill for event-contract paper traders.

Verifies that a HIBT-platform trader's recent-window kline load pulls candles
from HIBT's own public endpoint (real venue settlement prices) and maps them
into the unified persistence format, and that the Binance path is untouched.
"""
from decimal import Decimal

from services.event_contract_service import event_contract_service


def _sample_hibt_candles():
    # HIBT /v2/market/candle rows: strings for prices, ms timestamp in `ts`.
    return [
        {"symbol": "btc_usdt", "open": "60000.5", "high": "60100", "low": "59900",
         "close": "60050", "volume": "12.5", "amount": "750000", "ts": 1724916860000},
        {"symbol": "btc_usdt", "open": "60050", "high": "60200", "low": "60000",
         "close": "60180", "volume": "8.1", "amount": "486000", "ts": 1724916920000},
    ]


def test_hibt_candles_map_to_unified_klines():
    mapped = event_contract_service._hibt_klines_to_unified(_sample_hibt_candles(), "BTC", "1m")

    assert [k.timestamp for k in mapped] == [1724916860, 1724916920]  # ms -> seconds
    first = mapped[0]
    assert first.exchange == "hibt"
    assert first.symbol == "BTC"
    assert first.interval == "1m"
    assert first.open_price == Decimal("60000.5")
    assert first.high_price == Decimal("60100")
    assert first.close_price == Decimal("60050")
    assert first.volume == Decimal("12.5")
    assert first.quote_volume == Decimal("750000")  # HIBT `amount` -> quote volume


def test_hibt_mapping_skips_malformed_rows():
    rows = _sample_hibt_candles() + [{"open": "x"}, "not-a-dict", {"ts": 1, "open": "1"}]
    mapped = event_contract_service._hibt_klines_to_unified(rows, "BTC", "1m")
    assert len(mapped) == 2  # only the two well-formed rows survive


def test_backfill_dispatch_routes_hibt_to_hibt_source(monkeypatch):
    calls = {"hibt": 0, "binance": 0}

    monkeypatch.setattr(
        event_contract_service,
        "_backfill_recent_hibt_klines",
        lambda *a, **k: calls.__setitem__("hibt", calls["hibt"] + 1),
    )
    monkeypatch.setattr(
        event_contract_service,
        "_backfill_recent_binance_klines",
        lambda *a, **k: calls.__setitem__("binance", calls["binance"] + 1),
    )

    event_contract_service._backfill_recent_klines(None, "hibt", "BTC", "1m", 200, "mainnet")
    assert calls == {"hibt": 1, "binance": 0}

    event_contract_service._backfill_recent_klines(None, "binance", "BTC", "1m", 200, "mainnet")
    assert calls == {"hibt": 1, "binance": 1}


def test_hibt_backfill_fetches_persists_and_is_nonfatal(monkeypatch):
    persisted = {}

    class FakeClient:
        def __init__(self, access_key="", secret_key="", **kwargs):
            pass

        def get_klines(self, symbol, period="1m", count=200, start=None, end=None):
            persisted["fetch"] = (symbol, period, count)
            return _sample_hibt_candles()

    class FakePersistence:
        def __init__(self, db):
            pass

        def save_klines(self, klines, environment="mainnet"):
            persisted["saved"] = (len(klines), environment)
            return {"upserted": len(klines)}

    monkeypatch.setattr("services.hibt_trading_client.HibtTradingClient", FakeClient)
    monkeypatch.setattr(
        "services.exchanges.data_persistence.ExchangeDataPersistence", FakePersistence
    )

    event_contract_service._backfill_recent_hibt_klines(None, "BTC", "1m", 200, "mainnet")

    assert persisted["fetch"] == ("BTC", "1m", 210)  # min_bars + 10 buffer, under the 500 cap
    assert persisted["saved"] == (2, "mainnet")

    # A raising client must not propagate out of the best-effort backfill.
    class BoomClient(FakeClient):
        def get_klines(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr("services.hibt_trading_client.HibtTradingClient", BoomClient)
    event_contract_service._backfill_recent_hibt_klines(None, "BTC", "1m", 200, "mainnet")
