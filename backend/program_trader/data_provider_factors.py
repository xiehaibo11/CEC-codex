"""Factor access helpers for Program Trader data providers."""

from typing import Any, Dict, List, Callable

from sqlalchemy.orm import Session


def compute_factor_snapshot(
    db: Session,
    symbol: str,
    factor_name: str,
    period: str,
    exchange: str,
    klines_loader: Callable[[str, int], List[Dict[str, Any]]],
    include_effectiveness: bool = True,
) -> Dict[str, Any]:
    """Compute a factor snapshot from K-lines plus optional effectiveness metrics."""
    from services.factor_resolver import (
        compute_factor_value,
        resolve_factor_definition,
        extract_factor_expression,
    )
    from sqlalchemy import text as sa_text

    result = {
        "factor_name": factor_name,
        "symbol": symbol,
        "period": period,
        "value": None,
    }

    factor = resolve_factor_definition(db, factor_name)
    if not factor:
        result["error"] = f"Factor '{factor_name}' not found"
        return result

    result["id"] = factor.get("id")
    result["expression"] = extract_factor_expression(factor)
    result["description"] = factor.get("description") or ""
    result["category"] = factor.get("category")

    try:
        klines = klines_loader(period, 500)
        if klines and len(klines) >= 30:
            value, _, err = compute_factor_value(
                db=db,
                factor_name=factor_name,
                symbol=symbol,
                period=period,
                exchange=exchange,
                klines=klines,
            )
            if value is not None:
                result["value"] = value
            elif err:
                result["error"] = err
    except Exception as exc:
        result["error"] = str(exc)
        return result

    if include_effectiveness:
        row = db.execute(sa_text(
            "SELECT ic_mean, icir, win_rate, decay_half_life "
            "FROM factor_effectiveness "
            "WHERE factor_name = :fn AND symbol = :sym AND exchange = :ex "
            "AND period = '1h' AND forward_period = '4h' "
            "ORDER BY created_at DESC LIMIT 1"
        ), {"fn": factor_name, "sym": symbol, "ex": exchange}).fetchone()

        if row:
            result["ic"] = round(float(row[0]), 4) if row[0] is not None else None
            result["icir"] = round(float(row[1]), 2) if row[1] is not None else None
            result["win_rate"] = round(float(row[2]), 2) if row[2] is not None else None
            result["decay_half_life_hours"] = int(row[3]) if row[3] is not None else None

    return result


class FactorDataMixin:
    def get_factor(self, symbol: str, factor_name: str, period: str = "5m") -> Dict[str, Any]:
        """Get factor value and effectiveness for a symbol on a specific K-line period."""
        from services.market_data import get_kline_data

        result = compute_factor_snapshot(
            db=self.db,
            symbol=symbol,
            factor_name=factor_name,
            period=period,
            exchange=self.exchange,
            klines_loader=lambda requested_period, count: get_kline_data(
                symbol,
                market=self._get_market_param(),
                period=requested_period,
                count=count,
                environment=self.environment,
                persist=False,
            ) or [],
            include_effectiveness=True,
        )

        self._log_query("get_factor", {"symbol": symbol, "factor_name": factor_name, "period": period}, result)
        return result

    def get_factor_ranking(self, symbol: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top factors ranked by |ICIR| for a symbol."""
        from database.models import CustomFactor
        from sqlalchemy import text as sa_text

        results = []
        try:
            rows = self.db.execute(sa_text(
                "SELECT DISTINCT ON (factor_name) factor_name, ic_mean, icir, win_rate, decay_half_life "
                "FROM factor_effectiveness "
                "WHERE symbol = :sym AND exchange = :ex AND icir IS NOT NULL "
                "AND period = '1h' AND forward_period = '4h' "
                "ORDER BY factor_name, created_at DESC"
            ), {"sym": symbol, "ex": self.exchange}).fetchall()

            factor_names = [row[0] for row in rows]
            factors = self.db.query(CustomFactor).filter(
                CustomFactor.name.in_(factor_names),
                CustomFactor.is_active == True,
            ).all()
            factor_meta = {factor.name: factor for factor in factors}

            ranked = []
            for row in rows:
                factor_name = row[0]
                factor = factor_meta.get(factor_name)
                ranked.append({
                    "factor_name": factor_name,
                    "id": factor.id if factor else None,
                    "expression": factor.expression if factor else None,
                    "description": (factor.description or "") if factor else "",
                    "ic": round(float(row[1]), 4) if row[1] is not None else None,
                    "icir": round(float(row[2]), 2) if row[2] is not None else None,
                    "win_rate": round(float(row[3]), 2) if row[3] is not None else None,
                    "decay_half_life_hours": int(row[4]) if row[4] is not None else None,
                })
            ranked.sort(key=lambda item: abs(item["icir"] or 0), reverse=True)
            results = ranked[:top_n]

        except Exception as exc:
            results = [{"error": str(exc)}]

        self._log_query("get_factor_ranking", {"symbol": symbol, "top_n": top_n}, results)
        return results
