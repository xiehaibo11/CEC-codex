from types import SimpleNamespace

from api import arena_routes


def test_live_positions_are_scoped_to_current_user(monkeypatch):
    calls = []

    def fake_hyperliquid_positions(db, account_id, environment, current_user_id=None):
        calls.append(("hyperliquid", account_id, environment, current_user_id))
        return {
            "generated_at": "2026-06-29T00:00:00",
            "trading_mode": environment,
            "accounts": [
                {"account_id": 10, "account_name": "Owned HL", "exchange": "hyperliquid"}
            ],
        }

    def fake_binance_positions(db, account_id, environment, current_user_id=None):
        calls.append(("binance", account_id, environment, current_user_id))
        return [
            {"account_id": 11, "account_name": "Owned Binance", "exchange": "binance"}
        ]

    monkeypatch.setattr(arena_routes, "_get_hyperliquid_positions", fake_hyperliquid_positions)
    monkeypatch.setattr(arena_routes, "_get_binance_positions", fake_binance_positions)

    result = arena_routes.get_positions_snapshot(
        account_id=None,
        trading_mode="testnet",
        db=object(),
        current_user=SimpleNamespace(id=42),
    )

    assert [account["account_id"] for account in result["accounts"]] == [10, 11]
    assert calls == [
        ("hyperliquid", None, "testnet", 42),
        ("binance", None, "testnet", 42),
    ]
