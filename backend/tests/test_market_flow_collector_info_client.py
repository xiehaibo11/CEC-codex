from services import market_flow_collector
from services.market_flow_collector import MarketFlowCollector


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "tokens": [
                {"name": "USDC", "szDecimals": 8},
                {"name": "BTC", "szDecimals": 5},
            ],
            "universe": [
                {"name": "BTC/USDC", "tokens": [1, 0], "index": 1},
                {"name": "BROKEN/USDC", "tokens": [99, 0], "index": 2},
            ],
        }


def test_info_client_receives_sanitized_spot_meta(monkeypatch):
    created = []

    def fake_post(url, json, timeout):
        assert url == "https://api.hyperliquid.xyz/info"
        assert json == {"type": "spotMeta"}
        assert timeout == 10
        return _FakeResponse()

    class FakeInfo:
        def __init__(self, *, base_url, skip_ws, spot_meta, perp_dexs):
            assert base_url == "https://api.hyperliquid.xyz"
            assert skip_ws is False
            assert perp_dexs == ["", "xyz"]
            created.append(spot_meta)

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr(market_flow_collector, "Info", FakeInfo)

    collector = MarketFlowCollector()
    collector._create_info_client("https://api.hyperliquid.xyz")

    assert created[0]["universe"] == [{"name": "BTC/USDC", "tokens": [1, 0], "index": 1}]
