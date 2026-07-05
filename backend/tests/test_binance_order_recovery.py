"""Ambiguous-failure recovery in BinanceTradingOrdersMixin.place_order.

A gateway 5xx / transport error on POST /fapi/v1/order does not prove the
order was rejected — it may have reached the matching engine. place_order
must verify by client order ID before reporting failure, and must never
blindly re-submit.
"""
import pytest

from services.binance_trading_client import BinanceAPIError
from services.binance_trading_orders import BinanceTradingOrdersMixin


class _StubClient(BinanceTradingOrdersMixin):
    """Minimal host for the mixin: canned _request outcomes, no network."""

    broker_id = "TESTBRK"
    environment = "testnet"

    def __init__(self, post_exc, get_result=None, get_exc=None):
        self.post_exc = post_exc
        self.get_result = get_result
        self.get_exc = get_exc
        self.requests_seen = []

    def _to_binance_symbol(self, symbol):
        return f"{symbol}USDT"

    def _get_timestamp(self):
        return 1234567890

    def _get_precision(self, binance_symbol):
        return {"step_size": "0.001", "min_qty": 0.001, "tick_size": "0.1"}

    def _round_quantity(self, quantity, step_size):
        return quantity

    def _round_price(self, price, tick_size):
        return price

    def set_leverage(self, symbol, leverage):
        return {}

    def _request(self, method, endpoint, params=None, signed=False):
        self.requests_seen.append((method, endpoint, dict(params or {})))
        if method == "POST":
            raise self.post_exc
        if self.get_exc:
            raise self.get_exc
        return self.get_result


ORDER_ON_EXCHANGE = {
    "orderId": 42,
    "clientOrderId": "x-TESTBRK-1234567890",
    "status": "FILLED",
    "price": "0",
    "avgPrice": "62630.0",
    "executedQty": "0.01",
    "timeInForce": "GTC",
    "reduceOnly": False,
}


def test_502_with_order_found_recovers_instead_of_failing(monkeypatch):
    monkeypatch.setattr("services.binance_trading_orders.time.sleep", lambda s: None)
    client = _StubClient(
        post_exc=BinanceAPIError(502, "<html>502 Bad Gateway</html>", status_code=502),
        get_result=ORDER_ON_EXCHANGE,
    )
    result = client.place_order("BTC", "BUY", 0.01)
    assert result["order_id"] == 42
    assert result["status"] == "FILLED"
    # exactly one POST (no blind re-submit) and one verification GET
    posts = [r for r in client.requests_seen if r[0] == "POST" and r[1] == "/fapi/v1/order"]
    gets = [r for r in client.requests_seen if r[0] == "GET" and r[1] == "/fapi/v1/order"]
    assert len(posts) == 1
    assert len(gets) == 1
    assert gets[0][2]["origClientOrderId"] == "x-TESTBRK-1234567890"


def test_502_with_order_absent_reraises_original_error(monkeypatch):
    monkeypatch.setattr("services.binance_trading_orders.time.sleep", lambda s: None)
    original = BinanceAPIError(502, "<html>502 Bad Gateway</html>", status_code=502)
    client = _StubClient(
        post_exc=original,
        get_exc=BinanceAPIError(-2013, "Order does not exist", status_code=400),
    )
    with pytest.raises(BinanceAPIError) as exc_info:
        client.place_order("BTC", "BUY", 0.01)
    assert exc_info.value is original
    posts = [r for r in client.requests_seen if r[0] == "POST"]
    assert len(posts) == 1  # never re-submitted


def test_business_4xx_error_is_not_treated_as_ambiguous():
    original = BinanceAPIError(-2019, "Margin is insufficient", status_code=400)
    client = _StubClient(post_exc=original)
    with pytest.raises(BinanceAPIError) as exc_info:
        client.place_order("BTC", "BUY", 0.01)
    assert exc_info.value is original
    # no verification query for unambiguous rejections
    gets = [r for r in client.requests_seen if r[0] == "GET"]
    assert len(gets) == 0
