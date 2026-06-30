"""Factor value series extraction helpers for FactorEffectivenessService.

Vectorized extraction of complete factor value series from technical
indicators, derived calculations, and microstructure (flow) data aligned to
K-line timestamps.
"""

import numpy as np

from services.factor_timeframes import period_to_seconds


class _ExtractionMixin:
    def _extract_full_series(self, factor_def, indicators, klines, n_bars,
                             db=None, symbol=None, exchange=None, period="1h"):
        """Extract a complete factor value series (vectorized). Returns list or None."""
        ctype = factor_def["compute_type"]

        if ctype == "technical":
            return self._extract_technical_series(factor_def, indicators, klines, n_bars)

        if ctype == "derived":
            return self._extract_derived_series(factor_def, klines, n_bars)

        if ctype == "microstructure" and db and symbol:
            return self._extract_microstructure_series(
                factor_def, klines, db, symbol, exchange or "hyperliquid", period
            )

        return None

    def _extract_microstructure_series(self, factor_def, klines, db, symbol, exchange, period):
        """Extract historical series for microstructure factors aligned to kline timestamps."""
        from sqlalchemy import text

        indicator_key = factor_def.get("indicator_key", "")
        # Build timestamp list from klines (ms), aligned to the selected K-line period.
        ts_list = [int(k["timestamp"]) * 1000 if k["timestamp"] < 1e12 else int(k["timestamp"]) for k in klines]
        interval_ms = period_to_seconds(period) * 1000
        ts_min, ts_max = ts_list[0], ts_list[-1] + interval_ms

        if indicator_key == "OI_DELTA":
            rows = db.execute(text("""
                SELECT timestamp, open_interest FROM market_asset_metrics
                WHERE symbol = :s AND exchange = :e AND open_interest IS NOT NULL
                    AND timestamp >= :tmin AND timestamp < :tmax
                ORDER BY timestamp ASC
            """), {"s": symbol, "e": exchange, "tmin": ts_min, "tmax": ts_max}).fetchall()
            if len(rows) < 10:
                return None
            return self._align_flow_to_klines_delta(rows, ts_list, interval_ms, col_idx=1)

        if indicator_key == "FUNDING":
            rows = db.execute(text("""
                SELECT timestamp, funding_rate FROM market_asset_metrics
                WHERE symbol = :s AND exchange = :e AND funding_rate IS NOT NULL
                    AND timestamp >= :tmin AND timestamp < :tmax
                ORDER BY timestamp ASC
            """), {"s": symbol, "e": exchange, "tmin": ts_min, "tmax": ts_max}).fetchall()
            if len(rows) < 10:
                return None
            return self._align_flow_to_klines_avg(rows, ts_list, interval_ms, col_idx=1)

        if indicator_key in ("CVD", "TAKER"):
            rows = db.execute(text("""
                SELECT timestamp, taker_buy_volume, taker_sell_volume
                FROM market_trades_aggregated
                WHERE symbol = :s AND exchange = :e
                    AND timestamp >= :tmin AND timestamp < :tmax
                ORDER BY timestamp ASC
            """), {"s": symbol, "e": exchange, "tmin": ts_min, "tmax": ts_max}).fetchall()
            if len(rows) < 10:
                return None
            if indicator_key == "CVD":
                return self._align_flow_to_klines_cvd(rows, ts_list, interval_ms)
            else:
                return self._align_flow_to_klines_taker_ratio(rows, ts_list, interval_ms)

        if indicator_key == "DEPTH":
            rows = db.execute(text("""
                SELECT timestamp, bid_depth_5, ask_depth_5
                FROM market_orderbook_snapshots
                WHERE symbol = :s AND exchange = :e
                    AND timestamp >= :tmin AND timestamp < :tmax
                ORDER BY timestamp ASC
            """), {"s": symbol, "e": exchange, "tmin": ts_min, "tmax": ts_max}).fetchall()
            if len(rows) < 10:
                return None
            return self._align_flow_to_klines_depth(rows, ts_list, interval_ms)

        return None

    def _align_flow_to_klines_avg(self, rows, ts_list, interval_ms, col_idx):
        """Average value per selected K-line bucket."""
        result = []
        row_idx = 0
        n_rows = len(rows)
        for ts in ts_list:
            vals = []
            while row_idx < n_rows and rows[row_idx][0] < ts:
                row_idx += 1
            j = row_idx
            while j < n_rows and rows[j][0] < ts + interval_ms:
                v = rows[j][col_idx]
                if v is not None:
                    vals.append(float(v))
                j += 1
            result.append(sum(vals) / len(vals) if vals else None)
        return result

    def _align_flow_to_klines_delta(self, rows, ts_list, interval_ms, col_idx):
        """Percentage change of value over each selected K-line bucket."""
        result = []
        row_idx = 0
        n_rows = len(rows)
        for ts in ts_list:
            while row_idx < n_rows and rows[row_idx][0] < ts:
                row_idx += 1
            start_val = None
            end_val = None
            j = row_idx
            while j < n_rows and rows[j][0] < ts + interval_ms:
                v = rows[j][col_idx]
                if v is not None:
                    fv = float(v)
                    if start_val is None:
                        start_val = fv
                    end_val = fv
                j += 1
            if start_val and end_val and start_val != 0:
                result.append((end_val - start_val) / start_val * 100)
            else:
                result.append(None)
        return result

    def _align_flow_to_klines_cvd(self, rows, ts_list, interval_ms):
        """Cumulative volume delta per selected K-line bucket: sum(buy - sell)."""
        result = []
        row_idx = 0
        n_rows = len(rows)
        for ts in ts_list:
            cvd = 0.0
            count = 0
            while row_idx < n_rows and rows[row_idx][0] < ts:
                row_idx += 1
            j = row_idx
            while j < n_rows and rows[j][0] < ts + interval_ms:
                buy = float(rows[j][1] or 0)
                sell = float(rows[j][2] or 0)
                cvd += buy - sell
                count += 1
                j += 1
            result.append(cvd if count > 0 else None)
        return result

    def _align_flow_to_klines_taker_ratio(self, rows, ts_list, interval_ms):
        """Taker buy ratio per selected K-line bucket: sum(buy) / sum(buy+sell)."""
        result = []
        row_idx = 0
        n_rows = len(rows)
        for ts in ts_list:
            total_buy = 0.0
            total_sell = 0.0
            count = 0
            while row_idx < n_rows and rows[row_idx][0] < ts:
                row_idx += 1
            j = row_idx
            while j < n_rows and rows[j][0] < ts + interval_ms:
                total_buy += float(rows[j][1] or 0)
                total_sell += float(rows[j][2] or 0)
                count += 1
                j += 1
            total = total_buy + total_sell
            result.append(total_buy / total if total > 0 and count > 0 else None)
        return result

    def _align_flow_to_klines_depth(self, rows, ts_list, interval_ms):
        """Average depth ratio per selected K-line bucket: bid_depth / ask_depth."""
        result = []
        row_idx = 0
        n_rows = len(rows)
        for ts in ts_list:
            ratios = []
            while row_idx < n_rows and rows[row_idx][0] < ts:
                row_idx += 1
            j = row_idx
            while j < n_rows and rows[j][0] < ts + interval_ms:
                bid = float(rows[j][1] or 0)
                ask = float(rows[j][2] or 0)
                if ask > 0:
                    ratios.append(bid / ask)
                j += 1
            result.append(sum(ratios) / len(ratios) if ratios else None)
        return result

    def _extract_technical_series(self, factor_def, indicators, klines, n_bars):
        """Extract full series from technical indicator results."""
        key = factor_def["indicator_key"]
        raw = indicators.get(key)
        if raw is None:
            return None

        extract_key = factor_def.get("extract")
        normalize = factor_def.get("normalize")

        if isinstance(raw, dict):
            if extract_key == "width" and "upper" in raw and "middle" in raw and "lower" in raw:
                u, m, lo = np.array(raw["upper"], dtype=float), np.array(raw["middle"], dtype=float), np.array(raw["lower"], dtype=float)
                with np.errstate(divide='ignore', invalid='ignore'):
                    result = np.where(m != 0, (u - lo) / m, np.nan)
                return [None if np.isnan(v) else float(v) for v in result]

            if extract_key == "percent_b" and "upper" in raw and "lower" in raw:
                u, lo = np.array(raw["upper"], dtype=float), np.array(raw["lower"], dtype=float)
                cl = np.array([float(k["close"]) for k in klines], dtype=float)
                denom = u - lo
                with np.errstate(divide='ignore', invalid='ignore'):
                    result = np.where(denom != 0, (cl - lo) / denom, np.nan)
                return [None if np.isnan(v) else float(v) for v in result]

            if extract_key and extract_key in raw:
                series = raw[extract_key]
                if series and len(series) >= n_bars:
                    return [float(v) if v is not None and not np.isnan(v) else None for v in series[:n_bars]]
                return None

            # Stochastic K/D fallback
            if extract_key == "k":
                for k_key in ("STOCHk", "k", "%K"):
                    if k_key in raw and raw[k_key]:
                        return [float(v) if v is not None and not np.isnan(v) else None for v in raw[k_key][:n_bars]]
            if extract_key == "d":
                for d_key in ("STOCHd", "d", "%D"):
                    if d_key in raw and raw[d_key]:
                        return [float(v) if v is not None and not np.isnan(v) else None for v in raw[d_key][:n_bars]]
            return None

        if isinstance(raw, list) and len(raw) >= n_bars:
            if normalize == "price_deviation":
                cl = [float(k["close"]) for k in klines]
                return [
                    ((cl[i] - raw[i]) / cl[i]) if cl[i] != 0 and raw[i] is not None else None
                    for i in range(n_bars)
                ]
            return [float(v) if v is not None else None for v in raw[:n_bars]]

        return None

    def _extract_derived_series(self, factor_def, klines, n_bars):
        """Extract full series for derived factors (ROC, volume ratio)."""
        derive = factor_def.get("derive_from")
        plen = factor_def.get("period_len", 10)

        if derive == "close":
            closes = np.array([float(k["close"]) for k in klines], dtype=float)
            result = [None] * min(plen, n_bars)
            for i in range(plen, n_bars):
                prev = closes[i - plen]
                result.append((closes[i] - prev) / prev if prev != 0 else None)
            return result

        if derive == "volume_ratio":
            vols = np.array([float(k["volume"]) for k in klines], dtype=float)
            result = [None] * min(plen, n_bars)
            for i in range(plen, n_bars):
                avg = vols[i - plen:i].mean()
                result.append(vols[i] / avg if avg != 0 else None)
            return result

        return None
