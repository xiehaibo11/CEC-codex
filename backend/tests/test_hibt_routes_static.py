from database.migration_manager import MIGRATIONS
from database.models import HibtWallet
from api.hibt_routes import router


def test_hibt_wallet_model_and_migration_registered():
    assert HibtWallet.__tablename__ == "hibt_wallets"
    assert "add_hibt_wallet_tables.py" in MIGRATIONS


def test_hibt_router_exposes_expected_paths():
    paths = {route.path for route in router.routes}
    assert "/api/hibt/accounts/{account_id}/setup" in paths
    assert "/api/hibt/accounts/{account_id}/config" in paths
    assert "/api/hibt/accounts/{account_id}/balance" in paths
    assert "/api/hibt/accounts/{account_id}/positions" in paths
    assert "/api/hibt/accounts/{account_id}/order" in paths
    assert "/api/hibt/symbols/watchlist" in paths


def test_hibt_router_exposes_completed_api_paths():
    paths = {route.path for route in router.routes}
    # Trading additions
    assert "/api/hibt/accounts/{account_id}/cancel-order" in paths
    assert "/api/hibt/accounts/{account_id}/close-all" in paths
    assert "/api/hibt/accounts/{account_id}/open-orders" in paths
    assert "/api/hibt/accounts/{account_id}/order-history" in paths
    # Account history additions
    assert "/api/hibt/accounts/{account_id}/trades" in paths
    assert "/api/hibt/accounts/{account_id}/balance-records" in paths
    assert "/api/hibt/accounts/{account_id}/liquidations" in paths
    # Public market-data additions
    assert "/api/hibt/klines/{symbol}" in paths
    assert "/api/hibt/depth/{symbol}" in paths
    assert "/api/hibt/deals/{symbol}" in paths
    assert "/api/hibt/funding-rate/{symbol}" in paths
    assert "/api/hibt/mark-price/{symbol}" in paths
