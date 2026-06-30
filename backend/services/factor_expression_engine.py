"""
Factor Expression Engine

Safely evaluates user/AI-submitted factor expressions against K-line data.
Uses asteval (safe expression evaluator) + pandas-ta (130+ TA indicators).

Example expressions:
    EMA(close, 7) / EMA(close, 21) - 1
    RSI(close, 14) - 50
    ATR(high, low, close, 14) / close
    TS_CORR(close, volume, 20)
    IF(ROC(close,5) > 0, 1, -1)
"""

import logging
import numpy as np
import pandas as pd
from asteval import Interpreter
from typing import Dict, List, Optional, Tuple

from services.factor_expression.definitions import (
    CATEGORY_LABELS,
    FACTOR_DEFINITIONS,
    FUNCTION_REGISTRY,
)
from services.factor_expression.registry import build_functions

logger = logging.getLogger(__name__)

__all__ = [
    "CATEGORY_LABELS",
    "FACTOR_DEFINITIONS",
    "FUNCTION_REGISTRY",
    "FactorExpressionEngine",
    "factor_expression_engine",
]


class FactorExpressionEngine:
    """Evaluate factor expressions safely using asteval + pandas-ta."""

    # Legacy compat — FUNCTION_DOCS derived from FUNCTION_REGISTRY
    FUNCTION_DOCS = {
        name: f"{meta['signature']} - {meta['description']}"
        for name, meta in FUNCTION_REGISTRY.items()
    }

    def __init__(self):
        self._ta = None

    def _ensure_ta(self):
        if self._ta is None:
            import pandas_ta as ta

            self._ta = ta

    def _to_series(self, x) -> pd.Series:
        if isinstance(x, pd.Series):
            return x
        if isinstance(x, pd.DataFrame):
            return x.iloc[:, 0]
        return pd.Series(x, dtype=float)

    def _safe_float(self, x):
        """Ensure Series is float dtype (fixes bool/int ufunc issues)."""
        sr = self._to_series(x)
        if sr.dtype == bool or sr.dtype == object:
            return sr.astype(float)
        return sr

    def _build_functions(self, df: pd.DataFrame) -> Dict:
        """Build function dict bound to the given DataFrame context."""
        _ = df
        self._ensure_ta()
        return build_functions(self._ta, self._to_series, self._safe_float)

    def get_registry_grouped(self) -> Dict:
        """Return FUNCTION_REGISTRY grouped by category with labels."""
        groups = {}
        for name, meta in FUNCTION_REGISTRY.items():
            cat = meta["category"]
            if cat not in groups:
                labels = CATEGORY_LABELS.get(cat, {"en": cat, "zh": cat})
                groups[cat] = {
                    "label": labels["en"],
                    "label_zh": labels["zh"],
                    "functions": [],
                }
            groups[cat]["functions"].append({"name": name, **meta})
        return groups

    def validate(self, expression: str) -> Tuple[bool, str]:
        """Validate expression syntax without executing. Returns (ok, error_msg)."""
        if not expression or not expression.strip():
            return False, "Expression is empty"
        if len(expression) > 500:
            return False, "Expression too long (max 500 chars)"

        try:
            aeval = Interpreter(minimal=True)
            aeval.parse(expression)
            if aeval.error:
                errors = "; ".join(str(e.get_error()[1]) for e in aeval.error)
                return False, f"Syntax error: {errors}"
        except SyntaxError as e:
            return False, f"Syntax error: {str(e) or 'invalid expression'}"
        except Exception as e:
            return False, f"Parse error: {str(e)}"
        return True, ""

    def execute(
        self, expression: str, klines: List[Dict]
    ) -> Tuple[Optional[pd.Series], str]:
        """
        Execute expression against K-line data.
        Returns (result_series, error_msg). result_series is None on error.
        """
        ok, err = self.validate(expression)
        if not ok:
            return None, err

        if not klines or len(klines) < 10:
            return None, "Insufficient K-line data (need at least 10 bars)"

        # Build DataFrame from klines
        df = pd.DataFrame(klines)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Create safe interpreter
        aeval = Interpreter(minimal=True)

        # Inject K-line columns as variables
        aeval.symtable["open"] = df["open"]
        aeval.symtable["high"] = df["high"]
        aeval.symtable["low"] = df["low"]
        aeval.symtable["close"] = df["close"]
        aeval.symtable["volume"] = df["volume"]

        # Inject TA functions
        for name, func in self._build_functions(df).items():
            aeval.symtable[name] = func

        # Inject numpy for arithmetic
        aeval.symtable["np"] = np

        # Execute
        try:
            result = aeval(expression)
        except Exception as e:
            return None, f"Execution error: {str(e)}"

        if aeval.error:
            errors = "; ".join(str(e.get_error()[1]) for e in aeval.error)
            return None, f"Evaluation error: {errors}"

        if result is None:
            return None, "Expression returned None"

        # Convert to Series
        if isinstance(result, pd.Series):
            # Ensure float dtype for downstream IC calculation
            if result.dtype == bool:
                result = result.astype(float)
            return result, ""
        if isinstance(result, pd.DataFrame):
            col = result.iloc[:, 0]
            if col.dtype == bool:
                col = col.astype(float)
            return col, ""
        if isinstance(result, (np.ndarray, list)):
            return pd.Series(result, dtype=float), ""
        if isinstance(result, (int, float)):
            return pd.Series([result] * len(df), dtype=float), ""

        return None, f"Unexpected result type: {type(result).__name__}"

    def evaluate_ic(
        self,
        expression: str,
        klines: List[Dict],
        forward_periods: Dict[str, int] = None,
    ) -> Tuple[Optional[Dict], str]:
        """
        Evaluate expression and compute IC/ICIR/win_rate for each forward period.
        Returns (results_dict, error_msg).
        """
        if forward_periods is None:
            forward_periods = {"1h": 1, "4h": 4, "12h": 12, "24h": 24}

        series, err = self.execute(expression, klines)
        if series is None:
            return None, err

        closes = pd.to_numeric(pd.DataFrame(klines)["close"], errors="coerce")
        factor_vals = series.values.astype(float)
        close_vals = closes.values
        n = len(factor_vals)

        from scipy.stats import spearmanr

        results = {}
        for fp_label, fp_offset in forward_periods.items():
            if fp_offset >= n - 10:
                continue

            aligned_fv, aligned_rt = [], []
            for i in range(n - fp_offset):
                fv = factor_vals[i]
                cv = close_vals[i]
                if pd.isna(fv) or pd.isna(cv) or cv == 0:
                    continue
                ret = (close_vals[i + fp_offset] - cv) / cv
                aligned_fv.append(fv)
                aligned_rt.append(ret)

            if len(aligned_fv) < 10:
                continue

            fv_arr = np.array(aligned_fv)
            rt_arr = np.array(aligned_rt)

            ic, _ = spearmanr(fv_arr, rt_arr)
            ic = float(ic) if not np.isnan(ic) else 0.0

            # Rolling IC for ICIR
            window = min(20, max(5, len(aligned_fv) // 4))
            ics = []
            if window >= 5 and len(aligned_fv) >= window * 2:
                for i in range(len(aligned_fv) - window + 1):
                    c, _ = spearmanr(fv_arr[i : i + window], rt_arr[i : i + window])
                    if not np.isnan(c):
                        ics.append(c)

            ic_mean = float(np.mean(ics)) if ics else ic
            ic_std = float(np.std(ics)) if ics else 0.0
            icir = ic_mean / ic_std if ic_std > 1e-8 else 0.0

            signs_match = np.sign(fv_arr) == np.sign(rt_arr)
            win_rate = float(signs_match.mean())

            results[fp_label] = {
                "ic_mean": round(ic_mean, 6),
                "ic_std": round(ic_std, 6),
                "icir": round(icir, 4),
                "win_rate": round(win_rate, 4),
                "sample_count": len(aligned_fv),
            }

        if not results:
            return None, "Not enough aligned data for IC calculation"

        return results, ""


# Singleton
factor_expression_engine = FactorExpressionEngine()
