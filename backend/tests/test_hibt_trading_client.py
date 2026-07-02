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
