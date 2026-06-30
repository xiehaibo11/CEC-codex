"""
Kline loading, caching, fetching and persistence for HistoricalDataProvider.

Provides the data-acquisition layer (database query + API fetch + backfill +
virtual current-candle construction) used by the backtest historical data
provider. Mixed into HistoricalDataProvider; relies on attributes initialized
there (db, symbols, start_time_ms, end_time_ms, exchange, _kline_cache).
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from sqlalchemy import text

logger = logging.getLogger(__name__)


class KlineLoaderMixin:
    """Kline cache/DB/API/persistence methods for HistoricalDataProvider."""

    def _preload_data(self):
        """Preload all kline data for symbols to avoid repeated DB queries."""
        logger.info(f"Preloading data for {len(self.symbols)} symbols...")

        for symbol in self.symbols:
            # Preload common periods (1m for price accuracy, others for indicators)
            for period in ["1m", "5m", "15m", "1h", "4h", "1d"]:
                self._load_klines_to_cache(symbol, period)

        logger.info(f"Preload complete. Cache size: {len(self._kline_cache)} entries")

    def _load_klines_to_cache(self, symbol: str, period: str):
        """Load all klines for symbol/period into cache.

        If database has insufficient data, automatically fetch from API and persist.
        """
        cache_key = f"{symbol}_{period}"

        # Calculate time range with buffer for indicator calculation
        period_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "2h": 7200, "4h": 14400, "8h": 28800,
            "12h": 43200, "1d": 86400
        }
        period_sec = period_seconds.get(period, 300)  # default to 5m
        buffer_seconds = 500 * period_sec

        start_sec = (self.start_time_ms // 1000) - buffer_seconds
        end_sec = self.end_time_ms // 1000

        # Minimum required klines for indicator calculation (EMA100 needs ~150)
        min_required = 150

        try:
            # First, query from database
            klines = self._query_klines_from_db(symbol, period, start_sec, end_sec)

            # Check if data is sufficient:
            # 1. Need at least min_required klines for indicator calculation
            # 2. Data must cover close to end_time (gap < 2 periods means OK)
            needs_fetch = False
            if len(klines) < min_required:
                needs_fetch = True
                logger.warning(
                    f"[Backtest] Insufficient kline data for {symbol}/{period}/{self.exchange}: "
                    f"got {len(klines)}, need {min_required}. Fetching from API..."
                )
            elif klines:
                # Check if latest kline is too far from end_time
                latest_ts = klines[-1]["timestamp"]
                gap_periods = (end_sec - latest_ts) / period_sec
                if gap_periods > 2:
                    needs_fetch = True
                    logger.warning(
                        f"[Backtest] Kline data gap for {symbol}/{period}/{self.exchange}: "
                        f"latest={latest_ts}, end={end_sec}, gap={gap_periods:.0f} periods. Fetching from API..."
                    )

            if needs_fetch:
                # Fetch from API by time range and persist to database
                fetched = self._fetch_and_persist_klines(
                    symbol, period,
                    since_ms=start_sec * 1000,
                    until_ms=end_sec * 1000
                )

                if fetched:
                    logger.info(
                        f"[Backtest] Fetched {len(fetched)} klines for {symbol}/{period}/{self.exchange} from API"
                    )
                    # Re-query from database to get persisted data
                    klines = self._query_klines_from_db(symbol, period, start_sec, end_sec)
                    logger.info(f"[Backtest] After sync: {len(klines)} klines available")
                else:
                    logger.error(
                        f"[Backtest] Failed to fetch klines for {symbol}/{period}/{self.exchange} from API"
                    )

            self._kline_cache[cache_key] = klines
            logger.debug(f"Loaded {len(klines)} klines for {symbol} {period}")

        except Exception as e:
            logger.error(f"Failed to load klines for {symbol} {period}: {e}")
            self._kline_cache[cache_key] = []

    def _query_klines_from_db(self, symbol: str, period: str, start_sec: int, end_sec: int) -> list:
        """Query klines from database."""
        result = self.db.execute(text("""
            SELECT timestamp, open_price, high_price, low_price, close_price, volume
            FROM crypto_klines
            WHERE symbol = :symbol AND period = :period AND exchange = :exchange
            AND timestamp >= :start_ts AND timestamp <= :end_ts
            ORDER BY timestamp ASC
        """), {"symbol": symbol, "period": period, "exchange": self.exchange,
               "start_ts": start_sec, "end_ts": end_sec})

        klines = []
        for row in result:
            klines.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]) if row[5] else 0.0,
            })
        return klines

    def _fetch_and_persist_klines(
        self, symbol: str, period: str,
        since_ms: int = None, until_ms: int = None, count: int = 500
    ) -> list:
        """Fetch klines from API by time range and persist to database.

        Uses time-range API to get historical data matching the backtest window,
        then backfills to database for future reuse.

        Args:
            symbol: Trading symbol
            period: K-line period
            since_ms: Start timestamp in milliseconds (defaults to calculated range)
            until_ms: End timestamp in milliseconds (defaults to end_time_ms)
            count: Fallback count if since_ms not provided
        """
        if until_ms is None:
            until_ms = self.end_time_ms
        if since_ms is None:
            period_seconds = {
                "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                "1h": 3600, "2h": 7200, "4h": 14400, "8h": 28800,
                "12h": 43200, "1d": 86400
            }
            period_sec = period_seconds.get(period, 300)
            since_ms = until_ms - (count * period_sec * 1000)

        try:
            if self.exchange == "binance":
                return self._fetch_binance_klines(symbol, period, since_ms, until_ms)
            else:
                return self._fetch_hyperliquid_klines(symbol, period, since_ms, until_ms)
        except Exception as e:
            logger.error(f"Failed to fetch klines from API for {symbol}/{period}/{self.exchange}: {e}")
            return []

    def _fetch_hyperliquid_klines(self, symbol, period, since_ms, until_ms):
        """Fetch Hyperliquid klines by time range and persist."""
        from services.hyperliquid_market_data import get_historical_kline_data_from_hyperliquid
        klines = get_historical_kline_data_from_hyperliquid(
            symbol=symbol, period=period,
            since_ms=since_ms, until_ms=until_ms,
            environment="mainnet"
        )
        if klines:
            self._persist_klines_to_db(symbol, period, klines, "hyperliquid")
        return klines or []

    def _fetch_binance_klines(self, symbol, period, since_ms, until_ms):
        """Fetch Binance klines by time range and persist."""
        from services.exchanges.binance_adapter import BinanceAdapter
        adapter = BinanceAdapter(environment="mainnet")
        unified_klines = adapter.fetch_klines(
            symbol=symbol, interval=period, limit=500,
            start_time=since_ms, end_time=until_ms
        )
        if not unified_klines:
            return []
        klines = [
            {
                "timestamp": k.timestamp,
                "open": float(k.open_price),
                "high": float(k.high_price),
                "low": float(k.low_price),
                "close": float(k.close_price),
                "volume": float(k.volume),
            }
            for k in unified_klines
        ]
        self._persist_klines_to_db(symbol, period, klines, "binance")
        return klines

    def _persist_klines_to_db(self, symbol: str, period: str, klines: list, exchange: str):
        """Persist klines to database (works for both Hyperliquid and Binance)."""
        from database.models import CryptoKline

        try:
            inserted = 0
            for k in klines:
                ts = k.get("timestamp") or k.get("timestamp", 0)
                # Handle both seconds and milliseconds timestamps
                ts_sec = ts if ts < 1e12 else ts // 1000
                dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
                datetime_str = dt.strftime("%Y-%m-%d %H:%M:%S")

                existing = self.db.query(CryptoKline).filter(
                    CryptoKline.symbol == symbol,
                    CryptoKline.period == period,
                    CryptoKline.exchange == exchange,
                    CryptoKline.timestamp == ts_sec,
                ).first()

                if not existing:
                    record = CryptoKline(
                        exchange=exchange,
                        symbol=symbol,
                        market="CRYPTO",
                        period=period,
                        timestamp=ts_sec,
                        datetime_str=datetime_str,
                        environment="mainnet",
                        open_price=float(k.get("open", 0) or 0),
                        high_price=float(k.get("high", 0) or 0),
                        low_price=float(k.get("low", 0) or 0),
                        close_price=float(k.get("close", 0) or 0),
                        volume=float(k.get("volume", 0) or 0),
                    )
                    self.db.add(record)
                    inserted += 1

            self.db.commit()
            logger.info(f"Persisted {inserted}/{len(klines)} {exchange} klines for {symbol}/{period}")

        except Exception as e:
            logger.error(f"Failed to persist {exchange} klines: {e}")
            self.db.rollback()

    def _build_virtual_kline(self, symbol: str, period: str, current_time_sec: int) -> Optional[Dict]:
        """Build a virtual K-line for the current incomplete period.

        Real-time API returns the current incomplete K-line with close=current_price.
        To match this behavior, we build a virtual K-line from market_asset_metrics
        (15-second granularity mark_price data).

        Args:
            symbol: Trading symbol
            period: K-line period (1m, 5m, 15m, 1h, 4h, 1d)
            current_time_sec: Current simulation time in seconds

        Returns:
            Virtual K-line dict or None if insufficient data
        """
        period_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400
        }
        period_sec = period_seconds.get(period)
        if not period_sec:
            return None

        # Calculate current period start time
        period_start_sec = (current_time_sec // period_sec) * period_sec
        period_start_ms = period_start_sec * 1000
        current_time_ms = current_time_sec * 1000

        # Query mark_price data within current period
        try:
            result = self.db.execute(text("""
                SELECT timestamp, mark_price
                FROM market_asset_metrics
                WHERE symbol = :symbol AND exchange = :exchange
                AND timestamp >= :start_ms AND timestamp <= :end_ms
                ORDER BY timestamp ASC
            """), {
                "symbol": symbol,
                "exchange": self.exchange,
                "start_ms": period_start_ms,
                "end_ms": current_time_ms
            })

            prices = []
            for row in result:
                if row[1]:
                    prices.append(float(row[1]))

            if not prices:
                return None

            # Build OHLC from price series
            return {
                "timestamp": period_start_sec,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "volume": 0.0,  # Volume not available from mark_price
            }

        except Exception as e:
            logger.debug(f"Failed to build virtual kline for {symbol} {period}: {e}")
            return None
