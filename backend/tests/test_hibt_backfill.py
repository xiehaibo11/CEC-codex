"""HiBT K-line backfill service + endpoint wiring."""
import asyncio
from decimal import Decimal

from services.exchanges.base_adapter import UnifiedTrade
from services.exchanges.binance_constants import BINANCE_KLINE_INTERVALS

from api import system_routes
from services.exchanges import hibt_backfill


def _sample_candles():
    return [
        {"symbol": "btc_usdt", "open": "60000", "high": "60100", "low": "59900",
         "close": "60050", "volume": "12.5", "amount": "750000", "ts": 1724916860000},
        {"symbol": "btc_usdt", "open": "60050", "high": "60200", "low": "60000",
         "close": "60180", "volume": "8.1", "amount": "486000", "ts": 1724916920000},
    ]


def _sample_deals():
    return [
        {"symbol": "btc_usdt", "amount": "0.2", "price": "60000", "side": "buy", "time": 1724916860123},
        {"symbol": "btc_usdt", "amount": "0.1", "price": "60100", "side": "sell", "time": 1724916869123},
        {"symbol": "btc_usdt", "amount": "bad", "price": "60100", "side": "buy", "time": 1724916869123},
    ]


def test_shared_fetch_maps_and_caps_count(monkeypatch):
    from services import hibt_market_data

    captured = {}

    class FakeClient:
        def __init__(self, access_key="", secret_key="", **kwargs):
            pass

        def get_klines(self, symbol, period="1m", count=200, start=None, end=None, client=None):
            captured["args"] = (symbol, period, count, start, end)
            return _sample_candles()

    monkeypatch.setattr("services.hibt_trading_client.HibtTradingClient", FakeClient)

    klines = hibt_market_data.fetch_hibt_klines("BTC", "1m", count=9000)

    assert captured["args"] == ("BTC", "1m", 500, None, None)  # capped at HiBT's 500 row limit
    assert [k.timestamp for k in klines] == [1724916860, 1724916920]
    assert klines[0].exchange == "hibt"
    assert klines[0].symbol == "BTC"
    assert klines[0].quote_volume == Decimal("750000")


def test_shared_fetch_passes_hibt_historical_window(monkeypatch):
    from services import hibt_market_data

    captured = {}

    class FakeClient:
        def __init__(self, access_key="", secret_key="", **kwargs):
            pass

        def get_klines(self, symbol, period="1m", count=200, start=None, end=None, client=None):
            captured["args"] = (symbol, period, count, start, end)
            return _sample_candles()

    monkeypatch.setattr("services.hibt_trading_client.HibtTradingClient", FakeClient)

    hibt_market_data.fetch_hibt_klines("BTC", "1m", count=1000, start=1751673600000, end=1751703600000)

    assert captured["args"] == ("BTC", "1m", 500, 1751673600000, 1751703600000)


def test_shared_fetch_maps_hibt_deals_to_unified_trades(monkeypatch):
    from services import hibt_market_data

    captured = {}

    class FakeClient:
        def __init__(self, access_key="", secret_key="", **kwargs):
            pass

        def get_deals(self, symbol):
            captured["symbol"] = symbol
            return _sample_deals()

    monkeypatch.setattr("services.hibt_trading_client.HibtTradingClient", FakeClient)

    trades = hibt_market_data.fetch_hibt_deals("BTC")

    assert captured["symbol"] == "BTC"
    assert len(trades) == 2
    assert trades[0].exchange == "hibt"
    assert trades[0].symbol == "BTC"
    assert trades[0].timestamp == 1724916860123
    assert trades[0].side == "buy"
    assert trades[0].size == Decimal("0.2")
    assert trades[0].price == Decimal("60000")
    assert trades[1].side == "sell"


def test_backfill_market_flow_persists_hibt_deals(monkeypatch):
    saved = {}
    trades = [
        UnifiedTrade(
            exchange="hibt",
            symbol="BTC",
            timestamp=1724916860123,
            price=Decimal("60000"),
            size=Decimal("0.2"),
            side="buy",
        )
    ]

    monkeypatch.setattr(hibt_backfill, "fetch_hibt_deals", lambda s: trades)

    class FakePersistence:
        def __init__(self, db):
            pass

        def upsert_taker_trades_bulk(self, flow_trades, bucket_seconds=15):
            saved["call"] = (flow_trades, bucket_seconds)
            return {"upserted": len(flow_trades)}

    monkeypatch.setattr(hibt_backfill, "ExchangeDataPersistence", FakePersistence)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: _FakeSession())

    hibt_backfill.HibtBackfillService()._backfill_market_flow("BTC")

    assert saved["call"] == (trades, 15)


def test_backfill_market_flow_skips_persist_when_empty(monkeypatch):
    called = {"persist": False}
    monkeypatch.setattr(hibt_backfill, "fetch_hibt_deals", lambda s: [])

    class FakePersistence:
        def __init__(self, db):
            called["persist"] = True

        def upsert_taker_trades_bulk(self, *a, **k):
            called["persist"] = True

    monkeypatch.setattr(hibt_backfill, "ExchangeDataPersistence", FakePersistence)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: _FakeSession())

    hibt_backfill.HibtBackfillService()._backfill_market_flow("BTC")
    assert called["persist"] is False


def test_backfill_klines_persists_with_mainnet_environment(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        hibt_backfill, "fetch_hibt_klines", lambda s, p, count=500, start=None, end=None, client=None: _sample_candles()
    )

    class FakePersistence:
        def __init__(self, db):
            pass

        def save_klines(self, klines, environment="mainnet"):
            saved["call"] = (len(klines), environment)

        def upsert_taker_volume_proxy_from_klines_bulk(self, klines, bucket_seconds=60):
            saved["flow_call"] = (len(klines), bucket_seconds)

    monkeypatch.setattr(hibt_backfill, "ExchangeDataPersistence", FakePersistence)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: _FakeSession())

    hibt_backfill.HibtBackfillService()._backfill_klines("BTC", "1m", retention_days=0.001)

    assert saved["call"] == (2, "mainnet")


def test_hibt_backfill_uses_full_binance_period_skeleton():
    assert set(hibt_backfill.KLINE_PERIODS) | set(hibt_backfill.DERIVED_KLINE_PERIODS) == set(BINANCE_KLINE_INTERVALS)


def test_backfill_klines_pages_retention_window(monkeypatch):
    calls = []
    saved = []
    candles = _sample_candles()

    monkeypatch.setattr(hibt_backfill, "KLINE_BACKFILL_LIMIT", 2)
    monkeypatch.setattr(hibt_backfill.time, "time", lambda: 1_700_000_300)
    monkeypatch.setattr(hibt_backfill, "_PAGE_SPACING_SECONDS", 0)

    def fake_fetch(symbol, period, count=500, start=None, end=None, client=None):
        calls.append((symbol, period, count, start, end))
        return candles if len(calls) <= 3 else []

    monkeypatch.setattr(hibt_backfill, "fetch_hibt_klines", fake_fetch)

    class FakePersistence:
        def __init__(self, db):
            pass

        def save_klines(self, klines, environment="mainnet"):
            saved.append((len(klines), environment))

        def upsert_taker_volume_proxy_from_klines_bulk(self, klines, bucket_seconds=60):
            saved.append(("flow", len(klines), bucket_seconds))

    monkeypatch.setattr(hibt_backfill, "ExchangeDataPersistence", FakePersistence)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: _FakeSession())

    hibt_backfill.HibtBackfillService()._backfill_klines("BTC", "1m", retention_days=0.0035)

    assert calls == [
        ("BTC", "1m", 2, 1699999980000, 1700000100000),
        ("BTC", "1m", 2, 1700000100000, 1700000220000),
        ("BTC", "1m", 2, 1700000220000, 1700000280000),
    ]
    assert saved == [
        (2, "mainnet"), ("flow", 2, 60),
        (2, "mainnet"), ("flow", 2, 60),
        (2, "mainnet"), ("flow", 2, 60),
    ]


def test_backfill_klines_skips_persist_when_empty(monkeypatch):
    called = {"persist": False}
    monkeypatch.setattr(hibt_backfill, "fetch_hibt_klines", lambda s, p, count=500, start=None, end=None, client=None: [])

    class FakePersistence:
        def __init__(self, db):
            called["persist"] = True

        def save_klines(self, *a, **k):
            called["persist"] = True

    monkeypatch.setattr(hibt_backfill, "ExchangeDataPersistence", FakePersistence)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: _FakeSession())

    hibt_backfill.HibtBackfillService()._backfill_klines("BTC", "1m", retention_days=0.001)
    assert called["persist"] is False


def test_process_task_runs_all_pairs_and_marks_completed(monkeypatch):
    task = _FakeTask(symbols="BTC,ETH")
    session = _FakeSession(task=task)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: session)

    pairs = []
    derived = []
    flow_symbols = []
    service = hibt_backfill.HibtBackfillService()
    monkeypatch.setattr(service, "_backfill_market_flow", lambda s: flow_symbols.append(s))
    monkeypatch.setattr(service, "_backfill_klines", lambda s, p, d: pairs.append((s, p, d)))
    monkeypatch.setattr(service, "_derive_klines_from_existing_period", lambda s, p, sp, ps, d: derived.append((s, p, sp, d)))
    monkeypatch.setattr(hibt_backfill.asyncio, "sleep", _noop_async)

    asyncio.run(service._process_task(task.id))

    # 2 symbols x market-flow + 4 K-line periods
    assert flow_symbols == ["BTC", "ETH"]
    assert len(pairs) == 2 * len(hibt_backfill.KLINE_PERIODS)
    assert len(derived) == 2 * len(hibt_backfill.DERIVED_KLINE_PERIODS)
    assert all(days == 365 for _, _, days in pairs)
    assert all(days == 365 for _, _, _, days in derived)
    assert task.status == "completed"
    assert task.progress == 100


def test_process_task_marks_failed_on_error(monkeypatch):
    task = _FakeTask(symbols="BTC")
    session = _FakeSession(task=task)
    monkeypatch.setattr(hibt_backfill, "SessionLocal", lambda: session)

    service = hibt_backfill.HibtBackfillService()

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    # Make one progress commit raise once, so _process_task's outer except path
    # marks the task failed (and its own final commit still succeeds).
    monkeypatch.setattr(service, "_backfill_market_flow", lambda s: None)
    monkeypatch.setattr(service, "_backfill_klines", lambda s, p, d: None)
    monkeypatch.setattr(service, "_derive_klines_from_existing_period", lambda s, p, sp, ps, d: None)
    monkeypatch.setattr(hibt_backfill.asyncio, "sleep", _noop_async)
    session.fail_once_on_commit = 2

    asyncio.run(service._process_task(task.id))
    assert task.status == "failed"
    assert task.error_message


def test_system_router_exposes_hibt_backfill_paths():
    paths = {route.path for route in system_routes.router.routes}
    assert "/api/system/hibt/backfill" in paths
    assert "/api/system/hibt/backfill/status" in paths
    # existing paths still present
    assert "/api/system/binance/backfill" in paths


# --- lightweight fakes -------------------------------------------------------

async def _noop_async(*a, **k):
    return None


class _FakeTask:
    def __init__(self, symbols="BTC"):
        self.id = 1
        self.symbols = symbols
        self.status = "pending"
        self.progress = 0
        self.error_message = None


class _FakeQuery:
    def __init__(self, task):
        self._task = task

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._task


class _FakeSession:
    def __init__(self, task=None):
        self._task = task
        self.commits = 0
        self.fail_once_on_commit = None

    def query(self, *a, **k):
        return _FakeQuery(self._task)

    def commit(self):
        self.commits += 1
        if self.fail_once_on_commit == self.commits:
            self.fail_once_on_commit = None  # only fail this one commit
            raise RuntimeError("commit blew up")

    def close(self):
        pass
