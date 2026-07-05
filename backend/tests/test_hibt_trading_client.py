import hashlib
import hmac
import json

import pytest

from services.hibt_trading_client import HibtAPIError, HibtTradingClient


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params or {}, headers or {}, timeout))
        return self.response

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json or {}, headers or {}, timeout))
        return self.response


def test_hibt_signature_sorts_ascii_and_skips_empty_values():
    client = HibtTradingClient("access", "secret")

    payload = client._signature_payload({"symbol": "btc_usdt", "empty": "", "timestamp": 1724916869475})
    assert payload == "symbol=btc_usdt&timestamp=1724916869475"

    expected = hmac.new(b"secret", payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert client._sign({"timestamp": 1724916869475, "empty": "", "symbol": "btc_usdt"}) == expected


def test_hibt_signature_serializes_list_values_as_compact_json():
    client = HibtTradingClient("access", "secret")
    payload = client._signature_payload(
        {
            "timestamp": 1725599130897,
            "items": [
                {"symbol": "eth_usdt", "amount": "1", "side": 1},
                {"symbol": "btc_usdt", "amount": "0.01", "side": 2},
            ],
        }
    )

    assert payload.startswith("items=")
    assert " " not in payload
    assert "timestamp=1725599130897" in payload
    assert '"amount":"1"' in payload


def test_hibt_symbol_and_period_normalization():
    client = HibtTradingClient("access", "secret")

    assert client.to_hibt_symbol("BTC") == "btc_usdt"
    assert client.to_hibt_symbol("BTCUSDT") == "btc_usdt"
    assert client.to_hibt_symbol("eth_usdt") == "eth_usdt"
    assert client.to_period("1m") == "M1"
    assert client.to_period("4h") == "H4"

    with pytest.raises(ValueError):
        client.to_period("2m")


def test_hibt_testnet_requires_explicit_base_url(monkeypatch):
    monkeypatch.delenv("HIBT_TESTNET_FAPI_BASE_URL", raising=False)
    monkeypatch.delenv("HIBT_FAPI_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="HIBT_TESTNET_FAPI_BASE_URL"):
        HibtTradingClient("access", "secret", environment="testnet")

    monkeypatch.setenv("HIBT_TESTNET_FAPI_BASE_URL", "https://testnet.example/open-api")
    client = HibtTradingClient("access", "secret", environment="testnet")
    assert client.base_url == "https://testnet.example/open-api"


def test_signed_get_request_adds_timestamp_headers_and_signature():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"assets": []}}))
    client = HibtTradingClient("access-key", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    result = client._request("GET", "/v2/account/balance", signed=True)

    assert result == {"assets": []}
    method, url, params, headers, timeout = session.calls[0]
    assert method == "GET"
    assert url == "https://fapi.hibt0.com/open-api/v2/account/balance"
    assert params["timestamp"] == 1724916869475
    assert headers["X-ACCESS-KEY"] == "access-key"
    assert headers["X-TIMESTAMP"] == "1724916869475"
    expected_sig = hmac.new(b"secret", b"timestamp=1724916869475", hashlib.sha256).hexdigest()
    assert headers["X-SIGNATURE"] == expected_sig


def test_public_price_returns_price_from_list_response():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": [{"symbol": "btc_usdt", "price": "61234.5"}]}))
    client = HibtTradingClient("access", "secret", session=session)

    price = client.get_price("BTC")

    assert price == 61234.5
    method, url, params, headers, timeout = session.calls[0]
    assert method == "GET"
    assert params == {"symbol": "btc_usdt"}
    assert headers == {}


def test_private_order_open_uses_hibt_side_and_type_codes():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"orderID": "abc"}}))
    client = HibtTradingClient("access", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    result = client.place_order("BTC", side="BUY", quantity=0.01, order_type="MARKET", leverage=10)

    assert result["order_id"] == "abc"
    method, url, payload, headers, timeout = session.calls[0]
    assert method == "POST"
    assert url.endswith("/v2/order/open")
    assert payload["symbol"] == "btc_usdt"
    assert payload["side"] == 1
    assert payload["type"] == 2
    assert payload["amount"] == "0.01"
    assert payload["leverage"] == 10
    assert payload["timestamp"] == 1724916869475
    assert headers["X-ACCESS-KEY"] == "access"


def test_api_error_raises_structured_exception():
    session = FakeSession(FakeResponse({"code": 220008, "msg": "Signature verification failed", "data": None}))
    client = HibtTradingClient("access", "secret", session=session)

    with pytest.raises(HibtAPIError) as exc:
        client.get_balance()

    assert exc.value.code == 220008
    assert "Signature verification failed" in str(exc.value)


def test_public_market_endpoints_use_documented_paths():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": []}))
    client = HibtTradingClient("access", "secret", session=session)

    client.get_deals("BTC")
    client.get_mark_prices("BTC")
    client.get_funding_rate("BTC", start_time=1, end_time=2, limit=10)
    client.get_risk_limit("BTC")
    client.get_contracts()
    client.get_contract_specifications()
    client.get_order_book("BTC", depth=50)

    paths = [call[1].removeprefix(client.base_url) for call in session.calls]
    assert paths == [
        "/v2/market/deals",
        "/v2/market/index",
        "/v2/market/fundingRate",
        "/v2/market/riskLimit",
        "/v2/market/contracts",
        "/v2/market/contractSpecifications",
        "/v2/market/orderBook",
    ]
    funding_params = session.calls[2][2]
    assert funding_params == {"symbol": "btc_usdt", "startTime": 1, "endTime": 2, "limit": 10}
    assert session.calls[6][2] == {"symbol": "btc_usdt", "depth": 50}
    assert all(call[3] == {} for call in session.calls)  # public endpoints stay unsigned


def test_order_queries_are_signed_and_map_parameters():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"total": 1, "page": 1, "data": []}}))
    client = HibtTradingClient("access", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    result = client.get_order_history("BTC", start_time=1700000000, end_time=1700003600, page_index=2, page_size=50)

    assert result["total"] == 1
    method, url, params, headers, _ = session.calls[0]
    assert method == "GET"
    assert url.endswith("/v2/order/finished")
    assert params["symbol"] == "btc_usdt"
    assert params["startTime"] == 1700000000
    assert params["pageIndex"] == 2
    assert params["pageSize"] == 50
    assert headers["X-ACCESS-KEY"] == "access"

    client.get_open_orders(symbol="ETH", order_id="oid-1")
    _, url, params, headers, _ = session.calls[1]
    assert url.endswith("/v2/order/unFinish")
    assert params == {"symbol": "eth_usdt", "orderID": "oid-1", "timestamp": 1724916869475}
    assert "X-SIGNATURE" in headers


def test_batch_open_builds_items_from_friendly_orders():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"success": {}, "fail": {}}}))
    client = HibtTradingClient("access", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    client.place_batch_orders(
        [
            {"symbol": "BTC", "side": "BUY", "quantity": 0.01, "leverage": 5, "custom_id": "c1"},
            {"symbol": "ETH", "side": "SELL", "quantity": 1, "order_type": "LIMIT", "price": 2500, "custom_id": "c2"},
        ]
    )

    method, url, payload, headers, _ = session.calls[0]
    assert method == "POST"
    assert url.endswith("/v2/order/batchOpen")
    items = payload["items"]
    assert items[0]["symbol"] == "btc_usdt" and items[0]["side"] == 1 and items[0]["type"] == 2
    assert items[1]["symbol"] == "eth_usdt" and items[1]["side"] == 2 and items[1]["type"] == 1
    assert items[1]["price"] == "2500"
    assert "X-SIGNATURE" in headers


def test_batch_cancel_requires_exactly_one_id_list():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {}}))
    client = HibtTradingClient("access", "secret", session=session)

    with pytest.raises(ValueError):
        client.cancel_batch_orders("BTC")
    with pytest.raises(ValueError):
        client.cancel_batch_orders("BTC", order_ids=["1"], custom_ids=["2"])

    client.cancel_batch_orders("BTC", order_ids=["1", "2"])
    _, url, payload, _, _ = session.calls[0]
    assert url.endswith("/v2/order/batchCancel")
    assert payload["listOrderID"] == ["1", "2"]


def test_close_all_positions_returns_order_ids():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"listOrderID": ["a", "b"]}}))
    client = HibtTradingClient("access", "secret", session=session)

    order_ids = client.close_all_positions("BTC")

    assert order_ids == ["a", "b"]
    _, url, payload, _, _ = session.calls[0]
    assert url.endswith("/v2/order/closeAll")
    assert payload["symbol"] == "btc_usdt"


def test_conditional_order_uses_documented_field_casing():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": {"id": "e1"}}))
    client = HibtTradingClient("access", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    client.place_conditional_order(
        "BTC",
        side="BUY",
        quantity=0.5,
        trigger_price=60000,
        price=60100,
        leverage=3,
        trigger_type=2,
        take_profit_price=65000,
        stop_loss_price=58000,
        sp_sl_trigger_type=1,
    )

    _, url, payload, _, _ = session.calls[0]
    assert url.endswith("/v2/entrust/add")
    assert payload["triggerType"] == 2
    assert payload["triggerPrice"] == "60000"
    assert payload["IsSetSp"] is True and payload["spPrice"] == "65000"
    assert payload["IsSetSl"] is True and payload["slPrice"] == "58000"
    assert payload["spSlTriggerType"] == 1

    with pytest.raises(ValueError):
        client.cancel_conditional_order("BTC")


def test_account_history_endpoints_map_parameters():
    session = FakeSession(FakeResponse({"code": 0, "msg": "success", "data": []}))
    client = HibtTradingClient("access", "secret", session=session)
    client._get_timestamp = lambda: 1724916869475

    client.get_trade_history("BTC", start_time=1700000000, end_time=1700003600, limit=100)
    client.get_balance_records(symbol="BTC", event=9, limit=50)
    client.get_forced_liquidations(action=4)

    _, url, params, _, _ = session.calls[0]
    assert url.endswith("/v2/account/order")
    assert params["startTime"] == 1700000000 and params["limit"] == 100

    _, url, params, _, _ = session.calls[1]
    assert url.endswith("/v2/account/balanceRecord")
    assert params["event"] == 9 and params["symbol"] == "btc_usdt"

    _, url, params, _, _ = session.calls[2]
    assert url.endswith("/v2/account/orderForced")
    assert params["action"] == 4
