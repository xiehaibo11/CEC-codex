"""Market-data tools for AI signal generation."""
import logging
from typing import Any, Dict, List

import requests
from sqlalchemy.orm import Session

from services.exchanges.symbol_mapper import SymbolMapper
from services.signal_backtest_service import TIMEFRAME_MS, signal_backtest_service

logger = logging.getLogger(__name__)

def _tool_get_indicator_statistics(
    db: Session, symbol: str, indicator: str, time_window: str
) -> Dict[str, Any]:
    """Get statistical distribution of an indicator."""
    import numpy as np

    # Map indicator names
    metric_map = {
        "oi_delta_percent": "oi_delta",
        "funding_rate": "funding",
        "taker_buy_ratio": "taker_ratio",
    }
    metric = metric_map.get(indicator, indicator)
    interval_ms = TIMEFRAME_MS.get(time_window, 300000)

    # Get bucket values using backtest service's method
    signal_backtest_service._bucket_cache = {}
    bucket_values = signal_backtest_service._compute_all_bucket_values(
        db, symbol.upper(), metric, interval_ms
    )

    if not bucket_values:
        return {"error": f"No data found for {indicator} on {symbol}"}

    values = [v for v in bucket_values.values() if v is not None]
    if not values:
        return {"error": "No valid values found"}

    arr = np.array(values)
    return {
        "symbol": symbol.upper(),
        "indicator": indicator,
        "time_window": time_window,
        "data_points": len(values),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }


def _tool_backtest_threshold(
    db: Session, symbol: str, indicator: str, operator: str,
    threshold: float, time_window: str
) -> Dict[str, Any]:
    """Backtest a threshold on historical market flow data."""
    # Build trigger condition
    trigger_condition = {
        "metric": indicator,
        "operator": operator,
        "threshold": threshold,
        "time_window": time_window
    }

    # Use existing backtest service
    result = signal_backtest_service.backtest_temp_signal(
        db=db,
        symbol=symbol.upper(),
        trigger_condition=trigger_condition,
        kline_min_ts=None,
        kline_max_ts=None
    )

    if "error" in result:
        return {"error": result["error"]}

    triggers = result.get("triggers", [])
    trigger_count = len(triggers)

    # Return sample timestamps (max 10 for AI to analyze)
    sample_timestamps = [t["timestamp"] for t in triggers[:10]]

    return {
        "symbol": symbol.upper(),
        "indicator": indicator,
        "operator": operator,
        "threshold": threshold,
        "time_window": time_window,
        "trigger_count": trigger_count,
        "sample_timestamps": sample_timestamps,
        "assessment": (
            "too_many" if trigger_count > 50 else
            "too_few" if trigger_count < 5 else
            "reasonable"
        )
    }


def _tool_get_kline_context(
    db: Session, symbol: str, timestamps: List[int], time_window: str,
    exchange: str = "hyperliquid"
) -> Dict[str, Any]:
    """Get K-line price data around specific timestamps."""
    # Map time_window to interval format
    interval_map = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
        "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h"
    }
    interval = interval_map.get(time_window, "5m")
    interval_ms = TIMEFRAME_MS.get(time_window, 300000)

    # Limit to 10 timestamps
    timestamps = timestamps[:10]
    if not timestamps:
        return {"error": "No timestamps provided"}

    # Fetch K-lines from exchange API
    try:
        # Get range covering all timestamps with some buffer
        min_ts = min(timestamps) - (10 * interval_ms)
        max_ts = max(timestamps) + (10 * interval_ms)

        if exchange == "binance":
            # Binance USDS-M Futures API
            binance_symbol = f"{symbol.upper()}USDT"
            url = f"https://fapi.binance.com/fapi/v1/klines"
            params = {
                "symbol": binance_symbol,
                "interval": interval,
                "startTime": min_ts,
                "endTime": max_ts,
                "limit": 1500
            }
            resp = requests.get(url, params=params, timeout=10)
        else:
            # Hyperliquid API (default)
            url = "https://api.hyperliquid.xyz/info"
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": SymbolMapper.to_exchange(symbol.upper(), "hyperliquid"),
                    "interval": interval,
                    "startTime": min_ts,
                    "endTime": max_ts
                }
            }
            resp = requests.post(url, json=payload, timeout=10)

        if resp.status_code != 200:
            return {"error": f"Failed to fetch K-lines: HTTP {resp.status_code}"}

        klines = resp.json()
        if not klines:
            return {"error": "No K-line data returned"}

        # Build K-line lookup by timestamp (handle different exchange formats)
        kline_map = {}
        for k in klines:
            if exchange == "binance":
                # Binance format: [openTime, open, high, low, close, volume, ...]
                ts = k[0]
                kline_map[ts] = {
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                }
            else:
                # Hyperliquid format: {"t": timestamp, "o": open, ...}
                ts = k.get("t", k.get("T", 0))
                kline_map[ts] = {
                    "open": float(k.get("o", 0)),
                    "high": float(k.get("h", 0)),
                    "low": float(k.get("l", 0)),
                    "close": float(k.get("c", 0)),
                    "volume": float(k.get("v", 0))
                }

        # For each trigger timestamp, get context (before, at, after)
        contexts = []
        sorted_kline_ts = sorted(kline_map.keys())
        for trigger_ts in timestamps:
            # Find closest K-line
            closest_ts = min(sorted_kline_ts, key=lambda x: abs(x - trigger_ts))
            idx = sorted_kline_ts.index(closest_ts)

            context = {"trigger_ts": trigger_ts, "klines": []}
            # Get 3 K-lines before, the trigger, and 3 after
            for i in range(max(0, idx - 3), min(len(sorted_kline_ts), idx + 4)):
                ts = sorted_kline_ts[i]
                k = kline_map[ts]
                context["klines"].append({
                    "ts": ts,
                    "o": k["open"], "h": k["high"], "l": k["low"], "c": k["close"]
                })
            contexts.append(context)

        return {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "time_window": time_window,
            "contexts": contexts
        }
    except Exception as e:
        logger.error(f"Error fetching K-line context: {e}")
        return {"error": str(e)}


def _tool_get_indicators_batch(
    db: Session, symbol: str, indicators: List[str], time_window: str,
    exchange: str = "hyperliquid"
) -> Dict[str, Any]:
    """Get statistical distribution of multiple indicators in one call."""
    import numpy as np

    # Limit to 6 indicators
    indicators = indicators[:6]
    if not indicators:
        return {"error": "No indicators provided"}

    metric_map = {
        "oi_delta_percent": "oi_delta",
        "funding_rate": "funding",
        "taker_buy_ratio": "taker_ratio",
        "taker_volume": "taker_ratio",  # taker_volume uses same underlying data
    }
    interval_ms = TIMEFRAME_MS.get(time_window, 300000)

    results = {"symbol": symbol.upper(), "exchange": exchange, "time_window": time_window, "indicators": {}}

    for indicator in indicators:
        # Handle factor indicators
        if indicator.startswith("factor:"):
            factor_name = indicator.split(":", 1)[1]
            try:
                from services.market_data import get_kline_data
                from services.factor_resolver import (
                    compute_factor_series,
                    extract_factor_expression,
                )

                market = "binance" if exchange == "binance" else "CRYPTO"
                klines = get_kline_data(symbol.upper(), market=market, period=time_window, count=500)
                if not klines or len(klines) < 50:
                    results["indicators"][indicator] = {"error": "Insufficient K-line data"}
                    continue

                series, factor, err = compute_factor_series(
                    db=db,
                    factor_name=factor_name,
                    symbol=symbol.upper(),
                    period=time_window,
                    exchange=exchange,
                    klines=klines,
                )
                if series is None or len(series) == 0:
                    results["indicators"][indicator] = {"error": err or "Factor computation failed"}
                    continue

                values = series.dropna().astype(float).tolist()
                if not values:
                    results["indicators"][indicator] = {"error": "No valid values"}
                    continue

                arr = np.array(values)
                factor_info = {
                    "type": "factor",
                    "expression": extract_factor_expression(factor or {"name": factor_name}),
                    "data_points": len(values),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "mean": float(np.mean(arr)),
                    "p50": float(np.percentile(arr, 50)),
                    "p75": float(np.percentile(arr, 75)),
                    "p90": float(np.percentile(arr, 90)),
                    "p95": float(np.percentile(arr, 95)),
                    "p99": float(np.percentile(arr, 99)),
                    "latest": float(arr[-1]),
                    "note": "Factor triggers at K-line close. Use metric format: factor:" + factor_name,
                }
                # Attach decay half-life from effectiveness table
                from sqlalchemy import text as sa_text
                dhl_row = db.execute(sa_text("""
                    SELECT decay_half_life FROM factor_effectiveness
                    WHERE factor_name = :fn AND symbol = :sym AND period = '1h'
                        AND exchange = :ex AND decay_half_life IS NOT NULL
                    ORDER BY calc_date DESC LIMIT 1
                """), {"fn": factor_name, "sym": symbol.upper(), "ex": exchange}).fetchone()
                if dhl_row and dhl_row[0] is not None:
                    factor_info["decay_half_life_hours"] = int(dhl_row[0])
                results["indicators"][indicator] = factor_info
            except Exception as e:
                results["indicators"][indicator] = {"error": str(e)}
            continue

        metric = metric_map.get(indicator, indicator)

        # Special note for taker_volume
        if indicator == "taker_volume":
            results["indicators"][indicator] = {
                "note": "taker_volume is a composite indicator. Use direction (buy/sell/any), ratio_threshold (multiplier), and volume_threshold (USD) instead of operator/threshold.",
                "underlying_metric": "taker_ratio (log scale)",
                "example": {"direction": "buy", "ratio_threshold": 1.5, "volume_threshold": 100000}
            }
            continue
        signal_backtest_service._bucket_cache = {}
        bucket_values = signal_backtest_service._compute_all_bucket_values(
            db, symbol.upper(), metric, interval_ms, exchange
        )

        if not bucket_values:
            results["indicators"][indicator] = {"error": f"No data for {indicator}"}
            continue

        values = [v for v in bucket_values.values() if v is not None]
        if not values:
            results["indicators"][indicator] = {"error": "No valid values"}
            continue

        arr = np.array(values)
        results["indicators"][indicator] = {
            "data_points": len(values),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "p90": float(np.percentile(arr, 90)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
        }

    return results
