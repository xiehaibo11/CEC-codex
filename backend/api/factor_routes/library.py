"""
Factor library / values routes.

GET /api/factors/library  → Factor registry (built-in + custom)
GET /api/factors/values   → Latest factor values for a symbol/period/exchange
"""

from fastapi import Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import CustomFactor
from services.factor_registry import FACTOR_REGISTRY, FACTOR_CATEGORIES, CATEGORY_LABELS

from .base import router, get_db


@router.get("/library")
async def get_factor_library(db: Session = Depends(get_db)):
    """Return full factor registry: built-in + custom factors."""
    # Built-in factors with source tag
    builtin = [{**f, "source": "builtin"} for f in FACTOR_REGISTRY]

    # Custom factors from DB (includes builtin_expression and user-created)
    custom_rows = db.query(CustomFactor).filter(CustomFactor.is_active == True).all()
    custom = [
        {
            "name": cf.name,
            "category": cf.category if cf.category != "custom" else "custom",
            "display_name": cf.name, "display_name_zh": cf.name,
            "description": cf.description or cf.expression,
            "description_zh": cf.description or cf.expression,
            "source": cf.source or "custom",
            "expression": cf.expression,
            "custom_id": cf.id,
        }
        for cf in custom_rows
    ]

    # Collect all categories from both builtin and custom factors
    all_categories = sorted(set(
        FACTOR_CATEGORIES + [cf.category for cf in custom_rows if cf.category]
    ))

    # Merge category labels (expression engine labels + builtin labels + custom)
    from services.factor_expression_engine import CATEGORY_LABELS as EXPR_LABELS
    merged_labels = {**CATEGORY_LABELS, **EXPR_LABELS,
                     "custom": {"en": "Custom", "zh": "自定义"},
                     "composite": {"en": "Composite", "zh": "复合"},
                     "statistical": {"en": "Statistical", "zh": "统计"}}

    return {
        "factors": builtin + custom,
        "categories": all_categories,
        "category_labels": merged_labels,
    }


@router.get("/values")
async def get_factor_values(
    symbol: str = Query(...),
    period: str = Query("1h"),
    exchange: str = Query("hyperliquid"),
    db: Session = Depends(get_db),
):
    """Return latest factor values for a symbol/period/exchange."""
    rows = db.execute(text("""
        SELECT DISTINCT ON (factor_name)
            factor_name, factor_category, value, timestamp
        FROM factor_values
        WHERE symbol = :sym AND period = :p AND exchange = :ex
        ORDER BY factor_name, timestamp DESC
    """), {"sym": symbol, "p": period, "ex": exchange}).fetchall()

    return {
        "symbol": symbol, "period": period, "exchange": exchange,
        "values": [
            {"factor_name": r[0], "category": r[1], "value": r[2], "timestamp": r[3]}
            for r in rows
        ],
    }
