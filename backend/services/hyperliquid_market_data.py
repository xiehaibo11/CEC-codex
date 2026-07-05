"""
Hyperliquid market data service using CCXT
"""
import ccxt
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import time

from services.exchanges.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '2h': 7200,
    '4h': 14400,
    '8h': 28800,
    '12h': 43200,
    '1d': 86400,
    '3d': 259200,
    '1w': 604800,
    '1M': 2592000,
}

class HyperliquidClient:
    def __init__(self, environment: str = "mainnet"):
        self.environment = environment
        self.exchange = None

    def _initialize_exchange(self):
        """Initialize CCXT Hyperliquid exchange"""
        try:
            # Dynamic sandbox mode based on environment
            sandbox_mode = self.environment == "testnet"

            self.exchange = ccxt.hyperliquid({
                'sandbox': sandbox_mode,  # Dynamic based on environment
                'enableRateLimit': True,
                'options': {
                    'fetchMarkets': {
                        'types': ['swap'],  # Only load perp markets; skip spot (testnet has inconsistent spot data)
                        'hip3': {
                            'dex': []  # Skip HIP3 DEX markets
                        }
                    }
                }
            })
            self._disable_hip3_markets()

            # Pre-load markets to avoid ~3s delay on first API call
            # Markets are cached in the exchange instance
            try:
                self.exchange.load_markets()
                logger.info(f"CCXT markets pre-loaded for {self.environment}: {len(self.exchange.markets)} markets")
            except Exception as market_err:
                logger.warning(f"Failed to pre-load markets (will load on first use): {market_err}")

            logger.info(f"Hyperliquid exchange initialized successfully for {self.environment} environment")
        except Exception as e:
            logger.error(f"Failed to initialize Hyperliquid exchange for {self.environment}: {e}")
            raise

    def _disable_hip3_markets(self) -> None:
        """Ensure HIP3 market fetching is disabled."""
        try:
            fetch_markets_options = self.exchange.options.setdefault('fetchMarkets', {})
            hip3_options = fetch_markets_options.setdefault('hip3', {})
            hip3_options['enabled'] = False
            hip3_options['dex'] = []
            # Manually initialize hip3TokensByName to prevent KeyError in coin_to_market_id()
            self.exchange.options.setdefault('hip3TokensByName', {})
        except Exception as options_error:
            logger.debug(f"Unable to update HIP3 fetch options: {options_error}")

        if hasattr(self.exchange, 'fetch_hip3_markets'):
            def _skip_hip3_markets(exchange_self, params=None):
                logger.debug("Skipping HIP3 market fetch in market data client")
                return []
            self.exchange.fetch_hip3_markets = _skip_hip3_markets.__get__(self.exchange, type(self.exchange))
            logger.info("HIP3 market fetch disabled for market data client")

    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get the last price for a symbol"""
        try:
            ticker = self.get_ticker_data(symbol)
            if ticker and ticker.get('price'):
                return float(ticker['price'])
            return None

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def _info_api_url(self, symbol: str) -> str:
        if SymbolMapper.is_hip3_symbol(symbol):
            return "https://api.hyperliquid.xyz/info"
        if self.environment == "testnet":
            return "https://api.hyperliquid-testnet.xyz/info"
        return "https://api.hyperliquid.xyz/info"

    def get_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get complete ticker data using Hyperliquid native API"""
        try:
            import requests
            api_url = self._info_api_url(symbol)
            is_hip3 = SymbolMapper.is_hip3_symbol(symbol)

            payload = {"type": "metaAndAssetCtxs"}
            if is_hip3:
                payload["dex"] = "xyz"

            # Use Hyperliquid native API for complete market data
            response = requests.post(
                api_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list) or len(data) < 2:
                raise Exception("Invalid API response structure")

            # Find symbol index in universe (meta data)
            symbol_upper = SymbolMapper.to_internal(symbol.upper(), "hyperliquid")
            symbol_index = None

            if isinstance(data[0], dict) and 'universe' in data[0]:
                for i, asset_meta in enumerate(data[0]['universe']):
                    if isinstance(asset_meta, dict):
                        asset_name = str(asset_meta.get('name', '')).upper()
                        asset_internal = SymbolMapper.to_internal(asset_name, "hyperliquid")
                        if asset_internal == symbol_upper or asset_name == symbol_upper.replace('/', ''):
                            symbol_index = i
                            break

            if symbol_index is None or symbol_index >= len(data[1]):
                if is_hip3:
                    logger.warning("HIP-3 ticker symbol not found in Hyperliquid metadata: %s", symbol)
                    return None
                # Fallback to CCXT for unsupported symbols
                return self._get_ccxt_ticker_fallback(symbol)

            # Get asset data by index
            asset_data = data[1][symbol_index]
            if not isinstance(asset_data, dict):
                if is_hip3:
                    return None
                return self._get_ccxt_ticker_fallback(symbol)

            # Extract data from Hyperliquid API
            mark_px = float(asset_data.get('markPx', 0))
            oracle_px = float(asset_data.get('oraclePx', 0))
            prev_day_px = float(asset_data.get('prevDayPx', 0))
            day_ntl_vlm = float(asset_data.get('dayNtlVlm', 0))
            open_interest = float(asset_data.get('openInterest', 0))
            funding_rate = float(asset_data.get('funding', 0))

            # Calculate 24h change
            change_24h = mark_px - prev_day_px if prev_day_px else 0
            percentage_24h = (change_24h / prev_day_px * 100) if prev_day_px else 0

            # Convert open interest to USD value (OI * price)
            open_interest_usd = open_interest * mark_px

            result = {
                'symbol': symbol,
                'price': mark_px,
                'oracle_price': oracle_px,
                'change24h': change_24h,
                'volume24h': day_ntl_vlm,
                'percentage24h': percentage_24h,
                'open_interest': open_interest_usd,
                'funding_rate': funding_rate,
            }

            logger.info(f"Got Hyperliquid ticker for {symbol}: price={result['price']}, change24h={result['change24h']:.2f}")
            return result

        except Exception as e:
            logger.error(f"Error fetching Hyperliquid ticker for {symbol}: {e}")
            if SymbolMapper.is_hip3_symbol(symbol):
                return None
            # Fallback to CCXT
            return self._get_ccxt_ticker_fallback(symbol)

    def _get_ccxt_ticker_fallback(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fallback to CCXT ticker for unsupported symbols"""
        try:
            if not self.exchange:
                self._initialize_exchange()

            formatted_symbol = self._format_symbol(symbol)

            try:
                ticker = self.exchange.fetch_ticker(formatted_symbol)
            except Exception as perp_error:
                error_msg = str(perp_error).lower()
                if 'does not have market symbol' in error_msg or 'bad symbol' in error_msg:
                    if ':USDC' in formatted_symbol:
                        spot_symbol = formatted_symbol.replace(':USDC', '')
                        logger.debug(f"Perpetual format failed for {symbol}, retrying with spot format: {spot_symbol}")
                        ticker = self.exchange.fetch_ticker(spot_symbol)
                    else:
                        raise
                else:
                    raise

            result = {
                'symbol': symbol,
                'price': float(ticker['last']) if ticker['last'] else 0,
                'change24h': float(ticker['change']) if ticker['change'] else 0,
                'volume24h': float(ticker['baseVolume']) if ticker['baseVolume'] else 0,
                'percentage24h': float(ticker['percentage']) if ticker['percentage'] else 0,
            }
            return result
        except Exception as e:
            logger.error(f"CCXT fallback failed for {symbol}: {e}")
            return None

    def check_symbol_tradability(self, symbol: str) -> bool:
        """
        Check if a symbol is tradable (can fetch price data).

        This method is designed for validation purposes during symbol refresh
        and won't log errors for invalid symbols.

        Returns:
            True if symbol can fetch valid price data, False otherwise
        """
        try:
            ticker = self.get_ticker_data(symbol)
            price = ticker.get('price') if ticker else None
            is_valid = price is not None and price > 0
            if is_valid:
                logger.debug(f"Symbol {symbol} is tradable (price: {price})")
            return is_valid

        except Exception:
            # Silently return False for invalid symbols during validation
            return False

    def get_kline_data(self, symbol: str, period: str = '1d', count: int = 100, persist: bool = True) -> List[Dict[str, Any]]:
        """Get kline/candlestick data for a symbol"""
        try:
            return self._fetch_kline_native(symbol, period, count, persist)

        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []

    def get_historical_kline_data(self, symbol: str, period: str, since_ms: int, until_ms: int = None) -> List[Dict[str, Any]]:
        """Get historical kline data for a specific time range (for trade replay)

        Args:
            symbol: Trading symbol (e.g., 'BTC')
            period: Time period (e.g., '5m', '15m', '1h')
            since_ms: Start timestamp in milliseconds
            until_ms: End timestamp in milliseconds (optional)

        Returns:
            List of kline data dictionaries
        """
        try:
            return self._fetch_kline_native_range(symbol, period, since_ms, until_ms)

        except Exception as e:
            logger.error(f"Error fetching historical klines for {symbol}: {e}")
            return []

    def _persist_kline_data(self, symbol: str, period: str, klines: List[Dict[str, Any]]):
        """Persist kline data to database

        IMPORTANT DESIGN DECISION:
        Only mainnet K-line data is persisted to database.
        Testnet data is fetched in real-time on-demand and NOT stored.

        This design ensures:
        1. Database contains consistent historical data (mainnet only)
        2. Testnet trading uses real-time API calls without database overhead
        3. No environment mixing in stored K-line data
        """
        # CRITICAL: Only persist mainnet data per design specification
        if self.environment != "mainnet":
            logger.debug(f"Skipping K-line persistence for {symbol} {period} (environment={self.environment}, only mainnet data is stored)")
            return

        try:
            from database.connection import SessionLocal
            from repositories.kline_repo import KlineRepository

            db = SessionLocal()
            try:
                kline_repo = KlineRepository(db)
                result = kline_repo.save_kline_data(
                    symbol=symbol,
                    market="CRYPTO",
                    period=period,
                    kline_data=klines,
                    exchange="hyperliquid",
                    environment="mainnet"  # Always store as mainnet per design
                )
                logger.debug(f"Persisted {result['total']} kline records for {symbol} {period}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error persisting kline data: {e}")
            raise

    def get_market_status(self, symbol: str) -> Dict[str, Any]:
        """Get market status for a symbol"""
        try:
            if not self.exchange:
                self._initialize_exchange()
            
            formatted_symbol = self._format_symbol(symbol)
            
            # Hyperliquid is 24/7, but we can check if the market exists
            markets = self.exchange.load_markets()
            market_exists = formatted_symbol in markets
            
            status = {
                'market_status': 'OPEN' if market_exists else 'CLOSED',
                'is_trading': market_exists,
                'symbol': formatted_symbol,
                'exchange': 'Hyperliquid',
                'market_type': 'crypto',
            }
            
            if market_exists:
                market_info = markets[formatted_symbol]
                status.update({
                    'base_currency': market_info.get('base'),
                    'quote_currency': market_info.get('quote'),
                    'active': market_info.get('active', True),
                })
            
            logger.info(f"Market status for {formatted_symbol}: {status['market_status']}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting market status for {symbol}: {e}")
            return {
                'market_status': 'ERROR',
                'is_trading': False,
                'error': str(e)
            }

    def get_all_symbols(self) -> List[str]:
        """Get all available trading symbols"""
        try:
            if not self.exchange:
                self._initialize_exchange()
            
            markets = self.exchange.load_markets()
            symbols = list(markets.keys())
            
            # Filter for USDC pairs (both spot and perpetual)
            usdc_symbols = [s for s in symbols if '/USDC' in s]
            
            # Prioritize mainstream cryptos (perpetual swaps) and popular spot pairs
            mainstream_perps = [s for s in usdc_symbols if any(crypto in s for crypto in ['BTC/', 'ETH/', 'SOL/', 'DOGE/', 'BNB/', 'XRP/'])]
            other_symbols = [s for s in usdc_symbols if s not in mainstream_perps]
            
            # Return mainstream first, then others
            result = mainstream_perps + other_symbols[:50]
            
            logger.info(f"Found {len(usdc_symbols)} USDC trading pairs, returning {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return ['BTC/USD', 'ETH/USD', 'SOL/USD']  # Fallback popular pairs

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for CCXT (e.g., 'BTC' -> 'BTC/USDC:USDC')

        Hyperliquid primarily uses perpetual swap format for most trading pairs.
        Default to perpetual format, with fallback to spot in calling functions.
        """
        if '/' in symbol and ':' in symbol:
            return symbol
        elif '/' in symbol:
            # If it's BTC/USDC, convert to BTC/USDC:USDC for Hyperliquid
            return f"{symbol}:USDC"

        # Handle -PERP suffix (e.g., 'BTC-PERP' -> 'BTC')
        symbol_clean = symbol.upper()
        if symbol_clean.endswith('-PERP'):
            symbol_clean = symbol_clean[:-5]

        # Default to perpetual swap format (most common on Hyperliquid)
        symbol_upper = symbol_clean
        return f"{symbol_upper}/USDC:USDC"

    def _fetch_kline_native(self, symbol: str, period: str = '1d', count: int = 100, persist: bool = True) -> List[Dict[str, Any]]:
        """Fetch klines through Hyperliquid native candleSnapshot API."""
        secs = INTERVAL_SECONDS.get(period, 86400)
        end_time = int(time.time() * 1000)
        start_time = end_time - (secs * count * 1000)
        return self._fetch_kline_native_range(symbol, period, start_time, end_time, persist=persist)

    def _fetch_kline_native_range(
        self,
        symbol: str,
        period: str,
        since_ms: int,
        until_ms: Optional[int] = None,
        persist: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch Hyperliquid klines for an explicit time range."""
        import requests

        exchange_symbol = SymbolMapper.to_exchange(symbol, "hyperliquid")
        end_time = until_ms or int(time.time() * 1000)
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": exchange_symbol,
                "interval": period,
                "startTime": since_ms,
                "endTime": end_time,
            },
        }

        try:
            resp = requests.post(self._info_api_url(symbol), json=payload, timeout=15)
            resp.raise_for_status()
            candles = resp.json()
        except Exception as err:
            logger.warning("Failed to fetch Hyperliquid klines for %s: %s", symbol, err)
            return []

        klines: List[Dict[str, Any]] = []
        candle_items = candles if isinstance(candles, list) else []
        for candle in candle_items:
            try:
                ts_ms = candle['t']
                open_price = float(candle['o'])
                high_price = float(candle['h'])
                low_price = float(candle['l'])
                close_price = float(candle['c'])
                volume = float(candle['v'])
            except (KeyError, TypeError, ValueError) as parse_err:
                logger.debug("Skipping malformed Hyperliquid candle for %s: %s", symbol, parse_err)
                continue

            change = close_price - open_price if open_price else 0
            percent = (change / open_price * 100) if open_price else 0
            klines.append({
                'timestamp': int(ts_ms / 1000),
                'datetime': datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat(),
                # keep key parity with kline_data_service and the Binance path
                'datetime_str': datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume,
                'amount': volume * close_price if volume and close_price else None,
                'chg': change,
                'percent': percent,
            })

        if persist and klines:
            try:
                self._persist_kline_data(SymbolMapper.to_internal(symbol, "hyperliquid"), period, klines)
            except Exception as persist_error:
                logger.warning(f"Failed to persist Hyperliquid kline data for {symbol}: {persist_error}")

        logger.info("Got %d Hyperliquid klines for %s", len(klines), exchange_symbol)
        return klines


from services.hyperliquid_market_data_clients import (
    create_hyperliquid_client,
    get_all_symbols_from_hyperliquid,
    get_default_hyperliquid_client,
    get_historical_kline_data_from_hyperliquid,
    get_hyperliquid_client_for_environment,
    get_kline_data_from_hyperliquid,
    get_last_price_from_hyperliquid,
    get_market_status_from_hyperliquid,
    get_ticker_data_from_hyperliquid,
)
