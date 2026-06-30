"""Core orchestration for the Factor Effectiveness Service.

Defines FactorEffectivenessService (composed from the extraction and scoring
mixins), the daily scheduler hook, exchange-level and single-factor compute
entrypoints, and the module singleton.

See the package __init__ docstring for the full architecture and performance
history of the sliding-window IC/ICIR pipeline.
"""

import logging
import time
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from database.connection import SessionLocal
from services.factor_registry import FACTOR_REGISTRY
from services.technical_indicators import calculate_indicators
from services.scheduler import task_scheduler

from services.factor_effectiveness_service.extraction import _ExtractionMixin
from services.factor_effectiveness_service.scoring import _ScoringMixin

logger = logging.getLogger(__name__)


class FactorEffectivenessService(_ScoringMixin, _ExtractionMixin):
    def __init__(self):
        self._running = False
        self._progress: Dict = {"status": "idle"}

    def start(self):
        if self._running:
            return
        self._running = True
        from apscheduler.triggers.cron import CronTrigger
        task_scheduler.scheduler.add_job(
            func=self._run,
            trigger=CronTrigger(hour=1, minute=0),
            id="factor_effectiveness_daily",
            replace_existing=True,
            max_instances=1, coalesce=True,
        )
        print("[FactorEffectiveness] Scheduled daily at UTC 01:00", flush=True)

    def stop(self):
        self._running = False

    def _run(self):
        db: Session = SessionLocal()
        try:
            for ex in ["hyperliquid", "binance"]:
                self.compute_for_exchange(db, ex)
        except Exception as e:
            logger.error(f"[FactorEffectiveness] error: {e}")
        finally:
            db.close()

    def get_progress(self) -> Dict:
        return dict(self._progress)

    def compute_for_exchange(self, db: Session, exchange: str, period: str = "1h",
                             force: bool = False):
        """Compute effectiveness for all factors on one exchange.

        Args:
            force: If True, recompute ALL windows (overwrites existing data via
                   ON CONFLICT DO UPDATE). Used by manual compute button.
                   If False, skip existing calc_dates (daily cron incremental mode).
        """
        symbols = self._get_symbols(db, exchange)
        if not symbols:
            self._progress = {"status": "idle"}
            return {"computed": 0, "exchange": exchange}
        total = len(symbols)
        self._progress = {
            "status": "running", "phase": "effectiveness",
            "period": period,
            "symbol_completed": 0, "symbol_total": total,
            "current_symbol": "", "current_factor": "",
            "factor_completed": 0, "factor_total": 0,
        }
        count = 0
        for i, symbol in enumerate(symbols):
            self._progress["current_symbol"] = symbol
            self._progress["symbol_completed"] = i
            try:
                n = self._compute_symbol(db, exchange, symbol, period, force)
                count += n
            except Exception as e:
                logger.warning(f"[FactorEffectiveness] {exchange}/{symbol}: {e}")
        db.commit()
        self._progress = {"status": "idle"}
        print(f"[FactorEffectiveness] {exchange}: {count} records", flush=True)
        return {"computed": count, "exchange": exchange, "period": period}

    def compute_single_factor(self, db: Session, exchange: str, factor_name: str) -> dict:
        """Public API: Compute one factor across all watchlist symbols.
        Called by Hyper AI's compute_factor tool. Always force=True to ensure
        latest algorithm is applied (overwrites old data via ON CONFLICT).
        """
        import pandas as pd
        from database.models import CustomFactor
        from services.factor_expression_engine import factor_expression_engine
        from services.factor_data_provider import ensure_kline_coverage

        builtin_def = next((f for f in FACTOR_REGISTRY if f["name"] == factor_name), None)
        custom_factor = None
        if not builtin_def:
            custom_factor = db.query(CustomFactor).filter(
                CustomFactor.name == factor_name, CustomFactor.is_active == True
            ).first()
            if not custom_factor:
                return {"error": f"Factor '{factor_name}' not found"}

        symbols = self._get_symbols(db, exchange)
        if not symbols:
            return {"error": f"No watchlist symbols for {exchange}"}

        computed = 0
        icir_values = []

        for symbol in symbols:
            klines = ensure_kline_coverage(db, exchange, symbol, "1h")
            if not klines or len(klines) < 50:
                continue

            n_bars = len(klines)
            closes = [float(k["close"]) for k in klines]

            if custom_factor:
                series, err = factor_expression_engine.execute(custom_factor.expression, klines)
                if series is None:
                    continue
                fvals = [None if pd.isna(v) else float(v) for v in series.tolist()]
                category = custom_factor.category or "custom"
            else:
                tech_keys = list({f["indicator_key"] for f in FACTOR_REGISTRY
                                  if f["compute_type"] == "technical"})
                indicators = calculate_indicators(klines, tech_keys)
                fvals = self._extract_full_series(
                    builtin_def, indicators, klines, n_bars, db, symbol, exchange, "1h")
                if fvals is None:
                    continue
                category = builtin_def["category"]

            n = self._compute_factor_windowed(
                db, exchange, factor_name, category, symbol, "1h",
                fvals, closes, klines, n_bars, force=True,
            )
            computed += n

            latest_row = db.execute(text("""
                SELECT icir FROM factor_effectiveness
                WHERE exchange = :ex AND factor_name = :fn AND symbol = :sym
                    AND period = '1h' AND forward_period = '4h'
                ORDER BY calc_date DESC LIMIT 1
            """), {"ex": exchange, "fn": factor_name, "sym": symbol}).fetchone()
            if latest_row:
                icir_values.append(float(latest_row[0]))

        db.commit()

        avg_icir = round(sum(icir_values) / len(icir_values), 4) if icir_values else 0
        return {
            "success": True,
            "factor_name": factor_name, "exchange": exchange,
            "symbols_computed": len(icir_values),
            "total_records": computed,
            "avg_icir_4h": avg_icir,
            "note": f"Computed {factor_name} across {len(icir_values)} symbols. "
                    f"Average 4h ICIR: {avg_icir}",
        }

    # ── internal ──

    def _get_symbols(self, db, exchange):
        try:
            if exchange == "binance":
                from services.binance_symbol_service import get_selected_symbols
            else:
                from services.hyperliquid_symbol_service import get_selected_symbols
            return get_selected_symbols()
        except Exception:
            rows = db.execute(text(
                "SELECT DISTINCT symbol FROM crypto_klines "
                "WHERE exchange = :ex AND period = '1h' LIMIT 50"
            ), {"ex": exchange}).fetchall()
            return [r[0] for r in rows]

    def _compute_symbol(self, db, exchange, symbol, period, force=False) -> int:
        """Compute factor effectiveness for one symbol using sliding window IC."""
        from services.factor_data_provider import ensure_kline_coverage

        klines = ensure_kline_coverage(db, exchange, symbol, period)
        if not klines or len(klines) < 50:
            return 0

        n_bars = len(klines)
        closes = [float(k["close"]) for k in klines]

        tech_keys = list({f["indicator_key"] for f in FACTOR_REGISTRY
                          if f["compute_type"] == "technical"})
        indicators = calculate_indicators(klines, tech_keys)

        factor_series: Dict[str, List[Optional[float]]] = {}
        for fdef in FACTOR_REGISTRY:
            series = self._extract_full_series(
                fdef, indicators, klines, n_bars, db, symbol, exchange, period)
            if series is not None:
                factor_series[fdef["name"]] = (series, fdef["category"])

        # Count custom factors for accurate progress (builtin + custom = total)
        from database.models import CustomFactor
        try:
            custom_count = db.query(CustomFactor).filter(
                CustomFactor.is_active == True).count()
        except Exception:
            custom_count = 0

        count = 0
        builtin_count = len(factor_series)
        factor_total = builtin_count + custom_count
        for fi, (fname, (fvals, fcat)) in enumerate(factor_series.items()):
            self._progress["current_factor"] = fname
            self._progress["factor_completed"] = fi
            self._progress["factor_total"] = factor_total
            count += self._compute_factor_windowed(
                db, exchange, fname, fcat, symbol, period,
                fvals, closes, klines, n_bars, force=force,
            )

        count += self._compute_custom_effectiveness(
            db, exchange, symbol, period, klines, closes, n_bars,
            force=force, factor_offset=builtin_count, factor_total=factor_total,
        )
        return count


# Singleton
factor_effectiveness_service = FactorEffectivenessService()
