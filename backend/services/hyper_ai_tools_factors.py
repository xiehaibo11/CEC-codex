"""Hyper AI factor-system handlers: query, evaluate, save, edit, compute, list functions."""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database.models import SystemConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Factor System Tool Handlers
# =============================================================================

def execute_query_factors(
    db: Session, exchange: str, symbol: str = None,
    factor_name: str = None, forward_period: str = "4h",
    days: int = 30
) -> str:
    """Query factor library, values, and effectiveness."""
    from services.factor_registry import FACTOR_REGISTRY, CATEGORY_LABELS
    from database.models import CustomFactor

    try:
        # If specific factor requested, return detailed info + history
        if factor_name and symbol:
            row = db.execute(text("""
                SELECT factor_name, factor_category, ic_mean, ic_std, icir,
                    win_rate, sample_count, calc_date, decay_half_life
                FROM factor_effectiveness
                WHERE factor_name = :fn AND symbol = :sym AND period = '1h'
                    AND forward_period = :fp AND exchange = :ex
                ORDER BY calc_date DESC LIMIT 1
            """), {"fn": factor_name, "sym": symbol, "fp": forward_period, "ex": exchange}).fetchone()

            val_row = db.execute(text("""
                SELECT value, timestamp FROM factor_values
                WHERE factor_name = :fn AND symbol = :sym AND period = '1h' AND exchange = :ex
                ORDER BY timestamp DESC LIMIT 1
            """), {"fn": factor_name, "sym": symbol, "ex": exchange}).fetchone()

            from datetime import date as _d, timedelta as _td
            history_cutoff = _d.today() - _td(days=min(days, 365))
            history = db.execute(text("""
                SELECT calc_date, ic_mean, icir, win_rate, sample_count
                FROM factor_effectiveness
                WHERE factor_name = :fn AND symbol = :sym AND period = '1h'
                    AND forward_period = :fp AND exchange = :ex
                    AND calc_date >= :cutoff
                ORDER BY calc_date
            """), {"fn": factor_name, "sym": symbol, "fp": forward_period,
                   "ex": exchange, "cutoff": history_cutoff}).fetchall()

            return json.dumps({
                "factor_name": factor_name,
                "symbol": symbol, "exchange": exchange, "forward_period": forward_period,
                "latest_value": float(val_row[0]) if val_row else None,
                "effectiveness": {
                    "ic_mean": float(row[2]), "ic_std": float(row[3]),
                    "icir": float(row[4]), "win_rate": float(row[5]),
                    "sample_count": row[6], "calc_date": str(row[7]),
                    "decay_half_life_hours": int(row[8]) if row[8] is not None else None,
                } if row else None,
                "history": [
                    {"date": str(r[0]), "ic_mean": float(r[1]), "icir": float(r[2]),
                     "win_rate": float(r[3]), "sample_count": r[4]}
                    for r in history
                ]
            }, indent=2)

        # If symbol provided, return values + effectiveness ranking
        if symbol:
            eff_rows = db.execute(text("""
                SELECT DISTINCT ON (factor_name)
                    factor_name, factor_category, ic_mean, icir, win_rate, sample_count,
                    decay_half_life
                FROM factor_effectiveness
                WHERE symbol = :sym AND period = '1h' AND forward_period = :fp AND exchange = :ex
                ORDER BY factor_name, calc_date DESC
            """), {"sym": symbol, "fp": forward_period, "ex": exchange}).fetchall()

            # IC 7-day trend
            from datetime import date as _date, timedelta as _td
            cutoff_7d = _date.today() - _td(days=7)
            ic_7d_rows = db.execute(text("""
                SELECT factor_name, AVG(ic_mean) as ic_7d
                FROM factor_effectiveness
                WHERE symbol = :sym AND period = '1h' AND forward_period = :fp
                    AND exchange = :ex AND calc_date >= :cutoff
                GROUP BY factor_name
            """), {"sym": symbol, "fp": forward_period, "ex": exchange, "cutoff": cutoff_7d}).fetchall()
            ic_7d_map = {r[0]: round(float(r[1]), 6) if r[1] is not None else None for r in ic_7d_rows}

            items = []
            for r in eff_rows:
                fname = r[0]
                ic_30d = float(r[2])
                ic_7d = ic_7d_map.get(fname)
                ic_trend = None
                if ic_7d is not None and abs(ic_30d) > 1e-6:
                    ic_trend = round(ic_7d / ic_30d, 2)
                items.append({
                    "factor_name": fname, "category": r[1], "ic_mean": ic_30d,
                    "icir": float(r[3]), "win_rate": float(r[4]), "sample_count": r[5],
                    "decay_half_life_hours": int(r[6]) if r[6] is not None else None,
                    "ic_7d": ic_7d, "ic_trend": ic_trend,
                })
            items.sort(key=lambda x: abs(x.get("icir") or 0), reverse=True)

            return json.dumps({
                "symbol": symbol, "exchange": exchange, "forward_period": forward_period,
                "factor_count": len(items),
                "top_factors": items[:15],
                "note": f"Showing top 15 by |ICIR| out of {len(items)} factors"
            }, indent=2)

        # No symbol: return factor library
        custom_rows = db.query(CustomFactor).filter(CustomFactor.is_active == True).all()
        factors = [
            {"name": f["name"], "category": f["category"], "source": "builtin",
             "display_name": f.get("display_name", f["name"])}
            for f in FACTOR_REGISTRY
        ] + [
            {"name": cf.name, "category": "custom", "source": cf.source or "custom",
             "expression": cf.expression, "custom_id": cf.id}
            for cf in custom_rows
        ]
        return json.dumps({
            "exchange": exchange,
            "total_factors": len(factors),
            "builtin_count": len(FACTOR_REGISTRY),
            "custom_count": len(custom_rows),
            "factors": factors
        }, indent=2)

    except Exception as e:
        logger.error(f"[query_factors] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_evaluate_factor(
    db: Session, expression: str, symbol: str, exchange: str
) -> str:
    """Evaluate a factor expression against real market data (full local history)."""
    from services.factor_expression_engine import factor_expression_engine
    from services.factor_data_provider import ensure_kline_coverage
    import pandas as pd

    try:
        ok, err = factor_expression_engine.validate(expression)
        if not ok:
            return json.dumps({"error": err})

        klines = ensure_kline_coverage(db, exchange, symbol, "1h")
        if not klines or len(klines) < 50:
            return json.dumps({"error": f"Insufficient K-line data for {symbol} on {exchange}"})

        results, err = factor_expression_engine.evaluate_ic(expression, klines)
        if results is None:
            return json.dumps({"error": err})

        series, _ = factor_expression_engine.execute(expression, klines)
        latest_value = None
        if series is not None and len(series) > 0:
            last = series.iloc[-1]
            latest_value = float(last) if not pd.isna(last) else None

        return json.dumps({
            "expression": expression, "symbol": symbol, "exchange": exchange,
            "latest_value": latest_value,
            "effectiveness": results
        }, indent=2)

    except Exception as e:
        logger.error(f"[evaluate_factor] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_save_factor(db: Session, name: str, expression: str, description: str = "") -> str:
    """Save a custom factor expression to the library."""
    import re
    from database.models import CustomFactor
    from services.factor_expression_engine import factor_expression_engine

    try:
        # Validate factor name format
        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', name):
            return json.dumps({"error": "Factor name must start with a letter and contain only English letters, digits, and underscores (e.g., RSI_fast, momentum_v2)"})

        ok, err = factor_expression_engine.validate(expression)
        if not ok:
            return json.dumps({"error": f"Invalid expression: {err}"})

        existing = db.query(CustomFactor).filter(CustomFactor.name == name).first()
        if existing:
            return json.dumps({"error": f"Factor name '{name}' already exists"})

        factor = CustomFactor(
            name=name, expression=expression,
            description=description, category="custom", source="ai"
        )
        db.add(factor)
        db.commit()
        db.refresh(factor)

        return json.dumps({
            "success": True,
            "factor_id": factor.id,
            "name": factor.name,
            "expression": factor.expression,
            "action": "created",
            "view_url": "/#factor-library",
            "note": f"Factor '{name}' saved. Use compute_factor to run full evaluation across all symbols."
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[save_factor] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_edit_factor(
    db: Session, factor_id: int,
    name: str = None, expression: str = None, description: str = None
) -> str:
    """Edit an existing custom factor."""
    from database.models import CustomFactor
    from services.factor_expression_engine import factor_expression_engine

    try:
        factor = db.query(CustomFactor).filter(CustomFactor.id == factor_id).first()
        if not factor:
            return json.dumps({"error": f"Custom factor with id={factor_id} not found"})

        if expression:
            ok, err = factor_expression_engine.validate(expression)
            if not ok:
                return json.dumps({"error": f"Invalid expression: {err}"})
            factor.expression = expression

        if name:
            dup = db.query(CustomFactor).filter(
                CustomFactor.name == name, CustomFactor.id != factor_id
            ).first()
            if dup:
                return json.dumps({"error": f"Factor name '{name}' already exists"})
            factor.name = name

        if description is not None:
            factor.description = description

        db.commit()
        db.refresh(factor)

        return json.dumps({
            "success": True,
            "factor_id": factor.id,
            "name": factor.name,
            "expression": factor.expression,
            "action": "updated",
            "view_url": "/#factor-library",
            "note": f"Factor '{factor.name}' updated."
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[edit_factor] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_compute_factor(db: Session, factor_name: str, exchange: str) -> str:
    """Compute a single factor across all watchlist symbols using sliding window IC.
    Delegates to FactorEffectivenessService.compute_single_factor() — no duplicated logic.
    """
    from services.factor_effectiveness_service import FactorEffectivenessService

    try:
        eff_svc = FactorEffectivenessService()
        result = eff_svc.compute_single_factor(db, exchange, factor_name)
        return json.dumps(result, indent=2)
    except Exception as e:
        db.rollback()
        logger.error(f"[compute_factor] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_get_factor_functions(category: str = None) -> str:
    """Return factor expression functions from the registry, optionally filtered by category."""
    from services.factor_expression_engine import factor_expression_engine

    grouped = factor_expression_engine.get_registry_grouped()
    if category:
        filtered = {k: v for k, v in grouped.items() if k == category}
        if not filtered:
            cats = list(grouped.keys())
            return json.dumps({"error": f"Unknown category '{category}'. Available: {cats}"})
        grouped = filtered

    # Compact format for token efficiency
    lines = []
    for cat_key, cat_data in grouped.items():
        lines.append(f"\n## {cat_data['label']}")
        for fn in cat_data["functions"]:
            lines.append(f"- `{fn['signature']}` — {fn['description']}")
            lines.append(f"  Example: `{fn['example']}`")

    return json.dumps({
        "total_functions": sum(len(c["functions"]) for c in grouped.values()),
        "categories": list(grouped.keys()),
        "reference": "\n".join(lines),
    })


