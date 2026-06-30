"""
Expression evaluation routes.

POST /api/factors/evaluate             → Evaluate an expression on-demand
POST /api/factors/validate-expression  → Quick syntax check
GET  /api/factors/expression-functions → Available functions + metadata
"""

import pandas as pd
from pydantic import BaseModel

from services.factor_expression_engine import factor_expression_engine, FUNCTION_REGISTRY
from services.factor_timeframes import get_forward_period_offsets

from .base import router


class EvaluateRequest(BaseModel):
    expression: str
    symbol: str
    exchange: str = "hyperliquid"
    period: str = "1h"


@router.post("/evaluate")
async def evaluate_expression(req: EvaluateRequest):
    """Evaluate a factor expression on-demand (no save required)."""
    from services.market_data import get_kline_data

    market = "binance" if req.exchange == "binance" else "CRYPTO"
    klines = get_kline_data(req.symbol, market=market, period=req.period, count=500)
    if not klines or len(klines) < 50:
        return {"status": "error", "error": f"Insufficient K-line data for {req.symbol}"}

    results, err = factor_expression_engine.evaluate_ic(
        req.expression,
        klines,
        forward_periods=get_forward_period_offsets(req.period),
    )
    if results is None:
        return {"status": "error", "error": err}

    # Also get latest value + percentile distribution for threshold suggestions
    series, _ = factor_expression_engine.execute(req.expression, klines)
    latest_value = None
    percentiles = None
    if series is not None and len(series) > 0:
        clean = series.dropna()
        if len(clean) > 0:
            last = clean.iloc[-1]
            latest_value = float(last) if not pd.isna(last) else None
            pcts = clean.quantile([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]).to_dict()
            percentiles = {f"p{int(k*100)}": round(float(v), 6) for k, v in pcts.items()}
            percentiles["min"] = round(float(clean.min()), 6)
            percentiles["max"] = round(float(clean.max()), 6)
            percentiles["mean"] = round(float(clean.mean()), 6)
            percentiles["std"] = round(float(clean.std()), 6)
            # Current value percentile rank
            if latest_value is not None:
                rank = (clean < latest_value).sum() / len(clean) * 100
                percentiles["current_pct"] = round(float(rank), 1)

    # Compute decay half-life from effectiveness IC values
    # positive = decay hours, -1 = IC strengthens (persistent/trend factor), None = insufficient data
    decay_half_life = None
    if results and len(results) >= 3:
        import numpy as np
        fp_hours_map = {"1h": 1, "4h": 4, "12h": 12, "24h": 24}
        points = []
        for fp_label, m in results.items():
            abs_ic = abs(m.get("ic_mean", 0))
            if abs_ic > 1e-8 and fp_label in fp_hours_map:
                points.append((fp_hours_map[fp_label], abs_ic))
        if len(points) >= 3:
            points.sort(key=lambda p: p[0])
            if points[-1][1] >= points[0][1]:
                decay_half_life = -1  # IC strengthens
            else:
                t_arr = np.array([p[0] for p in points], dtype=float)
                ln_ic = np.log(np.array([p[1] for p in points], dtype=float))
                t_mean, ln_mean = t_arr.mean(), ln_ic.mean()
                num = ((t_arr - t_mean) * (ln_ic - ln_mean)).sum()
                den = ((t_arr - t_mean) ** 2).sum()
                if abs(den) > 1e-12:
                    slope = num / den
                    if slope < 0:
                        hl = int(round(np.log(2) / (-slope)))
                        if 1 <= hl <= 720:
                            decay_half_life = hl
                        else:
                            decay_half_life = -1
                    else:
                        decay_half_life = -1

    return {
        "status": "ok",
        "expression": req.expression,
        "symbol": req.symbol,
        "exchange": req.exchange,
        "latest_value": latest_value,
        "percentiles": percentiles,
        "effectiveness": results,
        "decay_half_life_hours": decay_half_life,
    }


class ValidateExpressionRequest(BaseModel):
    expression: str


@router.post("/validate-expression")
async def validate_expression(req: ValidateExpressionRequest):
    """Quick syntax check for an expression."""
    ok, err = factor_expression_engine.validate(req.expression)
    return {"valid": ok, "error": err if not ok else None}


@router.get("/expression-functions")
async def list_expression_functions():
    """Return available functions grouped by category with metadata."""
    return {
        "functions": factor_expression_engine.FUNCTION_DOCS,
        "grouped": factor_expression_engine.get_registry_grouped(),
        "total": len(FUNCTION_REGISTRY),
    }
