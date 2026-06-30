"""
Market-data query interface for HistoricalDataProvider.

Implements the DataProvider-compatible read API (prices, klines, indicators,
flow, regime, factors, market snapshots) constrained to the simulated
current_time_ms. Mixed into HistoricalDataProvider; relies on the kline cache
and helpers provided by KlineLoaderMixin and on attributes initialized in
HistoricalDataProvider (db, symbols, current_time_ms, exchange, caches).
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MarketQueryMixin:
    """Read-side query methods for HistoricalDataProvider."""

    def get_current_prices(self, symbols: List[str] = None) -> Dict[str, float]:
        """Get current prices for symbols at current_time_ms."""
        target_symbols = symbols or self.symbols
        prices = {}

        for symbol in target_symbols:
            if symbol in self._price_cache:
                prices[symbol] = self._price_cache[symbol]
                continue

            price = self._get_price_at_time(symbol, self.current_time_ms)
            if price:
                prices[symbol] = price
                self._price_cache[symbol] = price

        return prices

    def _get_price_at_time(self, symbol: str, timestamp_ms: int) -> Optional[float]:
        """Get price at specific timestamp.

        Priority:
        1. market_asset_metrics.mark_price (15-second granularity, most accurate)
        2. 1m kline close price (fallback)
        """
        # Try market_asset_metrics first (15-second granularity)
        try:
            result = self.db.execute(text("""
                SELECT mark_price FROM market_asset_metrics
                WHERE symbol = :symbol AND exchange = :exchange
                AND timestamp <= :ts
                ORDER BY timestamp DESC LIMIT 1
            """), {"symbol": symbol, "exchange": self.exchange, "ts": timestamp_ms})
            row = result.fetchone()
            if row and row[0]:
                return float(row[0])
        except Exception as e:
            logger.debug(f"Failed to get mark_price for {symbol}: {e}")

        # Fallback to 1m kline close price
        timestamp_sec = timestamp_ms // 1000
        cache_key = f"{symbol}_1m"

        if cache_key in self._kline_cache:
            klines = self._kline_cache[cache_key]
            for k in reversed(klines):
                if k["timestamp"] <= timestamp_sec:
                    return k["close"]
            if klines:
                return klines[0]["close"]

        # Final fallback: DB query for kline
        try:
            result = self.db.execute(text("""
                SELECT close_price FROM crypto_klines
                WHERE symbol = :symbol AND period = '1m' AND exchange = :exchange
                AND timestamp <= :ts
                ORDER BY timestamp DESC LIMIT 1
            """), {"symbol": symbol, "exchange": self.exchange, "ts": timestamp_sec})
            row = result.fetchone()
            if row:
                return float(row[0])
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")

        return None

    def get_klines(self, symbol: str, period: str, count: int = 50) -> List[Any]:
        """
        Get historical K-line data up to current_time_ms.

        Returns Kline objects compatible with DataProvider.
        Includes a virtual "current" K-line built from 15-second mark_price data
        to match real-time API behavior (which returns incomplete current candle).
        """
        from program_trader.models import Kline

        timestamp_sec = self.current_time_ms // 1000
        cache_key = f"{symbol}_{period}"

        # Load and cache all klines for this symbol/period if not cached
        if cache_key not in self._kline_cache:
            self._load_klines_to_cache(symbol, period)

        # Filter klines up to current time and return last 'count'
        all_klines = self._kline_cache.get(cache_key, [])
        filtered = [k for k in all_klines if k["timestamp"] <= timestamp_sec]

        # Build virtual current K-line to match real-time API behavior
        virtual_kline = self._build_virtual_kline(symbol, period, timestamp_sec)
        if virtual_kline:
            # Check if we need to replace or append
            if filtered and filtered[-1]["timestamp"] == virtual_kline["timestamp"]:
                # Same period start - replace with virtual (more up-to-date price)
                # Preserve real volume since virtual kline has no volume data
                virtual_kline["volume"] = filtered[-1]["volume"]
                filtered[-1] = virtual_kline
            else:
                # New period - append virtual kline
                filtered.append(virtual_kline)

        # Convert to Kline objects
        result = []
        for k in filtered[-count:]:
            result.append(Kline(
                timestamp=k["timestamp"],
                open=k["open"],
                high=k["high"],
                low=k["low"],
                close=k["close"],
                volume=k["volume"],
            ))

        # Log query with result summary (last kline info)
        result_summary = None
        if result:
            last_k = result[-1]
            result_summary = {
                "count": len(result),
                "last": {"timestamp": last_k.timestamp, "close": last_k.close}
            }
        self._log_query("get_klines", {"symbol": symbol, "period": period, "count": count, "exchange": self.exchange}, result_summary)

        return result

    def get_indicator(self, symbol: str, indicator: str, period: str) -> Dict[str, Any]:
        """
        Calculate technical indicator from historical klines.

        Uses same calculation as DataProvider for consistency.
        """
        from services.technical_indicators import calculate_indicators

        # Get klines (enough for indicator calculation)
        klines = self.get_klines(symbol, period, 500)
        if not klines:
            self._log_query("get_indicator", {"symbol": symbol, "indicator": indicator, "period": period, "exchange": self.exchange}, {})
            return {}

        # Convert to format expected by calculate_indicators
        kline_data = [
            {
                "timestamp": k.timestamp,
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "volume": k.volume,
            }
            for k in klines
        ]

        result = {}
        try:
            indicator_upper = indicator.upper()
            calculated = calculate_indicators(kline_data, [indicator_upper])

            if indicator_upper in calculated and calculated[indicator_upper] is not None:
                value = calculated[indicator_upper]
                if isinstance(value, list):
                    result = {'value': value[-1] if value else None, 'series': value}
                elif isinstance(value, dict):
                    latest = {}
                    for k, v in value.items():
                        if isinstance(v, list) and v:
                            latest[k] = v[-1]
                        else:
                            latest[k] = v
                    result = latest
                else:
                    result = {'value': value}
        except Exception as e:
            logger.warning(f"Failed to calculate {indicator} for {symbol}: {e}")

        # Log with result (exclude series to save space)
        log_result = {k: v for k, v in result.items() if k != 'series'} if result else {}
        self._log_query("get_indicator", {"symbol": symbol, "indicator": indicator, "period": period, "exchange": self.exchange}, log_result)

        return result

    def get_flow(self, symbol: str, metric: str, period: str) -> Dict[str, Any]:
        """
        Get historical flow data (CVD, OI, TAKER, etc.).

        Queries aggregated market data tables.
        """
        from services.market_flow_indicators import get_flow_indicators_for_prompt

        result = {}
        try:
            results = get_flow_indicators_for_prompt(
                self.db, symbol, period, [metric.upper()], self.current_time_ms,
                exchange=self.exchange
            )
            result = results.get(metric.upper(), {}) or {}
        except Exception as e:
            logger.warning(f"Failed to get flow {metric} for {symbol}: {e}")

        self._log_query("get_flow", {"symbol": symbol, "metric": metric, "period": period, "exchange": self.exchange}, result)
        return result

    def get_regime(self, symbol: str, period: str) -> Any:
        """
        Get market regime at current time.

        Uses historical data to calculate regime.
        """
        from program_trader.models import RegimeInfo
        from services.market_regime_service import get_market_regime

        regime_info = RegimeInfo(regime="noise", conf=0.0)
        log_result = {"regime": "noise", "conf": 0.0}

        try:
            result = get_market_regime(
                self.db, symbol, period,
                use_realtime=True,
                timestamp_ms=self.current_time_ms,
                exchange=self.exchange
            )
            if result:
                regime_info = RegimeInfo(
                    regime=result.get("regime", "noise"),
                    conf=result.get("confidence", 0.0),
                    direction=result.get("direction", "neutral"),
                    reason=result.get("reason", ""),
                    indicators=result.get("indicators", {}),
                )
                log_result = {
                    "regime": regime_info.regime,
                    "conf": regime_info.conf,
                    "direction": regime_info.direction,
                    "indicators": regime_info.indicators,
                }
        except Exception as e:
            logger.warning(f"Failed to get regime for {symbol}: {e}")

        self._log_query("get_regime", {"symbol": symbol, "period": period, "exchange": self.exchange}, log_result)
        return regime_info

    def get_price_change(self, symbol: str, period: str) -> Dict[str, float]:
        """Get price change over period.

        Returns:
            Dict with change_percent (percentage) and change_usd (absolute USD change)
        """
        from services.market_flow_indicators import get_flow_indicators_for_prompt

        result = {"change_percent": 0.0, "change_usd": 0.0}
        try:
            results = get_flow_indicators_for_prompt(
                self.db, symbol, period, ["PRICE_CHANGE"], self.current_time_ms,
                exchange=self.exchange
            )
            data = results.get("PRICE_CHANGE")
            if data:
                change_pct = data.get("current", 0.0)
                start_price = data.get("start_price", 0.0)
                end_price = data.get("end_price", 0.0)
                change_usd = (end_price - start_price) if start_price and end_price else 0.0
                result = {
                    "change_percent": change_pct,
                    "change_usd": change_usd,
                }
        except Exception:
            pass

        self._log_query("get_price_change", {"symbol": symbol, "period": period, "exchange": self.exchange}, result)
        return result

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data snapshot at current time."""
        price = self._get_price_at_time(symbol, self.current_time_ms)
        result = {"symbol": symbol, "price": price or 0.0}

        # Get additional data from market_asset_metrics if available.
        # Binance stores mark_price and open_interest in separate rows
        # (timestamps differ by ~1ms), so we fetch each field's latest
        # non-null value independently instead of relying on a single row.
        try:
            mark_price_val = None
            funding_rate_val = None
            oi_val = None

            row_mp = self.db.execute(text("""
                SELECT mark_price, funding_rate
                FROM market_asset_metrics
                WHERE symbol = :symbol AND exchange = :exchange
                AND timestamp <= :ts AND mark_price IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """), {"symbol": symbol, "exchange": self.exchange, "ts": self.current_time_ms}).fetchone()
            if row_mp:
                mark_price_val = float(row_mp[0] or 0)
                funding_rate_val = float(row_mp[1] or 0)

            row_oi = self.db.execute(text("""
                SELECT open_interest
                FROM market_asset_metrics
                WHERE symbol = :symbol AND exchange = :exchange
                AND timestamp <= :ts AND open_interest IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """), {"symbol": symbol, "exchange": self.exchange, "ts": self.current_time_ms}).fetchone()
            if row_oi:
                oi_val = float(row_oi[0] or 0)

            if mark_price_val is not None or oi_val is not None:
                result = {
                    "symbol": symbol,
                    "price": price or (mark_price_val or 0),
                    "mark_price": mark_price_val or 0,
                    "funding_rate": funding_rate_val or 0,
                    "open_interest": oi_val or 0,
                }
        except Exception as e:
            logger.warning(f"Failed to get market data for {symbol}: {e}")

        self._log_query("get_market_data", {"symbol": symbol, "exchange": self.exchange}, result)
        return result

    def get_factor(self, symbol: str, factor_name: str, period: str = "5m") -> Dict[str, Any]:
        """Get factor value at the current backtest timestamp.

        Sync rule: keep factor value calculation aligned with Program live
        get_factor() and Prompt factor variables. Only the data source differs:
        backtest uses historical K-lines constrained by current_time_ms.
        """
        from program_trader.data_provider import compute_factor_snapshot

        result = compute_factor_snapshot(
            db=self.db,
            symbol=symbol,
            factor_name=factor_name,
            period=period,
            exchange=self.exchange,
            klines_loader=lambda requested_period, count: [
                {
                    "timestamp": k.timestamp,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
                for k in self.get_klines(symbol, requested_period, count)
            ],
            include_effectiveness=False,
        )
        self._log_query("get_factor", {"symbol": symbol, "factor_name": factor_name, "period": period, "exchange": self.exchange}, result)
        return result

    def get_klines_between(
        self,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
        period: str = "5m"
    ) -> List[Dict[str, Any]]:
        """
        Get K-lines between two timestamps for TP/SL checking.

        Returns raw dict format with high/low for checking price extremes.

        Args:
            symbol: Trading symbol
            start_time_ms: Start timestamp (exclusive, after this time)
            end_time_ms: End timestamp (inclusive, up to this time)
            period: K-line period (default 5m for balance of accuracy and performance)

        Returns:
            List of kline dicts with timestamp, high, low, close
        """
        cache_key = f"{symbol}_{period}"

        # Load cache if not exists
        if cache_key not in self._kline_cache:
            self._load_klines_to_cache(symbol, period)

        all_klines = self._kline_cache.get(cache_key, [])

        # Convert to seconds for comparison
        start_sec = start_time_ms // 1000
        end_sec = end_time_ms // 1000

        # Filter klines in range (start exclusive, end inclusive)
        result = [
            k for k in all_klines
            if start_sec < k["timestamp"] <= end_sec
        ]

        return result
