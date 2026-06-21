"""CoinGlass historical feature loading for event-contract backtests."""

from __future__ import annotations

import bisect
import logging
import os
from typing import Any, Dict, List

import requests

from config.settings import COINGLASS_API_BASE_URL, COINGLASS_API_KEY
from services.event_contract.constants import PERIOD_SECONDS

logger = logging.getLogger(__name__)

DEFAULT_COINGLASS_METRICS = [
    "aggregated_cvd",
    "pair_taker_volume",
    "open_interest",
    "funding_rate",
    "pair_liquidation",
]

COINGLASS_METRIC_SPECS: Dict[str, Dict[str, Any]] = {
    "aggregated_cvd": {
        "label": "Aggregated CVD",
        "path": "/api/futures/aggregated-cvd/history",
        "limit": 4500,
        "coin": True,
        "exchange_list": True,
        "unit": "usd",
    },
    "pair_taker_volume": {
        "label": "Pair taker buy/sell",
        "path": "/api/futures/v2/taker-buy-sell-volume/history",
        "limit": 1000,
        "pair": True,
    },
    "open_interest": {
        "label": "Aggregated open interest",
        "path": "/api/futures/open-interest/aggregated-history",
        "limit": 1000,
        "coin": True,
        "unit": "usd",
    },
    "funding_rate": {
        "label": "Funding rate",
        "path": "/api/futures/funding-rate/history",
        "limit": 1000,
        "pair": True,
    },
    "pair_liquidation": {
        "label": "Pair liquidation",
        "path": "/api/futures/liquidation/history",
        "limit": 1000,
        "pair": True,
    },
}


class EventContractCoinGlassMixin:
    def _load_coinglass_feature_bundle(
        self,
        cfg: Dict[str, Any],
        fetch_start_ts: int,
        fetch_end_ts: int,
        audit_start_ts: int | None = None,
        audit_end_ts: int | None = None,
    ) -> Dict[str, Any]:
        if not cfg.get("enable_coinglass_features"):
            return {"enabled": False, "features_by_ts": {}, "audit": {"enabled": False, "warnings": []}}

        api_key = (cfg.get("_coinglass_api_key") or COINGLASS_API_KEY or os.getenv("COINGLASS_API_KEY", "")).strip()
        if not api_key:
            raise ValueError(
                "CoinGlass features are enabled, but no CoinGlass API key is available. "
                "Save a CoinGlass key in the CoinGlass page or set COINGLASS_API_KEY on the server."
            )

        interval = PERIOD_SECONDS[cfg["period"]]
        fetch_start_ms = int(fetch_start_ts) * 1000
        fetch_end_ms = int(fetch_end_ts) * 1000
        audit_start_ts = int(audit_start_ts if audit_start_ts is not None else fetch_start_ts)
        audit_end_ts = int(audit_end_ts if audit_end_ts is not None else fetch_end_ts)
        metrics = self._coinglass_metrics(cfg)
        series: Dict[str, Dict[int, Dict[str, Any]]] = {}
        metric_audits = []
        warnings: List[str] = []
        errors: List[str] = []

        for metric in metrics:
            spec = COINGLASS_METRIC_SPECS[metric]
            try:
                rows = self._fetch_coinglass_metric(cfg, spec, api_key, fetch_start_ms, fetch_end_ms)
                parsed = self._parse_coinglass_rows(metric, rows, fetch_start_ts, fetch_end_ts)
                series[metric] = parsed
                audit = self._audit_coinglass_metric(metric, spec, parsed, cfg, audit_start_ts, audit_end_ts)
            except Exception as exc:
                logger.warning("CoinGlass %s fetch failed: %s", metric, exc)
                series[metric] = {}
                audit = self._audit_coinglass_metric(metric, spec, {}, cfg, audit_start_ts, audit_end_ts)
                audit["error"] = str(exc)
                errors.append(f"{spec['label']}: {exc}")
            metric_audits.append(audit)
            warnings.extend(audit.get("warnings", []))

        features_by_ts = self._build_coinglass_features_by_ts(series)
        coverage_values = [item["coverage_pct"] for item in metric_audits] or [0.0]
        audit = {
            "enabled": True,
            "source": "coinglass",
            "key_source": cfg.get("_coinglass_key_source") or "server",
            "period": cfg["period"],
            "interval_seconds": interval,
            "records_loaded": sum(len(items) for items in series.values()),
            "decision_records": min((item["decision_records"] for item in metric_audits), default=0),
            "expected_decision_records": max((item["expected_decision_records"] for item in metric_audits), default=0),
            "coverage_pct": round(min(coverage_values), 4),
            "min_required_coverage_pct": cfg["min_coinglass_coverage_pct"],
            "metric_coverage": metric_audits,
            "warnings": warnings + errors,
            "strict": cfg["strict_coinglass_quality"],
            "no_future_leakage": cfg["coinglass_no_future_leakage"],
        }
        self._validate_coinglass_quality(audit, cfg)
        return {
            "enabled": True,
            "features_by_ts": features_by_ts,
            "timestamps": sorted(features_by_ts),
            "audit": audit,
        }

    def _attach_coinglass_features(
        self,
        klines: List[Dict[str, Any]],
        bundle: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not bundle.get("enabled") or not bundle.get("timestamps"):
            return klines
        timestamps = bundle["timestamps"]
        features_by_ts = bundle["features_by_ts"]
        interval = PERIOD_SECONDS[cfg["period"]]
        max_lag = int(cfg.get("max_coinglass_lag_seconds") or interval * 2)
        future_offset = 0 if cfg.get("coinglass_no_future_leakage", True) else interval

        for item in klines:
            usable_ts = int(item["timestamp"]) + future_offset
            idx = bisect.bisect_right(timestamps, usable_ts) - 1
            if idx < 0:
                continue
            feature_ts = timestamps[idx]
            lag = usable_ts - feature_ts
            if lag > max_lag:
                continue
            item["coinglass"] = {**features_by_ts[feature_ts], "lag_seconds": lag}
        return klines

    def _coinglass_metrics(self, cfg: Dict[str, Any]) -> List[str]:
        raw = cfg.get("coinglass_metrics") or DEFAULT_COINGLASS_METRICS
        if isinstance(raw, str):
            raw = [item.strip() for item in raw.split(",")]
        metrics = [item for item in raw if item in COINGLASS_METRIC_SPECS]
        return metrics or list(DEFAULT_COINGLASS_METRICS)

    def _fetch_coinglass_metric(
        self,
        cfg: Dict[str, Any],
        spec: Dict[str, Any],
        api_key: str,
        start_ms: int,
        end_ms: int,
    ) -> List[Dict[str, Any]]:
        interval_ms = PERIOD_SECONDS[cfg["period"]] * 1000
        limit = int(spec["limit"])
        page_span_ms = interval_ms * max(1, limit - 1)
        cursor = start_ms
        pages = 0
        max_pages = int(cfg.get("max_coinglass_pages_per_metric") or 80)
        rows_by_ts: Dict[int, Dict[str, Any]] = {}

        while cursor <= end_ms:
            if pages >= max_pages:
                raise ValueError(f"CoinGlass page limit reached for {spec['label']} ({max_pages})")
            page_end = min(end_ms, cursor + page_span_ms)
            params = self._coinglass_params(cfg, spec, cursor, page_end, limit)
            data = self._coinglass_http_get(spec["path"], params, api_key)
            for row in data:
                ts = self._coinglass_row_ts(row)
                if ts is not None and start_ms <= ts <= end_ms:
                    rows_by_ts[ts] = row
            pages += 1
            cursor = page_end + interval_ms
        return [rows_by_ts[ts] for ts in sorted(rows_by_ts)]

    def _coinglass_params(
        self,
        cfg: Dict[str, Any],
        spec: Dict[str, Any],
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> Dict[str, Any]:
        coin = cfg["symbol"].upper()
        exchange = self._coinglass_exchange_name(cfg["exchange"])
        params: Dict[str, Any] = {
            "interval": cfg["period"],
            "limit": limit,
            "start_time": start_ms,
            "end_time": end_ms,
        }
        if spec.get("coin"):
            params["symbol"] = coin
        if spec.get("exchange_list"):
            params["exchange_list"] = exchange
        if spec.get("pair"):
            params["symbol"] = f"{coin}USDT"
            params["exchange"] = exchange
        if spec.get("unit"):
            params["unit"] = spec["unit"]
        return params

    def _coinglass_http_get(self, path: str, params: Dict[str, Any], api_key: str) -> List[Dict[str, Any]]:
        url = f"{COINGLASS_API_BASE_URL.rstrip('/')}{path}"
        response = requests.get(
            url,
            headers={"CG-API-KEY": api_key, "accept": "application/json"},
            params={key: value for key, value in params.items() if value not in (None, "")},
            timeout=20,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError(f"CoinGlass returned non-JSON response for {path}") from exc
        if not response.ok or str(payload.get("code", "0")) != "0":
            message = payload.get("msg") or payload.get("message") or response.text[:160]
            raise ValueError(f"{path} failed: HTTP {response.status_code}, {message}")
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _parse_coinglass_rows(
        self,
        metric: str,
        rows: List[Dict[str, Any]],
        start_ts: int,
        end_ts: int,
    ) -> Dict[int, Dict[str, Any]]:
        parsed: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            ts_ms = self._coinglass_row_ts(row)
            if ts_ms is None:
                continue
            ts = ts_ms // 1000
            if ts < start_ts or ts > end_ts:
                continue
            item = {"timestamp": ts, "metric": metric}
            if metric == "aggregated_cvd":
                item.update({
                    "buy": self._num(row.get("agg_taker_buy_vol")),
                    "sell": self._num(row.get("agg_taker_sell_vol")),
                    "cum_delta": self._num(row.get("cum_vol_delta")),
                })
            elif metric == "pair_taker_volume":
                item.update({
                    "buy": self._num(row.get("taker_buy_volume_usd")),
                    "sell": self._num(row.get("taker_sell_volume_usd")),
                })
            elif metric in ("open_interest", "funding_rate"):
                item.update({"close": self._num(row.get("close"))})
            elif metric == "pair_liquidation":
                item.update({
                    "long_liq": self._num(row.get("long_liquidation_usd")),
                    "short_liq": self._num(row.get("short_liquidation_usd")),
                })
            parsed[ts] = item
        return parsed

    def _build_coinglass_features_by_ts(self, series: Dict[str, Dict[int, Dict[str, Any]]]) -> Dict[int, Dict[str, Any]]:
        union_ts = sorted({ts for items in series.values() for ts in items})
        previous: Dict[str, Dict[str, Any]] = {}
        features: Dict[int, Dict[str, Any]] = {}
        for ts in union_ts:
            feature: Dict[str, Any] = {"timestamp": ts, "source": "coinglass", "available_metrics": []}
            for metric, rows in series.items():
                row = rows.get(ts)
                if not row:
                    continue
                feature["available_metrics"].append(metric)
                if metric in ("aggregated_cvd", "pair_taker_volume"):
                    buy = row.get("buy") or 0.0
                    sell = row.get("sell") or 0.0
                    total = buy + sell
                    delta_norm = (buy - sell) / total if total else 0.0
                    if metric == "aggregated_cvd":
                        feature["cvd_delta_norm"] = delta_norm
                        feature["cvd_delta_usd"] = row.get("cum_delta") if row.get("cum_delta") is not None else buy - sell
                    else:
                        feature["taker_delta_norm"] = delta_norm
                        feature["taker_buy_sell_ratio"] = buy / sell if sell else 1.0
                elif metric == "open_interest":
                    close = row.get("close")
                    prev = previous.get(metric, {}).get("close")
                    feature["open_interest"] = close
                    feature["oi_change_pct"] = ((close - prev) / prev * 100) if close is not None and prev else 0.0
                elif metric == "funding_rate":
                    feature["funding_rate"] = row.get("close") or 0.0
                elif metric == "pair_liquidation":
                    long_liq = row.get("long_liq") or 0.0
                    short_liq = row.get("short_liq") or 0.0
                    total = long_liq + short_liq
                    feature["liquidation_imbalance"] = (short_liq - long_liq) / total if total else 0.0
                    feature["liquidation_usd"] = total
                previous[metric] = row
            features[ts] = feature
        return features

    def _audit_coinglass_metric(
        self,
        metric: str,
        spec: Dict[str, Any],
        rows: Dict[int, Dict[str, Any]],
        cfg: Dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        interval = PERIOD_SECONDS[cfg["period"]]
        expected = max(0, int((end_ts - start_ts) // interval) + 1)
        decision_records = len([ts for ts in rows if start_ts <= ts + interval <= end_ts])
        coverage = round(decision_records / expected * 100, 4) if expected else 0.0
        warnings = []
        if expected and coverage < cfg["min_coinglass_coverage_pct"]:
            warnings.append(f"{spec['label']} coverage {coverage}% below {cfg['min_coinglass_coverage_pct']}%")
        return {
            "metric": metric,
            "label": spec["label"],
            "decision_records": decision_records,
            "expected_decision_records": expected,
            "coverage_pct": coverage,
            "warnings": warnings,
        }

    def _validate_coinglass_quality(self, audit: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        if audit.get("enabled") and cfg.get("strict_coinglass_quality") and audit.get("warnings"):
            raise ValueError(f"CoinGlass data quality check failed: {'; '.join(audit['warnings'])}")

    def _coinglass_exchange_name(self, exchange: str) -> str:
        mapping = {
            "binance": "Binance",
            "hyperliquid": "Hyperliquid",
            "bybit": "Bybit",
            "okx": "OKX",
            "bitget": "Bitget",
        }
        return mapping.get(str(exchange or "binance").lower(), str(exchange).title())

    def _coinglass_row_ts(self, row: Dict[str, Any]) -> int | None:
        value = row.get("time") or row.get("timestamp")
        try:
            ts = int(float(value))
        except (TypeError, ValueError):
            return None
        return ts * 1000 if ts < 10_000_000_000 else ts

    def _num(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
