"""HiBT market-flow collection wiring."""
from decimal import Decimal
from pathlib import Path

from services.exchanges.base_adapter import UnifiedKline, UnifiedTrade
from services.exchanges import hibt_collector

ROOT = Path(__file__).resolve().parents[2]


def _sample_trade():
    return UnifiedTrade(
        exchange="hibt",
        symbol="BTC",
        timestamp=1724916860123,
        price=Decimal("60000"),
        size=Decimal("0.2"),
        side="buy",
    )


def test_hibt_collector_polls_deals_into_market_flow_storage(monkeypatch):
    saved = {}
    monkeypatch.setattr(hibt_collector, "fetch_hibt_deals", lambda symbol: [_sample_trade()])
    monkeypatch.setattr(hibt_collector, "SessionLocal", lambda: _FakeSession())

    class FakePersistence:
        def __init__(self, db):
            pass

        def upsert_taker_trades_bulk(self, trades, bucket_seconds=15):
            saved["call"] = (trades, bucket_seconds)
            return {"upserted": len(trades)}

    monkeypatch.setattr(hibt_collector, "ExchangeDataPersistence", FakePersistence)

    collector = hibt_collector.HibtCollector()
    collector.symbols = ["BTC"]
    collector._collect_deals()

    assert saved["call"] == ([_sample_trade()], 15)


def test_startup_starts_and_stops_hibt_market_flow_collector():
    src = (ROOT / "backend/services/startup.py").read_text(encoding="utf-8")
    assert "services.exchanges.hibt_collector" in src
    assert "hibt_collector.start" in src
    assert "hibt_collector.stop" in src


class _FakeSession:
    def close(self):
        pass


def test_taker_trade_bulk_upsert_aggregates_hibt_deals_by_bucket():
    from services.exchanges.data_persistence import ExchangeDataPersistence

    db = _CapturingSession()
    trades = [
        UnifiedTrade(
            exchange="hibt",
            symbol="BTC",
            timestamp=1724916860123,
            price=Decimal("60000"),
            size=Decimal("0.2"),
            side="buy",
        ),
        UnifiedTrade(
            exchange="hibt",
            symbol="BTC",
            timestamp=1724916869123,
            price=Decimal("60100"),
            size=Decimal("0.1"),
            side="sell",
        ),
    ]

    result = ExchangeDataPersistence(db).upsert_taker_trades_bulk(trades, bucket_seconds=15)

    assert result == {"upserted": 1}
    assert db.committed is True
    assert len(db.rows) == 1
    row = db.rows[0]
    assert row["exchange"] == "hibt"
    assert row["symbol"] == "BTC"
    assert row["timestamp"] == 1724916855000
    assert row["taker_buy_volume"] == Decimal("0.2")
    assert row["taker_sell_volume"] == Decimal("0.1")
    assert row["taker_buy_notional"] == Decimal("12000.0")
    assert row["taker_sell_notional"] == Decimal("6010.0")
    assert row["taker_buy_count"] == 1
    assert row["taker_sell_count"] == 1


def test_taker_proxy_from_klines_splits_historical_flow_neutrally():
    from services.exchanges.data_persistence import ExchangeDataPersistence

    db = _CapturingSession()
    klines = [
        UnifiedKline(
            exchange="hibt",
            symbol="BTC",
            interval="1m",
            timestamp=1724916860,
            open_price=Decimal("60000"),
            high_price=Decimal("60100"),
            low_price=Decimal("59900"),
            close_price=Decimal("60050"),
            volume=Decimal("0.2"),
            quote_volume=Decimal("12010"),
        )
    ]

    result = ExchangeDataPersistence(db).upsert_taker_volume_proxy_from_klines_bulk(klines)

    assert result == {"upserted": 1}
    row = db.rows[0]
    assert row["exchange"] == "hibt"
    assert row["timestamp"] == 1724916840000
    assert row["taker_buy_volume"] == Decimal("0.1")
    assert row["taker_sell_volume"] == Decimal("0.1")
    assert row["taker_buy_notional"] == Decimal("6005")
    assert row["taker_sell_notional"] == Decimal("6005")


class _CapturingSession:
    def __init__(self):
        self.rows = []
        self.committed = False

    def execute(self, stmt, rows):
        self.rows = rows

    def commit(self):
        self.committed = True
