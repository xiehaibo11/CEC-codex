from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests
from fastapi import HTTPException

from config.settings import COINGLASS_API_BASE_URL
from services.api_rate_limiter import acquire_api_slot, record_api_response

from .catalog import _catalog_by_path
from .keys import _mask_key, _server_coinglass_key

logger = logging.getLogger(__name__)


def _coinglass_request(
    path: str,
    params: dict[str, Any],
    *,
    api_key: str | None = None,
    key_source: str = "server",
    key_masked: str | None = None,
) -> dict[str, Any]:
    api_key = (api_key or _server_coinglass_key()).strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="COINGLASS_API_KEY is not configured")

    if path != "/api/user/account/subscription" and path not in _catalog_by_path():
        raise HTTPException(status_code=404, detail="CoinGlass endpoint is not in the local documentation catalog")

    cleaned_params = {
        key: value
        for key, value in params.items()
        if value is not None and str(value).strip() != ""
    }
    url = f"{COINGLASS_API_BASE_URL.rstrip('/')}{path}"
    try:
        acquire_api_slot("coinglass", cost=float(os.getenv("COINGLASS_RATE_WEIGHT_DEFAULT", "1")))
        response = requests.get(
            url,
            headers={"CG-API-KEY": api_key, "accept": "application/json"},
            params=cleaned_params,
            timeout=15,
        )
        record_api_response("coinglass", response.headers)
    except requests.RequestException as exc:
        logger.warning("CoinGlass request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CoinGlass request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="CoinGlass returned a non-JSON response") from exc

    rate_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower().startswith("x-ratelimit") or key.lower() in {"retry-after"}
    }

    return {
        "ok": response.ok and str(payload.get("code", "0")) == "0",
        "status_code": response.status_code,
        "path": path,
        "params": cleaned_params,
        "payload": payload,
        "data": payload.get("data") if isinstance(payload, dict) else None,
        "msg": payload.get("msg") if isinstance(payload, dict) else None,
        "rate_limit": rate_headers,
        "key_source": key_source,
        "key_masked": key_masked or _mask_key(api_key),
        "fetched_at": int(time.time() * 1000),
    }
