"""Self-consistency gate for LLM trading decisions.

Verified research (arXiv 2505.06120): long-running LLM degradation is mostly
an increase in run-to-run VARIANCE, not a loss of aptitude. So for decisions
that move money, sample the same prompt N times (temperature > 0) and only
act when the direction agrees. Divergent samples are the model telling us it
is unsure - the conservative resolution is hold, with the divergence recorded
in the decision log.

The primary sample stays authoritative for order parameters (portion,
leverage, TP/SL); later samples only vote on the *direction*. A later sample
can veto a trade but never create one the primary did not propose.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ENV_VAR = "AI_DECISION_SELF_CONSISTENCY_N"
DEFAULT_SAMPLES = 2
MAX_SAMPLES = 3


def configured_samples() -> int:
    """How many LLM samples to draw per decision cycle (1 disables the gate)."""
    raw = os.getenv(ENV_VAR, "")
    try:
        value = int(raw) if raw.strip() else DEFAULT_SAMPLES
    except ValueError:
        value = DEFAULT_SAMPLES
    return min(max(value, 1), MAX_SAMPLES)


def _ops_by_symbol(sample: List[Dict[str, Any]]) -> Dict[str, str]:
    ops: Dict[str, str] = {}
    for entry in sample:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").upper()
        if symbol:
            ops[symbol] = str(entry.get("operation") or "").lower()
    return ops


def reconcile_decision_samples(
    samples: List[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Merge N decision samples into one action list.

    Per symbol: all samples agree on the operation -> keep the primary entry;
    any divergence on an acting operation (buy/sell/close) -> downgrade to
    hold. Symbols absent from a sample count as hold (the schema says HOLD
    entries may be omitted), so absence vetoes too."""
    if not samples:
        return []
    primary = samples[0]
    if len(samples) == 1:
        return primary

    other_ops = [_ops_by_symbol(sample) for sample in samples[1:]]
    reconciled: List[Dict[str, Any]] = []
    for entry in primary:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").upper()
        operation = str(entry.get("operation") or "").lower()
        votes = [ops.get(symbol, "hold") for ops in other_ops]

        if operation in ("buy", "sell", "close") and any(v != operation for v in votes):
            logger.info(
                "[SelfConsistency] %s: primary=%s, other samples=%s -> hold",
                symbol, operation, votes,
            )
            reconciled.append(
                {
                    "operation": "hold",
                    "symbol": entry.get("symbol"),
                    "target_portion_of_balance": 0,
                    "reason": (
                        f"自一致性检验未通过：{len(samples)} 次采样方向不一致"
                        f"（{operation} vs {'/'.join(votes)}）。方向分歧说明该决策置信度不足，"
                        "按保守原则观望。"
                    ),
                    "trading_strategy": (
                        "Self-consistency gate: divergent samples imply low decision "
                        "confidence; standing aside instead of guessing."
                    ),
                    "_prompt_snapshot": entry.get("_prompt_snapshot"),
                    "_reasoning_snapshot": entry.get("_reasoning_snapshot"),
                    "_raw_decision_text": entry.get("_raw_decision_text"),
                    "_self_consistency": {
                        "agreed": False,
                        "samples": len(samples),
                        "operations": [operation, *votes],
                    },
                }
            )
        else:
            kept = dict(entry)
            kept["_self_consistency"] = {"agreed": True, "samples": len(samples)}
            reconciled.append(kept)
    return reconciled
