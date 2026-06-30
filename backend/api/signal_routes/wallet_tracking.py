"""CoinGlass wallet tracking status endpoints and helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth_dependencies import get_current_user
from api.coinglass_routes import _coinglass_request, _effective_key, _normalize_plan

from ._base import (
    COINGLASS_WALLET_TRACKING_ENDPOINTS,
    _count_active_wallet_pools,
    get_db,
    router,
)


def _coinglass_timestamp_to_iso(timestamp_ms: Any) -> str | None:
    try:
        value = int(timestamp_ms)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None).isoformat()


def _coinglass_wallet_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        rows = data.get("list")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def _coinglass_wallet_addresses(rows: list[dict[str, Any]]) -> list[str]:
    addresses: set[str] = set()
    for row in rows:
        address = row.get("user") or row.get("address") or row.get("user_address")
        if isinstance(address, str) and address.strip():
            addresses.add(address.strip().lower())
    return sorted(addresses)


def _latest_coinglass_event_time(rows: list[dict[str, Any]]) -> str | None:
    latest_ms = 0
    for row in rows:
        for key in ("create_time", "update_time"):
            try:
                latest_ms = max(latest_ms, int(row.get(key) or 0))
            except (TypeError, ValueError):
                continue
    return _coinglass_timestamp_to_iso(latest_ms)


def _coinglass_wallet_tracking_status(db: Session, current_user) -> dict[str, Any]:
    active_wallet_pool_count = _count_active_wallet_pools(db)
    api_key, key_source, key_masked = _effective_key(db, current_user)
    if not api_key:
        return {
            "enabled": False,
            "configured": False,
            "source": "coinglass",
            "status": "not_configured",
            "tier": None,
            "synced_addresses": [],
            "last_connected_at": None,
            "last_message_at": None,
            "last_event_at": None,
            "last_error": "CoinGlass API key is not configured",
            "active_wallet_pool_count": active_wallet_pool_count,
            "token_synced_at": None,
            "key_source": "none",
            "key_masked": None,
            "data_sources": [],
        }

    fetched_at = datetime.utcnow().isoformat()
    subscription_level = None
    subscription_expired = None
    try:
        subscription = _coinglass_request(
            "/api/user/account/subscription",
            {},
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        )
        subscription_data = subscription.get("data") or {}
        subscription_level = _normalize_plan(subscription_data.get("level"))
        subscription_expired = subscription_data.get("expired")
    except HTTPException:
        subscription_level = None
        subscription_expired = None

    addresses: set[str] = set()
    source_statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    last_event_at: str | None = None

    for source_id, path, params in COINGLASS_WALLET_TRACKING_ENDPOINTS:
        try:
            result = _coinglass_request(
                path,
                params,
                api_key=api_key,
                key_source=key_source,
                key_masked=key_masked,
            )
        except HTTPException as exc:
            detail = str(exc.detail)
            errors.append(f"{source_id}: {detail}")
            source_statuses.append({"id": source_id, "path": path, "ok": False, "message": detail})
            continue

        rows = _coinglass_wallet_rows(result.get("data"))
        addresses.update(_coinglass_wallet_addresses(rows))
        event_time = _latest_coinglass_event_time(rows)
        if event_time and (last_event_at is None or event_time > last_event_at):
            last_event_at = event_time
        source_statuses.append(
            {
                "id": source_id,
                "path": path,
                "ok": bool(result.get("ok")),
                "message": result.get("msg"),
                "row_count": len(rows),
            }
        )
        if not result.get("ok"):
            errors.append(f"{source_id}: {result.get('msg') or 'CoinGlass request failed'}")

    any_source_ok = any(item.get("ok") for item in source_statuses)
    return {
        "enabled": True,
        "configured": True,
        "source": "coinglass",
        "status": "connected" if any_source_ok else "error",
        "tier": subscription_level,
        "expired": subscription_expired,
        "synced_addresses": sorted(addresses),
        "last_connected_at": fetched_at if any_source_ok else None,
        "last_message_at": fetched_at if any_source_ok else None,
        "last_event_at": last_event_at,
        "last_error": "; ".join(errors) if errors and not any_source_ok else None,
        "active_wallet_pool_count": active_wallet_pool_count,
        "token_synced_at": None,
        "key_source": key_source,
        "key_masked": key_masked,
        "data_sources": source_statuses,
    }


class WalletTrackingRuntimeRequest(BaseModel):
    enabled: bool
    access_token: Optional[str] = None


class WalletTrackingTokenRequest(BaseModel):
    access_token: str


@router.get("/wallet-tracking/status")
def get_wallet_tracking_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get CoinGlass wallet tracking status and currently available wallet addresses."""
    return _coinglass_wallet_tracking_status(db, current_user)


@router.put("/wallet-tracking/runtime")
async def update_wallet_tracking_runtime(
    payload: WalletTrackingRuntimeRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compatibility endpoint; CoinGlass wallet tracking is controlled by CoinGlass key availability."""
    return _coinglass_wallet_tracking_status(db, current_user)


@router.post("/wallet-tracking/token")
async def sync_wallet_tracking_token(payload: WalletTrackingTokenRequest):
    """Compatibility endpoint retained for older clients; CoinGlass does not use HAA access tokens."""
    return {"success": True, "source": "coinglass"}


@router.delete("/wallet-tracking/token")
async def clear_wallet_tracking_token():
    """Compatibility endpoint retained for older clients; CoinGlass does not use HAA access tokens."""
    return {"success": True, "source": "coinglass"}
