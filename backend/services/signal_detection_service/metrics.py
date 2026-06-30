"""
Signal Detection Service - metric value resolution helpers.

Reads metric/factor values from the database and indicator services.
"""

import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class MetricMixin:
    """Mixin providing metric value lookups and conversions."""

    def _get_metric_value(
        self, metric: str, symbol: str, market_data: Dict[str, Any], time_window: int,
        exchange: str = "hyperliquid"
    ) -> Optional[float]:
        """
        Get the current value of a metric from market data or indicators.

        Uses get_indicator_value() from market_flow_indicators for DB-based metrics.
        This ensures proper separation of concerns - signal detection doesn't depend
        on prompt-specific data structures.
        """
        try:
            # taker_volume is handled in _check_signal_trigger directly
            # All other metrics use DB query via market_flow_indicators
            from database.connection import SessionLocal
            from services.market_flow_indicators import get_indicator_value

            # Convert time_window to period string
            period = self._time_window_to_period(time_window)

            # Map old metric names to new names (backward compatibility)
            metric_name_map = {
                "oi_delta_percent": "oi_delta",
                "funding_rate": "funding",
                "taker_buy_ratio": "taker_ratio",
            }
            # Normalize metric name
            metric = metric_name_map.get(metric, metric)

            # Map signal metric names to indicator types (aligned with K-line)
            indicator_map = {
                "oi_delta": "OI_DELTA",
                "cvd": "CVD",
                "depth_ratio": "DEPTH",
                "order_imbalance": "IMBALANCE",
                "taker_ratio": "TAKER",
                "funding": "FUNDING",
                "oi": "OI",
                "price_change": "PRICE_CHANGE",
                "volatility": "VOLATILITY",
            }

            # Factor metric: factor:<factor_name>
            if metric.startswith("factor:"):
                return self._get_factor_metric_value(metric, symbol, period, exchange)

            if metric not in indicator_map:
                logger.warning(f"Unknown metric: {metric}")
                return None

            indicator_type = indicator_map[metric]

            db = SessionLocal()
            try:
                from datetime import datetime
                current_time_ms = int(datetime.utcnow().timestamp() * 1000)
                value = get_indicator_value(db, symbol, indicator_type, period, current_time_ms=current_time_ms, exchange=exchange)
                # DEBUG LOG: Record the exact timestamp used for indicator calculation
                print(f"[MetricValue] symbol={symbol} metric={metric} exchange={exchange} period={period} ts={current_time_ms} value={value}", flush=True)
                return value
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error getting metric {metric} for {symbol}: {e}")
            return None

    def _get_factor_metric_value(
        self, metric: str, symbol: str, period: str, exchange: str
    ) -> Optional[float]:
        """
        Get factor value from K-line data using expression engine.

        Factor metrics use format: factor:<factor_name>
        Loads latest closed K-lines, runs expression engine, returns last value.
        """
        factor_name = metric.split(":", 1)[1]
        try:
            from database.connection import SessionLocal
            from services.market_data import get_kline_data
            from services.factor_resolver import compute_factor_series

            db = SessionLocal()
            try:
                market = "binance" if exchange == "binance" else "CRYPTO"
                klines = get_kline_data(symbol, market=market, period=period, count=300)
                if not klines or len(klines) < 30:
                    logger.warning(f"Insufficient K-line data for factor {factor_name}: {symbol}")
                    return None

                series, _, err = compute_factor_series(
                    db=db,
                    factor_name=factor_name,
                    symbol=symbol,
                    period=period,
                    exchange=exchange,
                    klines=klines,
                )
                if series is None or len(series) == 0:
                    logger.warning(f"Factor {factor_name} execution failed: {err}")
                    return None

                import pandas as pd
                last_val = series.iloc[-1]
                if pd.isna(last_val):
                    return None

                value = float(last_val)
                print(f"[FactorMetric] symbol={symbol} factor={factor_name} exchange={exchange} "
                      f"period={period} value={value:.6f}", flush=True)
                return value
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error computing factor metric {factor_name} for {symbol}: {e}")
            return None

    def _enrich_factor_effectiveness(
        self, result: dict, metric: str, symbol: str, exchange: str
    ) -> None:
        """Enrich a factor signal result with effectiveness data from DB."""
        factor_name = metric.split(":", 1)[1]
        try:
            from database.connection import SessionLocal
            from sqlalchemy import text as sa_text

            db = SessionLocal()
            try:
                row = db.execute(sa_text(
                    "SELECT ic_mean, icir, win_rate, decay_half_life "
                    "FROM factor_effectiveness "
                    "WHERE factor_name = :fn AND symbol = :sym AND exchange = :ex "
                    "AND period = '1h' AND forward_period = '4h' "
                    "ORDER BY created_at DESC LIMIT 1"
                ), {"fn": factor_name, "sym": symbol, "ex": exchange}).fetchone()

                if row:
                    result["factor_effectiveness"] = {
                        "ic": round(float(row[0]), 4) if row[0] is not None else None,
                        "icir": round(float(row[1]), 2) if row[1] is not None else None,
                        "win_rate": round(float(row[2]), 2) if row[2] is not None else None,
                        "decay_half_life_hours": int(row[3]) if row[3] is not None else None,
                    }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error enriching factor effectiveness for {factor_name}/{symbol}: {e}")

    def _get_funding_current_rate(self, symbol: str, time_window, exchange: str = "hyperliquid") -> Optional[float]:
        """Get current funding rate in bps for context."""
        try:
            from database.connection import SessionLocal
            from services.market_flow_indicators import _get_funding_data, TIMEFRAME_MS
            from datetime import datetime

            period = time_window if isinstance(time_window, str) else self._time_window_to_period(time_window)
            if period not in TIMEFRAME_MS:
                return None

            interval_ms = TIMEFRAME_MS[period]
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            db = SessionLocal()
            try:
                data = _get_funding_data(db, symbol, period, interval_ms, current_time_ms, exchange)
                return data.get("current") if data else None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting funding current rate for {symbol}: {e}")
            return None

    def _time_window_to_period(self, time_window: int) -> str:
        """Convert time window (seconds or string) to period string"""
        if isinstance(time_window, str):
            return time_window
        # time_window in seconds
        if time_window <= 60:
            return "1m"
        elif time_window <= 180:
            return "3m"
        elif time_window <= 300:
            return "5m"
        elif time_window <= 900:
            return "15m"
        elif time_window <= 1800:
            return "30m"
        elif time_window <= 3600:
            return "1h"
        elif time_window <= 7200:
            return "2h"
        else:
            return "4h"
