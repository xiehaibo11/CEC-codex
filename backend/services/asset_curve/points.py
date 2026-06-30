"""Pure response-point builders for asset curve data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from .schemas import AssetCurvePoint


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_utc_timestamp(dt: datetime) -> int:
    utc_dt = ensure_utc(dt)
    return int(utc_dt.timestamp())


def sort_curve_points(result: List[AssetCurvePoint]) -> None:
    result.sort(key=lambda item: (item["timestamp"], item["account_id"]))


def build_paper_snapshot_point(
    account_id: int,
    total_assets: float,
    cash: float,
    positions_value: float,
    event_time: datetime,
    account: Any,
) -> AssetCurvePoint:
    event_time_utc = ensure_utc(event_time)
    return {
        "timestamp": int(event_time_utc.timestamp()),
        "datetime_str": event_time_utc.isoformat(),
        "account_id": account_id,
        "user_id": account.user_id,
        "username": account.name,
        "total_assets": float(total_assets),
        "cash": float(cash),
        "positions_value": float(positions_value),
    }


def build_paper_initial_point(account: Any, now_utc: datetime) -> AssetCurvePoint:
    return {
        "timestamp": int(now_utc.timestamp()),
        "datetime_str": now_utc.isoformat(),
        "account_id": account.id,
        "user_id": account.user_id,
        "username": account.name,
        "total_assets": float(account.initial_capital),
        "cash": float(account.current_cash),
        "positions_value": 0.0,
    }


def build_hyperliquid_snapshot_point(
    account_id: int,
    total_equity: float,
    created_at: datetime,
    wallet_address: str | None,
    account: Any,
) -> AssetCurvePoint:
    return {
        "timestamp": to_utc_timestamp(created_at),
        "datetime_str": ensure_utc(created_at).strftime("%Y-%m-%d %H:%M:%S"),
        "account_id": account_id,
        "username": account.name,
        "user_id": account.user_id,
        "total_assets": float(total_equity),
        "cash": 0.0,
        "positions_value": float(total_equity),
        "wallet_address": wallet_address,
        "exchange": "hyperliquid",
    }


def build_binance_snapshot_point(
    account_id: int,
    total_margin: float,
    available: float,
    unrealized_pnl: float | None,
    snapshot_time: datetime,
    account: Any,
) -> AssetCurvePoint:
    return {
        "timestamp": to_utc_timestamp(snapshot_time),
        "datetime_str": ensure_utc(snapshot_time).strftime("%Y-%m-%d %H:%M:%S"),
        "account_id": account_id,
        "username": account.name,
        "user_id": account.user_id,
        "total_assets": float(total_margin),
        "cash": float(available),
        "positions_value": float(unrealized_pnl) if unrealized_pnl else 0.0,
        "wallet_address": None,
        "exchange": "binance",
    }
