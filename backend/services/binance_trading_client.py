"""
Binance Futures Trading Client

Handles trading operations on Binance USDS-M Futures via REST API.
Supports both testnet and mainnet environments.
"""

import hashlib
import hmac
import logging
import os
import time
import requests
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional
from urllib.parse import urlencode

from config.settings import BINANCE_BROKER_CONFIG
from services.binance_trading_account import BinanceTradingAccountMixin
from services.binance_trading_history import BinanceTradingHistoryMixin
from services.binance_trading_order_views import BinanceTradingOrderViewsMixin
from services.binance_trading_orders import BinanceTradingOrdersMixin
from services.binance_trading_tpsl import BinanceTradingTpslMixin

logger = logging.getLogger(__name__)


class BinanceAPIError(Exception):
    """Structured Binance REST API error."""

    def __init__(
        self,
        code: Any,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        super().__init__(f"Binance API Error {code}: {message}")


class BinanceTradingClient(
    BinanceTradingAccountMixin,
    BinanceTradingOrdersMixin,
    BinanceTradingOrderViewsMixin,
    BinanceTradingTpslMixin,
    BinanceTradingHistoryMixin,
):
    """
    Binance Futures trading client with HMAC authentication.

    Supports:
    - Account balance and position queries
    - Leverage configuration
    - Market/Limit order placement
    - Stop-loss and take-profit orders
    """

    # API Endpoints
    MAINNET_BASE_URL = "https://fapi.binance.com"
    TESTNET_BASE_URL = "https://demo-fapi.binance.com"
    DEFAULT_RECV_WINDOW = 10000
    SERVER_TIME_SYNC_TTL_SECONDS = 30

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        environment: str = "testnet"
    ):
        """
        Initialize Binance trading client.

        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            environment: 'testnet' or 'mainnet'
        """
        if environment not in ("testnet", "mainnet"):
            raise ValueError(f"Invalid Binance environment: {environment!r}. Must be 'testnet' or 'mainnet'.")
        self.api_key = api_key
        self.secret_key = secret_key
        self.environment = environment
        self.base_url = self.TESTNET_BASE_URL if environment == "testnet" else self.MAINNET_BASE_URL
        self.broker_id = BINANCE_BROKER_CONFIG.broker_id

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        })
        proxy = os.environ.get("BINANCE_HTTPS_PROXY") or os.environ.get("HTTPS_PROXY")
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})
            logger.info(f"[BinanceTradingClient] Using proxy: {proxy}")

        # Cache for exchange info (precision data)
        self._exchange_info_cache: Optional[Dict] = None
        self._exchange_info_timestamp: float = 0
        self._cache_ttl = 3600  # 1 hour

        # Rate limit tracking (from response headers)
        self._last_used_weight: int = 0
        self._weight_cap: int = 2400  # Binance Futures default

        # Signed requests need Binance server-aligned timestamps.
        self._timestamp_offset_ms: int = 0
        self._server_time_synced_at: float = 0.0

        logger.info(f"[BINANCE] Client initialized for {environment}")

    def _get_local_timestamp(self) -> int:
        """Get local system timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _get_timestamp(self) -> int:
        """Get Binance-aligned timestamp in milliseconds."""
        return self._get_local_timestamp() + self._timestamp_offset_ms

    def _sync_server_time(self, force: bool = False) -> int:
        """
        Sync local timestamp offset against Binance server time.

        Uses the midpoint between request start/end to reduce the impact of
        network latency on the offset estimate.
        """
        now = time.time()
        if not force and self._server_time_synced_at and (
            now - self._server_time_synced_at
        ) < self.SERVER_TIME_SYNC_TTL_SECONDS:
            return self._timestamp_offset_ms

        url = f"{self.base_url}/fapi/v1/time"
        request_start_ms = self._get_local_timestamp()
        response = self.session.get(url, timeout=5)
        request_end_ms = self._get_local_timestamp()
        response.raise_for_status()

        payload = response.json()
        server_time_ms = int(payload["serverTime"])
        midpoint_ms = (request_start_ms + request_end_ms) // 2

        self._timestamp_offset_ms = server_time_ms - midpoint_ms
        self._server_time_synced_at = time.time()

        logger.debug(
            "[BINANCE] Synced server time offset: %sms (round trip %sms)",
            self._timestamp_offset_ms,
            request_end_ms - request_start_ms,
        )
        return self._timestamp_offset_ms

    def _sign(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for request parameters.

        Args:
            params: Request parameters dict

        Returns:
            Hex-encoded signature string
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _prepare_signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build a fresh signed params dict with Binance-aligned timestamp."""
        signed_params = dict(params)
        signed_params["timestamp"] = self._get_timestamp()
        signed_params["recvWindow"] = self.DEFAULT_RECV_WINDOW
        signed_params["signature"] = self._sign(signed_params)
        return signed_params

    def _is_timestamp_error(self, error_code: Any, error_msg: Any) -> bool:
        """Return True when Binance rejects the request due to timestamp drift."""
        return str(error_code) == "-1021" or "recvWindow" in str(error_msg)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Binance API.

        Args:
            method: HTTP method ('GET' or 'POST')
            endpoint: API endpoint path
            params: Request parameters
            signed: Whether to sign the request

        Returns:
            JSON response as dict

        Raises:
            Exception: On API error
        """
        url = f"{self.base_url}{endpoint}"
        base_params = dict(params or {})
        max_attempts = 2 if signed else 1

        for attempt in range(max_attempts):
            request_params = dict(base_params)

            try:
                if signed:
                    self._sync_server_time(force=(attempt > 0))
                    request_params = self._prepare_signed_params(request_params)

                if method == "GET":
                    response = self.session.get(url, params=request_params, timeout=10)
                elif method == "DELETE":
                    response = self.session.delete(url, params=request_params, timeout=10)
                else:
                    response = self.session.post(url, data=request_params, timeout=10)

                # Log rate limit info and save to instance
                used_weight = response.headers.get("X-MBX-USED-WEIGHT-1M", "0")
                try:
                    self._last_used_weight = int(used_weight)
                except (ValueError, TypeError):
                    pass
                logger.debug(f"[BINANCE] {method} {endpoint} - Weight: {used_weight}/{self._weight_cap}")

                if response.status_code != 200:
                    try:
                        error_data = response.json() if response.text else {}
                    except ValueError:
                        error_data = {}

                    error_code = error_data.get("code", response.status_code)
                    error_msg = error_data.get("msg", response.text)

                    if signed and attempt == 0 and self._is_timestamp_error(error_code, error_msg):
                        logger.warning(
                            "[BINANCE] Timestamp drift detected for %s %s, syncing server time and retrying once",
                            method,
                            endpoint,
                        )
                        self._server_time_synced_at = 0.0
                        continue

                    logger.error(f"[BINANCE] API Error: {error_code} - {error_msg}")
                    raise BinanceAPIError(
                        error_code,
                        str(error_msg),
                        status_code=response.status_code,
                        endpoint=endpoint,
                    )

                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error(f"[BINANCE] Request failed: {endpoint} - {e}")
                raise

        raise RuntimeError(f"Binance request retry loop exited unexpectedly: {method} {endpoint}")

    def _get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange info with caching.

        Returns:
            Exchange info dict with symbols and filters
        """
        now = time.time()
        if self._exchange_info_cache and (now - self._exchange_info_timestamp) < self._cache_ttl:
            return self._exchange_info_cache

        self._exchange_info_cache = self._request("GET", "/fapi/v1/exchangeInfo")
        self._exchange_info_timestamp = now
        return self._exchange_info_cache

    def _get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get symbol-specific info including precision filters.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Symbol info dict or None if not found
        """
        exchange_info = self._get_exchange_info()
        for sym_info in exchange_info.get("symbols", []):
            if sym_info["symbol"] == symbol:
                return sym_info
        return None

    def _get_precision(self, symbol: str) -> Dict[str, Any]:
        """
        Get price and quantity precision for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with tick_size, step_size, min_qty, min_notional
        """
        sym_info = self._get_symbol_info(symbol)
        if not sym_info:
            # Default conservative values
            return {
                "tick_size": Decimal("0.01"),
                "step_size": Decimal("0.001"),
                "min_qty": Decimal("0.001"),
                "min_notional": Decimal("5")
            }

        result = {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_qty": Decimal("0.001"),
            "min_notional": Decimal("5")
        }

        for f in sym_info.get("filters", []):
            if f["filterType"] == "PRICE_FILTER":
                result["tick_size"] = Decimal(f["tickSize"])
            elif f["filterType"] == "LOT_SIZE":
                result["step_size"] = Decimal(f["stepSize"])
                result["min_qty"] = Decimal(f["minQty"])
            elif f["filterType"] == "MIN_NOTIONAL":
                result["min_notional"] = Decimal(f["notional"])

        return result

    def _round_price(self, price: float, tick_size: Decimal) -> Decimal:
        """Round price to tick size."""
        price_dec = Decimal(str(price))
        return (price_dec / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick_size

    def _round_quantity(self, quantity: float, step_size: Decimal) -> Decimal:
        """Round quantity to step size."""
        qty_dec = Decimal(str(quantity))
        return (qty_dec / step_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * step_size

    def _to_binance_symbol(self, symbol: str) -> str:
        """
        Convert internal symbol to Binance format.

        Args:
            symbol: Internal symbol (e.g., 'BTC' or 'BTCUSDT')

        Returns:
            Binance symbol (e.g., 'BTCUSDT')
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol

    def _to_internal_symbol(self, binance_symbol: str) -> str:
        """
        Convert Binance symbol to internal format.

        Args:
            binance_symbol: Binance symbol (e.g., 'BTCUSDT')

        Returns:
            Internal symbol (e.g., 'BTC')
        """
        if binance_symbol.endswith("USDT"):
            return binance_symbol[:-4]
        return binance_symbol
