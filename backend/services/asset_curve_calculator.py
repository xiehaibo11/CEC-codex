"""
Asset Curve Calculator with SQL-level aggregation and caching.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import cast, func
from sqlalchemy.orm import Session, aliased
from sqlalchemy.types import Integer

from database.models import Account, AccountAssetSnapshot, BinanceAccountSnapshot
from database.snapshot_connection import SnapshotSessionLocal
from database.snapshot_models import HyperliquidAccountSnapshot
from services.asset_curve.points import (
    build_binance_snapshot_point,
    build_hyperliquid_snapshot_point,
    build_paper_initial_point,
    build_paper_snapshot_point,
    sort_curve_points,
)
from services.asset_curve.schemas import AssetCurvePoint, BucketedSnapshotRow
from services.asset_curve.timeframes import (
    HYPERLIQUID_TRADING_MODES,
    TIMEFRAME_BUCKET_MINUTES as TIMEFRAME_BUCKET_MINUTES,
    get_bucket_minutes,
    get_bucket_seconds,
    get_environment_filter,
    parse_date_filter,
    resolve_effective_environment,
)

logger = logging.getLogger(__name__)

# Simple in-process cache keyed by timeframe
_ASSET_CURVE_CACHE: Dict[str, Dict[str, object]] = {}
_CACHE_LOCK = threading.Lock()


def invalidate_asset_curve_cache() -> None:
    """Clear cached asset curve data (call when snapshots change)."""
    with _CACHE_LOCK:
        _ASSET_CURVE_CACHE.clear()
        logger.debug("Asset curve cache invalidated")


def _get_bucketed_snapshots(
    db: Session, bucket_minutes: int
) -> List[BucketedSnapshotRow]:
    """
    Query snapshots grouped by bucket using SQL aggregation.

    Returns tuples: (account_id, total_assets, cash, positions_value, event_time)
    """
    bucket_seconds = get_bucket_seconds(bucket_minutes)

    time_seconds = cast(func.extract("epoch", AccountAssetSnapshot.event_time), Integer)
    bucket_index_expr = cast(func.floor(time_seconds / bucket_seconds), Integer)

    bucket_subquery = (
        db.query(
            AccountAssetSnapshot.account_id.label("account_id"),
            bucket_index_expr.label("bucket_index"),
            func.max(AccountAssetSnapshot.event_time).label("latest_event_time"),
        )
        .group_by(AccountAssetSnapshot.account_id, bucket_index_expr)
        .subquery()
    )

    snapshot_alias = aliased(AccountAssetSnapshot)

    rows = (
        db.query(
            snapshot_alias.account_id,
            snapshot_alias.total_assets,
            snapshot_alias.cash,
            snapshot_alias.positions_value,
            snapshot_alias.event_time,
        )
        .join(
            bucket_subquery,
            (snapshot_alias.account_id == bucket_subquery.c.account_id)
            & (snapshot_alias.event_time == bucket_subquery.c.latest_event_time),
        )
        .order_by(snapshot_alias.event_time.asc(), snapshot_alias.account_id.asc())
        .all()
    )

    return rows


def get_all_asset_curves_data_new(
    db: Session,
    timeframe: str = "1h",
    trading_mode: str = "testnet",
    environment: Optional[str] = None,
    wallet_address: Optional[str] = None,
    account_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """
    Build asset curve data for all active accounts (or specific account) using cached SQL aggregation.
    Returns data from both Hyperliquid and Binance with 'exchange' field to distinguish.
    """
    bucket_minutes = get_bucket_minutes(timeframe)

    # Handle Hyperliquid mode with 5-minute bucketing
    if trading_mode in HYPERLIQUID_TRADING_MODES:
        effective_environment = resolve_effective_environment(trading_mode, environment)

        # Get Hyperliquid data
        hl_data = _build_hyperliquid_asset_curve(
            db,
            bucket_minutes,
            environment=effective_environment,
            wallet_address=wallet_address,
            account_id=account_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get Binance data
        binance_data = _build_binance_asset_curve(
            db,
            bucket_minutes,
            environment=effective_environment,
            account_id=account_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Merge and sort by timestamp
        combined = hl_data + binance_data
        combined.sort(key=lambda item: (item["timestamp"], item["account_id"]))
        return combined

    # For other non-paper modes, return empty data for now
    if trading_mode != "paper":
        return []

    current_max_snapshot_id: Optional[int] = db.query(
        func.max(AccountAssetSnapshot.id)
    ).scalar()
    cache_key = f"{timeframe}_{trading_mode}_{user_id or 'all'}"

    with _CACHE_LOCK:
        cache_entry = _ASSET_CURVE_CACHE.get(cache_key)
        if (
            cache_entry
            and cache_entry.get("last_snapshot_id") == current_max_snapshot_id
            and cache_entry.get("data") is not None
        ):
            return cache_entry["data"]  # type: ignore[return-value]

    # Get all active accounts for paper mode (filtered by show_on_dashboard)
    accounts = (
        db.query(Account)
        .filter(
            Account.is_active == "true",
            Account.show_on_dashboard == True,
            Account.is_deleted != True,
        )
        .all()
    )
    if user_id:
        accounts = [account for account in accounts if account.user_id == user_id]
    account_map = {account.id: account for account in accounts}
    rows = _get_bucketed_snapshots(db, bucket_minutes)

    result: List[AssetCurvePoint] = []
    seen_accounts = set()

    for account_id, total_assets, cash, positions_value, event_time in rows:
        account = account_map.get(account_id)
        if not account:
            continue

        seen_accounts.add(account_id)
        result.append(
            build_paper_snapshot_point(
                account_id,
                total_assets,
                cash,
                positions_value,
                event_time,
                account,
            )
        )

    # Ensure accounts without snapshots still appear with their initial capital
    now_utc = datetime.now(timezone.utc)
    for account in accounts:
        if account.id not in seen_accounts:
            result.append(build_paper_initial_point(account, now_utc))

    sort_curve_points(result)

    with _CACHE_LOCK:
        _ASSET_CURVE_CACHE[cache_key] = {
            "last_snapshot_id": current_max_snapshot_id,
            "data": result,
        }

    return result


def _build_hyperliquid_asset_curve(
    db: Session,
    bucket_minutes: int,
    environment: Optional[str] = None,
    wallet_address: Optional[str] = None,
    account_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Build asset curve for Hyperliquid accounts with 5-minute bucketing"""
    bucket_seconds = get_bucket_seconds(bucket_minutes)

    # Use snapshot database for Hyperliquid data
    snapshot_db = SnapshotSessionLocal()

    try:
        # Get all active AI accounts (or specific account)
        # Note: We don't filter by environment at Account level anymore (multi-wallet architecture)
        # Instead, we rely on HyperliquidAccountSnapshot filtering by environment
        account_query = db.query(Account).filter(
            Account.is_active == "true",
            Account.account_type == "AI",
            Account.show_on_dashboard == True,
            Account.is_deleted != True,
        )

        # Filter by specific account if provided
        if account_id:
            account_query = account_query.filter(Account.id == account_id)
        if user_id:
            account_query = account_query.filter(Account.user_id == user_id)

        accounts = account_query.all()

        if not accounts:
            return []

        account_map = {account.id: account for account in accounts}
        account_ids = list(account_map.keys())

        env_filter_value = get_environment_filter(environment)

        # Build bucket query for Hyperliquid snapshots
        time_seconds = cast(
            func.extract("epoch", HyperliquidAccountSnapshot.created_at), Integer
        )
        bucket_index_expr = cast(func.floor(time_seconds / bucket_seconds), Integer)

        bucket_query = snapshot_db.query(
            HyperliquidAccountSnapshot.account_id.label("account_id"),
            bucket_index_expr.label("bucket_index"),
            func.max(HyperliquidAccountSnapshot.created_at).label("latest_created_at"),
        )
        if env_filter_value:
            bucket_query = bucket_query.filter(
                HyperliquidAccountSnapshot.environment == env_filter_value
            )
        if wallet_address:
            bucket_query = bucket_query.filter(
                HyperliquidAccountSnapshot.wallet_address == wallet_address
            )
        bucket_query = bucket_query.filter(
            HyperliquidAccountSnapshot.account_id.in_(account_ids)
        )
        if account_id:
            bucket_query = bucket_query.filter(
                HyperliquidAccountSnapshot.account_id == account_id
            )

        # Apply time range filters
        start_dt = parse_date_filter(start_date, "start_date", logger)
        end_dt = parse_date_filter(end_date, "end_date", logger)
        if start_dt:
            bucket_query = bucket_query.filter(
                HyperliquidAccountSnapshot.created_at >= start_dt
            )
        if end_dt:
            bucket_query = bucket_query.filter(
                HyperliquidAccountSnapshot.created_at <= end_dt
            )

        bucket_subquery = bucket_query.group_by(
            HyperliquidAccountSnapshot.account_id,
            bucket_index_expr,
        ).subquery()

        snapshot_alias = aliased(HyperliquidAccountSnapshot)
        rows_query = snapshot_db.query(
            snapshot_alias.account_id,
            snapshot_alias.total_equity,
            snapshot_alias.created_at,
            snapshot_alias.wallet_address,
        ).join(
            bucket_subquery,
            (snapshot_alias.account_id == bucket_subquery.c.account_id)
            & (snapshot_alias.created_at == bucket_subquery.c.latest_created_at),
        )

        if env_filter_value:
            rows_query = rows_query.filter(
                snapshot_alias.environment == env_filter_value
            )
        if wallet_address:
            rows_query = rows_query.filter(
                snapshot_alias.wallet_address == wallet_address
            )
        rows_query = rows_query.filter(snapshot_alias.account_id.in_(account_ids))
        if account_id:
            rows_query = rows_query.filter(snapshot_alias.account_id == account_id)

        # Apply time range filters to rows query as well
        if start_dt:
            rows_query = rows_query.filter(snapshot_alias.created_at >= start_dt)
        if end_dt:
            rows_query = rows_query.filter(snapshot_alias.created_at <= end_dt)

        rows = rows_query.order_by(
            snapshot_alias.created_at.asc(),
            snapshot_alias.account_id.asc(),
        ).all()

        result: List[AssetCurvePoint] = []

        for account_id, total_equity, created_at, snap_wallet in rows:
            account = account_map.get(account_id)
            if not account:
                continue

            result.append(
                build_hyperliquid_snapshot_point(
                    account_id,
                    total_equity,
                    created_at,
                    snap_wallet,
                    account,
                )
            )

        # No longer fill missing accounts with initial_capital
        # Only return accounts that have actual snapshot data for this environment
        # If an account doesn't have a wallet configured for this environment, it won't appear

        sort_curve_points(result)
        return result

    finally:
        snapshot_db.close()


def _build_binance_asset_curve(
    db: Session,
    bucket_minutes: int,
    environment: Optional[str] = None,
    account_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Build asset curve for Binance accounts with bucketing"""
    bucket_seconds = get_bucket_seconds(bucket_minutes)

    # Get all active AI accounts
    account_query = db.query(Account).filter(
        Account.is_active == "true",
        Account.account_type == "AI",
        Account.show_on_dashboard == True,
        Account.is_deleted != True,
    )
    if account_id:
        account_query = account_query.filter(Account.id == account_id)
    if user_id:
        account_query = account_query.filter(Account.user_id == user_id)

    accounts = account_query.all()
    if not accounts:
        return []

    account_map = {account.id: account for account in accounts}
    account_ids = list(account_map.keys())

    env_filter = get_environment_filter(environment)

    # Build bucket query for Binance snapshots (stored in main DB)
    time_seconds = cast(
        func.extract("epoch", BinanceAccountSnapshot.snapshot_time), Integer
    )
    bucket_index_expr = cast(func.floor(time_seconds / bucket_seconds), Integer)

    bucket_query = db.query(
        BinanceAccountSnapshot.account_id.label("account_id"),
        bucket_index_expr.label("bucket_index"),
        func.max(BinanceAccountSnapshot.snapshot_time).label("latest_snapshot_time"),
    ).filter(BinanceAccountSnapshot.account_id.in_(account_ids))

    if env_filter:
        bucket_query = bucket_query.filter(
            BinanceAccountSnapshot.environment == env_filter
        )
    if account_id:
        bucket_query = bucket_query.filter(
            BinanceAccountSnapshot.account_id == account_id
        )

    # Apply time range filters
    start_dt = parse_date_filter(start_date, "start_date", logger)
    end_dt = parse_date_filter(end_date, "end_date", logger)
    if start_dt:
        bucket_query = bucket_query.filter(
            BinanceAccountSnapshot.snapshot_time >= start_dt
        )
    if end_dt:
        bucket_query = bucket_query.filter(
            BinanceAccountSnapshot.snapshot_time <= end_dt
        )

    bucket_subquery = bucket_query.group_by(
        BinanceAccountSnapshot.account_id,
        bucket_index_expr,
    ).subquery()

    snapshot_alias = aliased(BinanceAccountSnapshot)
    rows_query = db.query(
        snapshot_alias.account_id,
        snapshot_alias.total_margin_balance,
        snapshot_alias.available_balance,
        snapshot_alias.total_unrealized_profit,
        snapshot_alias.snapshot_time,
    ).join(
        bucket_subquery,
        (snapshot_alias.account_id == bucket_subquery.c.account_id)
        & (snapshot_alias.snapshot_time == bucket_subquery.c.latest_snapshot_time),
    )

    if env_filter:
        rows_query = rows_query.filter(snapshot_alias.environment == env_filter)
    if account_id:
        rows_query = rows_query.filter(snapshot_alias.account_id == account_id)

    # Apply time range filters to rows query
    if start_dt:
        rows_query = rows_query.filter(snapshot_alias.snapshot_time >= start_dt)
    if end_dt:
        rows_query = rows_query.filter(snapshot_alias.snapshot_time <= end_dt)

    rows = rows_query.order_by(
        snapshot_alias.snapshot_time.asc(),
        snapshot_alias.account_id.asc(),
    ).all()

    result: List[AssetCurvePoint] = []

    for acct_id, total_margin, available, unrealized_pnl, snapshot_time in rows:
        account = account_map.get(acct_id)
        if not account:
            continue

        result.append(
            build_binance_snapshot_point(
                acct_id,
                total_margin,
                available,
                unrealized_pnl,
                snapshot_time,
                account,
            )
        )

    sort_curve_points(result)
    return result
