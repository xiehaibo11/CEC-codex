"""HiBT perpetual futures REST client.

The official HiBT perpetual docs use ``https://fapi.hibt0.com/open-api`` as
REST base URL. Private endpoints require ``X-ACCESS-KEY``, ``X-SIGNATURE`` and
``X-TIMESTAMP`` headers, where the signature is HMAC-SHA256 over non-empty
request parameters sorted by ASCII key order.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, Mapping, Optional

import requests

logger = logging.getLogger(__name__)


class HibtAPIError(Exception):
    """Structured HiBT REST API error."""

    def __init__(self, code: Any, message: str, status_code: Optional[int] = None, endpoint: Optional[str] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(f"HiBT API Error {code}: {message}")


class HibtTradingClient:
    """Small HiBT perpetual futures REST client used by routes and trading UI."""

    MAINNET_BASE_URL = "https://fapi.hibt0.com/open-api"
    DEFAULT_TIMEOUT = 10
    PERIOD_MAP = {
        "1m": "M1",
        "5m": "M5",
        "15m": "M15",
        "30m": "M30",
        "1h": "H1",
        "2h": "H2",
        "4h": "H4",
        "6h": "H6",
        "12h": "H12",
        "1d": "D1",
        "1w": "W1",
    }

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        environment: str = "mainnet",
        session: Any | None = None,
        base_url: str | None = None,
    ):
        if environment not in {"mainnet", "testnet"}:
            raise ValueError(f"Invalid HiBT environment: {environment!r}. Must be 'mainnet' or 'testnet'.")
        self.access_key = access_key
        self.secret_key = secret_key
        self.environment = environment
        self.base_url = (base_url or self._default_base_url(environment)).rstrip("/")
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update({"Content-Type": "application/json"})
        logger.info("[HiBT] Client initialized for %s", environment)

    @classmethod
    def _default_base_url(cls, environment: str) -> str:
        if environment == "testnet":
            testnet_base_url = os.environ.get("HIBT_TESTNET_FAPI_BASE_URL")
            if not testnet_base_url:
                raise ValueError(
                    "HiBT testnet base URL is not configured. "
                    "Set HIBT_TESTNET_FAPI_BASE_URL before using the HiBT testnet environment."
                )
            return testnet_base_url
        return os.environ.get("HIBT_FAPI_BASE_URL") or cls.MAINNET_BASE_URL

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    def _normalize_signature_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._normalize_signature_value(value[key])
                for key in sorted(value)
                if value[key] not in (None, "")
            }
        if isinstance(value, list):
            return [self._normalize_signature_value(item) for item in value]
        return value

    def _signature_payload(self, params: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for key in sorted(params):
            value = params[key]
            if value in (None, ""):
                continue
            value = self._normalize_signature_value(value)
            if isinstance(value, (list, dict)):
                encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            else:
                encoded = str(value)
            parts.append(f"{key}={encoded}")
        return "&".join(parts)

    def _sign(self, params: Mapping[str, Any]) -> str:
        payload = self._signature_payload(params)
        return hmac.new(self.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _headers_for(self, params: Mapping[str, Any], signed: bool) -> Dict[str, str]:
        if not signed:
            return {}
        timestamp = str(params.get("timestamp", ""))
        return {
            "X-ACCESS-KEY": self.access_key,
            "X-SIGNATURE": self._sign(params),
            "X-TIMESTAMP": timestamp,
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Any:
        request_params = dict(params or {})
        if signed and "timestamp" not in request_params:
            request_params["timestamp"] = self._get_timestamp()
        headers = self._headers_for(request_params, signed)
        url = f"{self.base_url}{endpoint}"
        method_upper = method.upper()

        try:
            if method_upper == "GET":
                response = self.session.get(url, params=request_params, headers=headers, timeout=self.DEFAULT_TIMEOUT)
            elif method_upper == "POST":
                response = self.session.post(url, json=request_params, headers=headers, timeout=self.DEFAULT_TIMEOUT)
            else:
                raise ValueError(f"Unsupported HiBT HTTP method: {method}")
            response.raise_for_status()
        except HibtAPIError:
            raise
        except Exception as exc:
            raise HibtAPIError("HTTP_ERROR", str(exc), endpoint=endpoint) from exc

        try:
            payload = response.json()
        except Exception as exc:
            raise HibtAPIError("BAD_JSON", f"Invalid HiBT JSON response: {getattr(response, 'text', '')}", endpoint=endpoint) from exc

        if isinstance(payload, dict) and "code" in payload:
            code = payload.get("code")
            if str(code) not in {"0", "0.0"}:
                raise HibtAPIError(code, str(payload.get("msg") or payload.get("message") or "HiBT API error"), response.status_code, endpoint)
            return payload.get("data")
        return payload

    @staticmethod
    def to_hibt_symbol(symbol: str) -> str:
        raw = str(symbol or "").strip().lower().replace("/", "_").replace("-", "_")
        if not raw:
            raise ValueError("Symbol is required")
        if "_" in raw:
            return raw
        if raw.endswith("usdt") and len(raw) > 4:
            return f"{raw[:-4]}_usdt"
        return f"{raw}_usdt"

    @classmethod
    def to_display_symbol(cls, symbol: str) -> str:
        base = cls.to_hibt_symbol(symbol).split("_", 1)[0]
        return base.upper()

    @classmethod
    def to_period(cls, period: str) -> str:
        value = str(period).strip()
        if value in cls.PERIOD_MAP.values():
            return value
        if value not in cls.PERIOD_MAP:
            raise ValueError(f"Unsupported HiBT period: {period}")
        return cls.PERIOD_MAP[value]

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_server_time(self) -> int:
        data = self._request("GET", "/v2/server/time")
        if isinstance(data, dict):
            return int(data.get("serverTime") or 0)
        return 0

    def get_symbols(self) -> list[Dict[str, Any]]:
        data = self._request("GET", "/v2/market/symbols")
        return data if isinstance(data, list) else []

    def get_tickers(self, symbol: str | None = None) -> Any:
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        return self._request("GET", "/v2/market/tickers", params)

    def get_price(self, symbol: str) -> float:
        hibt_symbol = self.to_hibt_symbol(symbol)
        data = self._request("GET", "/v2/market/ticker/price", {"symbol": hibt_symbol})
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("symbol") and str(entry.get("symbol")).lower() != hibt_symbol:
                continue
            return self._float(entry.get("price") or entry.get("lastPrice") or entry.get("close") or entry.get("contract_price"))
        return 0.0

    def get_klines(self, symbol: str, period: str = "1m", start: int | None = None, end: int | None = None, count: int = 200) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol), "period": self.to_period(period), "count": count}
        if start is not None:
            params["start"] = int(start)
        if end is not None:
            params["end"] = int(end)
        data = self._request("GET", "/v2/market/candle", params)
        return data if isinstance(data, list) else []

    def get_depth(self, symbol: str, limit: int = 20) -> Any:
        return self._request("GET", "/v2/market/depth", {"symbol": self.to_hibt_symbol(symbol), "limit": limit})

    def get_balance(self) -> Any:
        return self._request("GET", "/v2/account/balance", signed=True)

    def get_account_state(self, db: Any | None = None) -> Dict[str, Any]:
        data = self.get_balance()
        balance = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
        total = self._float(balance.get("balance")) + self._float(balance.get("profit"))
        frozen = self._float(balance.get("frozen")) + self._float(balance.get("margin"))
        available = max(0.0, self._float(balance.get("balance")) - self._float(balance.get("frozen")))
        return {
            "total_equity": total,
            "available_balance": available,
            "used_margin": frozen,
            "maintenance_margin": 0.0,
            "margin_usage_percent": (frozen / total * 100) if total > 0 else 0.0,
            "unrealized_pnl": self._float(balance.get("profit") or balance.get("openProfit")),
            "raw_response": data,
            "environment": self.environment,
        }

    def get_positions(self, symbol: str | None = None, include_timing: bool = False) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        data = self._request("GET", "/v2/account/position", params, signed=True)
        entries = data if isinstance(data, list) else []
        positions: list[Dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            amount = self._float(item.get("amount"))
            side = int(self._float(item.get("side")))
            signed_size = amount if side == 1 else -amount if side == 2 else amount
            entry_px = self._float(item.get("price"))
            positions.append(
                {
                    "position_id": item.get("positionID") or item.get("positionId"),
                    "coin": self.to_display_symbol(str(item.get("symbol") or "")),
                    "symbol": self.to_display_symbol(str(item.get("symbol") or "")),
                    "side": "LONG" if side == 1 else "SHORT" if side == 2 else "UNKNOWN",
                    "szi": signed_size,
                    "entry_px": entry_px,
                    "position_value": abs(amount * entry_px),
                    "unrealized_pnl": self._float(item.get("openProfit") or item.get("profit")),
                    "margin_used": self._float(item.get("margin")),
                    "liquidation_px": self._float(item.get("closePrice")),
                    "leverage": int(self._float(item.get("leverage"), 1)),
                    "raw": item,
                }
            )
        return positions

    def set_leverage(self, symbol: str, leverage: int) -> Any:
        return self._request("POST", "/v2/account/setLeverage", {"symbol": self.to_hibt_symbol(symbol), "leverage": int(leverage)}, signed=True)

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        leverage: int = 1,
        reduce_only: bool = False,
        take_profit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        custom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if reduce_only:
            raise ValueError("HiBT reduce-only close requires close_position with a position ID")
        order_type_upper = order_type.upper()
        payload: Dict[str, Any] = {
            "symbol": self.to_hibt_symbol(symbol),
            "type": 2 if order_type_upper == "MARKET" else 1,
            "side": 1 if side.upper() == "BUY" else 2,
            "leverage": int(leverage),
            "amount": str(quantity),
        }
        if custom_id:
            payload["customID"] = custom_id
        if order_type_upper == "LIMIT":
            if price is None:
                raise ValueError("Price required for HiBT limit order")
            payload["price"] = str(price)
        if take_profit_price is not None:
            payload["isSetSp"] = True
            payload["spPrice"] = str(take_profit_price)
            payload.setdefault("triggerType", 2)
        if stop_loss_price is not None:
            payload["isSetSl"] = True
            payload["slPrice"] = str(stop_loss_price)
            payload.setdefault("triggerType", 2)
        data = self._request("POST", "/v2/order/open", payload, signed=True)
        return {
            "order_id": data.get("orderID") if isinstance(data, dict) else None,
            "status": "submitted",
            "symbol": self.to_display_symbol(symbol),
            "side": side.upper(),
            "type": order_type_upper,
            "quantity": float(quantity),
            "price": float(price or 0),
            "environment": self.environment,
            "raw_response": data,
        }

    def close_position(self, position_id: str, quantity: float, order_type: str = "MARKET", price: Optional[float] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "positionID": position_id,
            "amount": str(quantity),
            "type": 2 if order_type.upper() == "MARKET" else 1,
        }
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("Price required for HiBT limit close")
            payload["price"] = str(price)
        data = self._request("POST", "/v2/order/close", payload, signed=True)
        return {"order_id": data.get("orderID") if isinstance(data, dict) else None, "status": "submitted", "raw_response": data}

    def cancel_order(self, symbol: str, order_id: str | None = None, custom_id: str | None = None, position_id: str | None = None) -> Any:
        payload = {
            "symbol": self.to_hibt_symbol(symbol),
            "orderID": order_id or "",
            "customID": custom_id or "",
            "positionID": position_id or "",
        }
        return self._request("POST", "/v2/order/cancel", payload, signed=True)
