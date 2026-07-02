import pytest

from services.binance_testnet_order_probe import run_binance_testnet_order_probe


class FakeWallet:
    account_id = 7
    environment = "testnet"


class MainnetWallet:
    account_id = 7
    environment = "mainnet"


class FakeClient:
    base_url = "https://demo-fapi.binance.com"

    def __init__(self):
        self.calls = []

    def get_mark_price(self, symbol):
        self.calls.append(("get_mark_price", symbol))
        return 60000.0

    def place_order(self, **kwargs):
        self.calls.append(("place_order", kwargs))
        return {"order_id": 12345, "status": "NEW"}

    def get_order(self, **kwargs):
        self.calls.append(("get_order", kwargs))
        return {"orderId": 12345, "status": "NEW"}

    def cancel_order(self, **kwargs):
        self.calls.append(("cancel_order", kwargs))
        return {"orderId": 12345, "status": "CANCELED"}


def test_testnet_order_probe_places_limit_order_then_cancels():
    client = FakeClient()

    result = run_binance_testnet_order_probe(
        wallet=FakeWallet(),
        client=client,
        symbol="BTC",
        side="SELL",
        quantity=0.001,
        leverage=1,
        price_offset_pct=5,
    )

    assert result["success"] is True
    assert result["environment"] == "testnet"
    assert result["base_url"] == "https://demo-fapi.binance.com"
    assert result["order_id"] == 12345
    assert result["place_status"] == "NEW"
    assert result["query_status"] == "NEW"
    assert result["cancel_status"] == "CANCELED"
    assert result["limit_price"] == 63000.0
    assert client.calls[1] == (
        "place_order",
        {
            "symbol": "BTC",
            "side": "SELL",
            "quantity": 0.001,
            "order_type": "LIMIT",
            "price": 63000.0,
            "time_in_force": "GTC",
            "reduce_only": False,
            "leverage": 1,
        },
    )
    assert client.calls[-1] == ("cancel_order", {"symbol": "BTC", "order_id": 12345})


def test_testnet_order_probe_rejects_mainnet_wallet():
    with pytest.raises(ValueError, match="testnet"):
        run_binance_testnet_order_probe(
            wallet=MainnetWallet(),
            client=FakeClient(),
            symbol="BTC",
            side="BUY",
            quantity=0.001,
        )
