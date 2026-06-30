from __future__ import annotations

import hashlib
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth_dependencies import get_current_user
from api.coinglass.catalog import (
    CURATED_DATASETS,
    INTERVAL_MINUTES,
    _catalog_by_id,
    _catalog_by_path,
    _interval_allowed,
    _merge_params,
    _normalize_plan,
    get_catalog_payload,
)
from api.coinglass.client import _coinglass_request
from api.coinglass.event_contract import (
    EVENT_CONTRACT_REQUIRED_METRICS,
    _cached_event_contract_capability,
    _coin_and_pair,
    _coinglass_exchange_name,
    _event_contract_required_plan,
    _store_event_contract_capability,
    event_contract_interval_blocked,
)
from api.coinglass.keys import (
    _effective_key,
    _mask_key,
    _server_coinglass_key,
    _upsert_user_key,
    _user_key_record,
)
from api.coinglass.schemas import CoinGlassKeyRequest
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/coinglass", tags=["coinglass"])


@router.get("/catalog")
def get_catalog():
    return get_catalog_payload()


@router.get("/subscription")
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key, key_source, key_masked = _effective_key(db, current_user)
    if not api_key:
        return {
            "configured": False,
            "user_key_configured": False,
            "server_key_configured": False,
            "key_source": "none",
            "key_masked": None,
            "level": None,
            "expired": None,
            "expire_time": None,
        }

    result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source=key_source,
        key_masked=key_masked,
    )
    data = result.get("data") or {}
    record = _user_key_record(db, current_user.id)
    if not result.get("ok"):
        return {
            "configured": False,
            "user_key_configured": record is not None,
            "server_key_configured": bool(_server_coinglass_key()),
            "key_source": key_source,
            "key_masked": key_masked,
            "ok": False,
            "status": "invalid_key",
            "reason": result.get("msg") or "CoinGlass API key validation failed",
            "level": None,
            "expired": None,
            "expire_time": None,
            "fetched_at": result["fetched_at"],
        }
    return {
        "configured": True,
        "user_key_configured": record is not None,
        "server_key_configured": bool(_server_coinglass_key()),
        "key_source": key_source,
        "key_masked": key_masked,
        "ok": result["ok"],
        "level": data.get("level"),
        "expired": data.get("expired"),
        "expire_time": data.get("expire_time"),
        "fetched_at": result["fetched_at"],
    }


@router.get("/event-contract-capability")
def get_event_contract_capability(
    symbol: str = "BTC",
    exchange: str = "Binance",
    period: str = "1m",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = str(period or "1m")
    if period not in INTERVAL_MINUTES:
        return {
            "available": False,
            "configured": False,
            "status": "unsupported_period",
            "reason": f"Unsupported CoinGlass interval for event-contract checks: {period}",
            "period": period,
            "metrics": [],
        }

    api_key, key_source, key_masked = _effective_key(db, current_user)
    if not api_key:
        return {
            "available": False,
            "configured": False,
            "status": "not_configured",
            "reason": "CoinGlass API key is not configured.",
            "period": period,
            "key_source": "none",
            "key_masked": None,
            "metrics": [],
        }

    cache_key = hashlib.sha1(
        f"{api_key}:{symbol}:{exchange}:{period}".encode("utf-8")
    ).hexdigest()
    cached = _cached_event_contract_capability(cache_key)
    if cached:
        return cached

    subscription_result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source=key_source,
        key_masked=key_masked,
    )
    subscription_data = subscription_result.get("data") or {}
    plan = _normalize_plan(subscription_data.get("level"))
    expired = bool(subscription_data.get("expired"))
    base_payload: dict[str, Any] = {
        "available": False,
        "configured": True,
        "period": period,
        "symbol": symbol,
        "exchange": _coinglass_exchange_name(exchange),
        "key_source": key_source,
        "key_masked": key_masked,
        "level": plan,
        "expired": expired,
        "expire_time": subscription_data.get("expire_time"),
        "required_plan": _event_contract_required_plan(period, plan),
        "fetched_at": int(time.time() * 1000),
    }

    if not subscription_result.get("ok"):
        base_payload.update(
            {
                "status": "subscription_check_failed",
                "reason": subscription_result.get("msg") or "CoinGlass subscription check failed.",
                "metrics": [],
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    if expired:
        base_payload.update(
            {
                "status": "expired",
                "reason": "CoinGlass subscription is expired.",
                "metrics": [],
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    coin, pair = _coin_and_pair(symbol)
    exchange_name = _coinglass_exchange_name(exchange)
    metrics = []
    for metric in EVENT_CONTRACT_REQUIRED_METRICS:
        params = metric["params"](coin, pair, exchange_name, period)
        result = _coinglass_request(
            metric["path"],
            params,
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        )
        metrics.append(
            {
                "metric": metric["metric"],
                "label": metric["label"],
                "path": metric["path"],
                "ok": bool(result.get("ok")),
                "status_code": result.get("status_code"),
                "code": (result.get("payload") or {}).get("code"),
                "message": result.get("msg") or (result.get("payload") or {}).get("message"),
            }
        )

    failed = [item for item in metrics if not item["ok"]]
    interval_blocked = event_contract_interval_blocked(failed)
    if failed:
        reason = (
            f"Current CoinGlass plan {plan or '-'} does not support {period} event-contract metrics."
            if interval_blocked
            else "; ".join(f"{item['label']}: {item.get('message') or item.get('code')}" for item in failed)
        )
        base_payload.update(
            {
                "available": False,
                "status": "plan_interval_unavailable" if interval_blocked else "metric_unavailable",
                "reason": reason,
                "metrics": metrics,
            }
        )
        return _store_event_contract_capability(cache_key, base_payload)

    base_payload.update(
        {
            "available": True,
            "status": "available",
            "reason": f"CoinGlass {period} event-contract metrics are available for plan {plan or '-'}",
            "metrics": metrics,
        }
    )
    return _store_event_contract_capability(cache_key, base_payload)


@router.post("/key")
def save_user_key(
    body: CoinGlassKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key = body.api_key.strip()
    result = _coinglass_request(
        "/api/user/account/subscription",
        {},
        api_key=api_key,
        key_source="user",
        key_masked=_mask_key(api_key),
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("msg") or "CoinGlass API key validation failed")

    data = result.get("data") or {}
    _upsert_user_key(db, current_user.id, api_key, data)
    db.commit()

    return {
        "configured": True,
        "user_key_configured": True,
        "server_key_configured": bool(_server_coinglass_key()),
        "key_source": "user",
        "key_masked": _mask_key(api_key),
        "ok": result["ok"],
        "level": data.get("level"),
        "expired": data.get("expired"),
        "expire_time": data.get("expire_time"),
        "fetched_at": result["fetched_at"],
    }


@router.delete("/key")
def delete_user_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _user_key_record(db, current_user.id)
    if record:
        db.delete(record)
        db.commit()
    return get_subscription(current_user=current_user, db=db)


@router.get("/dataset/{dataset_id}")
def get_dataset(
    dataset_id: str,
    symbol: str | None = None,
    exchange: str | None = None,
    exchange_list: str | None = None,
    interval: str | None = None,
    limit: int | None = Query(None, ge=1, le=1000),
    start_time: int | None = None,
    end_time: int | None = None,
    unit: str | None = None,
    range: str | None = Query(None),
    min_liquidation_amount: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = CURATED_DATASETS.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Unknown CoinGlass dataset")

    endpoint = _catalog_by_path().get(dataset["path"])
    allowed_names = {param["name"] for param in endpoint.get("params", [])} if endpoint else set(dataset["default_params"].keys())
    params = _merge_params(
        dataset["default_params"],
        {
            "symbol": symbol,
            "exchange": exchange,
            "exchange_list": exchange_list,
            "interval": interval,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "unit": unit,
            "range": range,
            "min_liquidation_amount": min_liquidation_amount,
        },
        allowed_names,
    )

    api_key, key_source, key_masked = _effective_key(db, current_user)
    result = _coinglass_request(dataset["path"], params, api_key=api_key, key_source=key_source, key_masked=key_masked)
    result["dataset"] = {"id": dataset_id, **dataset, "endpoint": endpoint}
    current_plan = None
    try:
        current_plan = _coinglass_request(
            "/api/user/account/subscription",
            {},
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        ).get("data", {}).get("level")
    except Exception:
        current_plan = None
    if endpoint:
        result["plan_check"] = {
            "current_plan": current_plan,
            "min_plan": endpoint.get("min_plan"),
            "interval_allowed": _interval_allowed(
                current_plan.title() if isinstance(current_plan, str) else current_plan,
                params.get("interval"),
                endpoint.get("interval_limit", {}),
            ),
        }
    return result


@router.get("/endpoint/{endpoint_id}")
def get_endpoint_data(
    endpoint_id: str,
    symbol: str | None = None,
    exchange: str | None = None,
    exchange_list: str | None = None,
    interval: str | None = None,
    limit: int | None = Query(None, ge=1, le=1000),
    start_time: int | None = None,
    end_time: int | None = None,
    unit: str | None = None,
    range: str | None = Query(None),
    min_liquidation_amount: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    endpoint = _catalog_by_id().get(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Unknown CoinGlass endpoint")

    allowed_names = {param["name"] for param in endpoint.get("params", [])}
    defaults = {
        param["name"]: param.get("default")
        for param in endpoint.get("params", [])
        if param.get("default") not in (None, "")
    }
    params = _merge_params(
        defaults,
        {
            "symbol": symbol,
            "exchange": exchange,
            "exchange_list": exchange_list,
            "interval": interval,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
            "unit": unit,
            "range": range,
            "min_liquidation_amount": min_liquidation_amount,
        },
        allowed_names,
    )

    missing = [name for name in endpoint.get("required_params", []) if not params.get(name)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required query params: {', '.join(missing)}")

    api_key, key_source, key_masked = _effective_key(db, current_user)
    result = _coinglass_request(endpoint["path"], params, api_key=api_key, key_source=key_source, key_masked=key_masked)
    result["endpoint"] = endpoint
    current_plan = None
    try:
        current_plan = _coinglass_request(
            "/api/user/account/subscription",
            {},
            api_key=api_key,
            key_source=key_source,
            key_masked=key_masked,
        ).get("data", {}).get("level")
    except Exception:
        current_plan = None
    result["plan_check"] = {
        "current_plan": current_plan,
        "min_plan": endpoint.get("min_plan"),
        "interval_allowed": _interval_allowed(
            current_plan.title() if isinstance(current_plan, str) else current_plan,
            params.get("interval"),
            endpoint.get("interval_limit", {}),
        ),
    }
    return result
