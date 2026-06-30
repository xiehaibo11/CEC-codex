from services.hyperliquid_market_data import HyperliquidClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_hyperliquid_client_initialization_is_lazy(monkeypatch):
    def fail_initialize_exchange(self):
        raise AssertionError("CCXT should not load during client construction")

    monkeypatch.setattr(HyperliquidClient, "_initialize_exchange", fail_initialize_exchange)

    client = HyperliquidClient("mainnet")

    assert client.exchange is None


def test_standard_symbol_last_price_uses_native_info_api(monkeypatch):
    client = HyperliquidClient.__new__(HyperliquidClient)
    client.environment = "mainnet"
    client.exchange = None

    def fail_initialize_exchange():
        raise AssertionError("CCXT should not load for native ticker data")

    client._initialize_exchange = fail_initialize_exchange

    def fake_post(url, json, timeout):
        assert url == "https://api.hyperliquid.xyz/info"
        assert json == {"type": "metaAndAssetCtxs"}
        assert timeout == 10
        return _FakeResponse(
            [
                {"universe": [{"name": "BTC"}]},
                [
                    {
                        "markPx": "60000.5",
                        "oraclePx": "60001",
                        "prevDayPx": "59000",
                        "dayNtlVlm": "12345",
                        "openInterest": "10",
                        "funding": "0.0001",
                    }
                ],
            ]
        )

    monkeypatch.setattr("requests.post", fake_post)

    assert client.get_last_price("BTC") == 60000.5


def test_standard_symbol_klines_use_native_candle_snapshot(monkeypatch):
    client = HyperliquidClient.__new__(HyperliquidClient)
    client.environment = "mainnet"
    client.exchange = None

    def fail_initialize_exchange():
        raise AssertionError("CCXT should not load for native kline data")

    client._initialize_exchange = fail_initialize_exchange

    def fake_post(url, json, timeout):
        assert url == "https://api.hyperliquid.xyz/info"
        assert json["type"] == "candleSnapshot"
        assert json["req"]["coin"] == "BTC"
        assert json["req"]["interval"] == "1m"
        assert timeout == 15
        return _FakeResponse(
            [
                {
                    "t": 1_700_000_000_000,
                    "o": "100.0",
                    "h": "110.0",
                    "l": "95.0",
                    "c": "105.0",
                    "v": "2.5",
                }
            ]
        )

    monkeypatch.setattr("requests.post", fake_post)

    klines = client.get_kline_data("BTC", "1m", count=1, persist=False)

    assert klines == [
        {
            "timestamp": 1_700_000_000,
            "datetime": "2023-11-14T22:13:20+00:00",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 105.0,
            "volume": 2.5,
            "amount": 262.5,
            "chg": 5.0,
            "percent": 5.0,
        }
    ]
