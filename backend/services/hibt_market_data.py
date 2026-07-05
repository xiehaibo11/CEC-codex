"""HiBT perpetual futures public market-data endpoints.

Mixed into :class:`services.hibt_trading_client.HibtTradingClient`. Every
endpoint here is an unsigned public REST call from the official perpetual
contract docs (https://apidoc.hibt.co/hibt-openapi-en, Basic Information API).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from services.exchanges.base_adapter import UnifiedKline, UnifiedTrade


class HibtMarketDataMixin:
    """Public (unsigned) HiBT market-data REST endpoints.

    Relies on ``_request``, ``to_hibt_symbol``, ``to_period`` and ``_float``
    provided by the concrete client class.
    """

    DEPTH_LIMITS = (5, 10, 20, 50, 100, 200)

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

    def get_deals(self, symbol: str) -> list[Dict[str, Any]]:
        """Latest public trades for a symbol (``/v2/market/deals``)."""
        data = self._request("GET", "/v2/market/deals", {"symbol": self.to_hibt_symbol(symbol)})
        return data if isinstance(data, list) else []

    def get_mark_prices(self, symbol: str | None = None) -> list[Dict[str, Any]]:
        """Mark/index prices (``/v2/market/index``); all symbols when omitted."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        data = self._request("GET", "/v2/market/index", params)
        return data if isinstance(data, list) else []

    def get_funding_rate(
        self,
        symbol: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> list[Dict[str, Any]]:
        """Funding-rate history in ms timestamps (max 3-month range, limit<=1000)."""
        params: Dict[str, Any] = {"symbol": self.to_hibt_symbol(symbol)}
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        if limit is not None:
            params["limit"] = int(limit)
        data = self._request("GET", "/v2/market/fundingRate", params)
        return data if isinstance(data, list) else []

    def get_risk_limit(self, symbol: str) -> list[Dict[str, Any]]:
        """Risk-limit tiers incl. maintenance margin rate and max leverage."""
        data = self._request("GET", "/v2/market/riskLimit", {"symbol": self.to_hibt_symbol(symbol)})
        return data if isinstance(data, list) else []

    def get_contracts(self, symbol: str | None = None) -> list[Dict[str, Any]]:
        """Latest contract market data (open interest, funding, fees, ...)."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        data = self._request("GET", "/v2/market/contracts", params)
        return data if isinstance(data, list) else []

    def get_contract_specifications(self) -> list[Dict[str, Any]]:
        data = self._request("GET", "/v2/market/contractSpecifications")
        return data if isinstance(data, list) else []

    def get_order_book(self, symbol: str | None = None, depth: int | None = None) -> Any:
        """Aggregated contract order book (``/v2/market/orderBook``, depth 1-100)."""
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_hibt_symbol(symbol)
        if depth is not None:
            params["depth"] = int(depth)
        return self._request("GET", "/v2/market/orderBook", params)


def hibt_candles_to_unified(
    raw: List[Dict[str, Any]], symbol: str, period: str
) -> List["UnifiedKline"]:
    """Map HIBT ``/v2/market/candle`` rows to ``UnifiedKline``.

    HIBT candles carry ``ts`` in milliseconds and no taker split, so
    CVD-derived features are simply absent for this venue. ``symbol`` is stored
    as the passed-in internal symbol (e.g. ``BTC``), matching the rest of the
    ``crypto_klines`` table.
    """
    from decimal import Decimal

    from services.exchanges.base_adapter import UnifiedKline

    mapped: List[UnifiedKline] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            open_price = Decimal(str(item["open"]))
            high_price = Decimal(str(item["high"]))
            low_price = Decimal(str(item["low"]))
            close_price = Decimal(str(item["close"]))
            amount = Decimal(str(item.get("amount") or 0))
            volume = Decimal(str(item.get("volume") or 0))
            # HiBT live rows use amount=base quantity and volume=quote notional,
            # but older examples/docs can be encountered in the opposite shape.
            if amount > 0 and volume >= amount * close_price * Decimal("0.5"):
                base_volume = amount
                quote_volume = volume
            else:
                base_volume = volume
                quote_volume = amount
            mapped.append(
                UnifiedKline(
                    exchange="hibt",
                    symbol=symbol,
                    interval=period,
                    timestamp=int(item["ts"]) // 1000,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=base_volume,
                    quote_volume=quote_volume,
                )
            )
        except (KeyError, TypeError, ValueError, ArithmeticError):
            continue
    return mapped


def _normalize_deal_side(value: Any) -> str | None:
    """Normalize HiBT public deal side into a taker side."""
    side = str(value or "").strip().lower()
    if side in {"buy", "b", "bid", "1"}:
        return "buy"
    if side in {"sell", "s", "ask", "a", "2"}:
        return "sell"
    return None


def hibt_deals_to_unified(raw: List[Dict[str, Any]], symbol: str) -> List["UnifiedTrade"]:
    """Map HiBT ``/v2/market/deals`` rows to ``UnifiedTrade``.

    HiBT returns recent public trades with millisecond ``time``, ``amount``,
    ``price`` and ``side`` fields. ``side`` is treated as the taker side, which
    is the shape expected by local CVD/taker-flow storage.
    """
    from decimal import Decimal

    from services.exchanges.base_adapter import UnifiedTrade

    mapped: List[UnifiedTrade] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            side = _normalize_deal_side(item.get("side") or item.get("direction") or item.get("type"))
            if not side:
                continue
            timestamp = int(item.get("time") or item.get("ts") or item.get("timestamp"))
            if timestamp < 10_000_000_000:
                timestamp *= 1000
            price = Decimal(str(item["price"]))
            size = Decimal(str(item.get("amount") or item.get("qty") or item.get("quantity") or item.get("volume")))
            if price <= 0 or size <= 0:
                continue
            mapped.append(
                UnifiedTrade(
                    exchange="hibt",
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                    size=size,
                    side=side,
                    trade_id=str(item.get("id") or item.get("tradeId") or item.get("trade_id") or ""),
                )
            )
        except (KeyError, TypeError, ValueError, ArithmeticError):
            continue
    return mapped


def fetch_hibt_klines(
    symbol: str,
    period: str,
    count: int = 200,
    start: int | None = None,
    end: int | None = None,
    client: Any | None = None,
) -> List["UnifiedKline"]:
    """Fetch recent HIBT candles for ``symbol``/``period`` and map to
    ``UnifiedKline``. Uses the public (unsigned) candle endpoint. Persistence is
    left to the caller. HIBT's candle cap is 500 rows per request. ``start`` and
    ``end`` are millisecond timestamps when provided.
    """
    from services.hibt_trading_client import HibtTradingClient

    count = min(max(int(count), 1), 500)
    hibt_client = client or HibtTradingClient(access_key="", secret_key="")
    raw = hibt_client.get_klines(symbol, period=period, count=count, start=start, end=end)
    return hibt_candles_to_unified(raw, symbol, period)


def fetch_hibt_deals(symbol: str) -> List["UnifiedTrade"]:
    """Fetch latest HiBT public trades and map them to unified taker flow."""
    from services.hibt_trading_client import HibtTradingClient

    raw = HibtTradingClient(access_key="", secret_key="").get_deals(symbol)
    return hibt_deals_to_unified(raw, symbol)
