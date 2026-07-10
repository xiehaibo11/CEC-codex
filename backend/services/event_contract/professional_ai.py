"""Single professional AI reviewer for production event-contract decisions."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from services.ai_decision_service import (
    build_llm_headers,
    build_llm_payload,
    detect_api_format,
    get_max_tokens,
)

logger = logging.getLogger(__name__)

REQUIRED_TIMEFRAMES = ("4h", "30m", "15m", "10m", "5m")


def build_professional_ai_prompt(
    *,
    snapshot: Dict[str, Any],
    rule_analysis: Dict[str, Any],
    config: Dict[str, Any],
) -> str:
    """Build a no-future-data prompt with an explicit JSON response contract."""
    payload = {
        "task": "Professional multi-timeframe event-contract analysis",
        "symbol": config.get("symbol", "BTC"),
        "expiry_minutes": config.get("expiry_minutes", 5),
        "required_timeframes": list(REQUIRED_TIMEFRAMES),
        "timeframe_snapshot": snapshot,
        "rule_prefilter": {
            "direction": rule_analysis.get("final_direction", "hold"),
            "allow_trade": bool(rule_analysis.get("allow_trade")),
            "confidence": rule_analysis.get("confidence", 0),
            "blocked_reasons": rule_analysis.get("blocked_reasons", []),
        },
        "output_schema": {
            "direction": "long|short|hold",
            "confidence": "number 0-100",
            "timeframe_analysis": {period: "short evidence string" for period in REQUIRED_TIMEFRAMES},
            "risk_flags": ["short strings"],
            "invalid_conditions": ["conditions that invalidate the next entry"],
            "reason": "short explanation based only on supplied data",
        },
    }
    return (
        "Analyze only the supplied completed candles and features. Do not use future prices, "
        "external data, or unstated assumptions. The signal is evaluated after the current bar "
        "closes and, if approved, executes on the next bar open. Return JSON only. If any required "
        "timeframe is missing or conflicts, return hold. The 5m/10m contract expiry is fixed by "
        "the request; never invent a different expiry.\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def parse_professional_ai_response(raw_text: str) -> Dict[str, Any]:
    """Parse and validate one professional review; invalid output fails closed."""
    clean = str(raw_text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"```$", "", clean).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Professional AI returned no JSON object")
    try:
        data = json.loads(clean[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Professional AI returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Professional AI response must be a JSON object")

    timeframe_analysis = data.get("timeframe_analysis")
    if not isinstance(timeframe_analysis, dict) or any(
        timeframe not in timeframe_analysis for timeframe in REQUIRED_TIMEFRAMES
    ):
        raise ValueError("Professional AI timeframe_analysis must include 4h, 30m, 15m, 10m and 5m")

    direction = str(data.get("direction") or "hold").strip().lower()
    if direction not in {"long", "short", "hold"}:
        raise ValueError("Professional AI direction must be long, short or hold")
    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Professional AI confidence must be numeric") from exc
    if confidence < 0 or confidence > 100:
        raise ValueError("Professional AI confidence must be between 0 and 100")

    def strings(key: str) -> list[str]:
        value = data.get(key) or []
        if not isinstance(value, list):
            return [str(value)]
        return [str(item) for item in value]

    return {
        "direction": direction,
        "confidence": round(confidence, 2),
        "timeframe_analysis": {
            timeframe: str(timeframe_analysis[timeframe])
            for timeframe in REQUIRED_TIMEFRAMES
        },
        "risk_flags": strings("risk_flags"),
        "invalid_conditions": strings("invalid_conditions"),
        "reason": str(data.get("reason") or ""),
    }


class EventContractProfessionalAiMixin:
    """Production-only single-reviewer AI gate.

    The deterministic rule engine remains the final risk authority. This
    reviewer can confirm a direction, or veto it; it cannot change expiry,
    leverage, margin, or the execution mode. Network and parse failures are
    deliberately surfaced to the caller so the prediction can be converted to
    a visible HOLD rather than inventing a synthetic AI result.
    """

    def _call_professional_ai(
        self,
        db: Session,
        cfg: Dict[str, Any],
        snapshot: Dict[str, Any],
        rule_analysis: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        llm = self._resolve_llm_config(db, cfg)
        api_format = llm.get("api_format") or detect_api_format(llm["base_url"])[1] or "openai"
        headers = build_llm_headers(api_format, llm["api_key"], llm["base_url"])
        prompt = build_professional_ai_prompt(
            snapshot=snapshot,
            rule_analysis=rule_analysis,
            config=cfg,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the professional event-contract trading analyst. "
                    "Use only the completed multi-timeframe data supplied by the user message. "
                    "Return JSON matching the requested schema and never fabricate missing data."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        payload = build_llm_payload(
            model=llm["model"],
            messages=messages,
            api_format=api_format,
            max_tokens=min(max(get_max_tokens(llm["model"]), 1200), 4000),
            temperature=min(float(cfg.get("ai_temperature") or 0.2), 0.2),
        )
        endpoints = self._build_llm_endpoints(llm["base_url"], llm["model"], api_format)
        if not endpoints:
            raise ValueError("Professional AI failed: invalid LLM base_url")

        last_error = ""
        retries = max(1, int(cfg.get("ai_max_retries") or 1))
        for endpoint in endpoints:
            for attempt in range(retries):
                try:
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=int(cfg.get("llm_timeout_seconds") or 180),
                        # Do not repeat the legacy consensus client's insecure
                        # verify=False behavior in the production gate.
                        verify=True,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        raw_text = self._extract_llm_text(result, api_format)
                        review = parse_professional_ai_response(raw_text)
                        return review, {
                            "account_id": llm.get("account_id"),
                            "account_name": llm.get("account_name"),
                            "model": llm.get("model"),
                            "provider": llm.get("provider"),
                            "api_format": api_format,
                        }

                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if response.status_code == 429 and attempt < retries - 1:
                        time.sleep(2**attempt)
                        continue
                    break
                except requests.Timeout:
                    last_error = "request timed out"
                except requests.RequestException as exc:
                    last_error = str(exc)
                except (ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                    break

        logger.warning(
            "Professional event AI failed for %s %s using %s: %s",
            cfg.get("exchange"),
            cfg.get("symbol"),
            llm.get("model"),
            last_error,
        )
        raise ValueError(f"Professional AI failed: {last_error or 'request failed'}")

    def _apply_professional_ai_review(
        self,
        *,
        result: Dict[str, Any],
        cfg: Dict[str, Any],
        latest: Dict[str, Any],
        review: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply an AI review as a fail-closed confirmation/veto gate."""
        metadata = metadata or {}
        ai_consensus = dict(result.get("ai_consensus") or {})
        blocked_reasons = list(result.get("veto_reasons") or [])
        entry_reasons = list(result.get("entry_warning") and [result["entry_warning"]] or [])
        snapshot = cfg.get("_production_mtf_snapshot") or {}
        aligned = snapshot.get("aligned_direction", "hold")
        conflict = bool(snapshot.get("conflict", True))
        review_payload: Dict[str, Any] = dict(review or {})
        if metadata:
            review_payload["model"] = metadata.get("model")
            review_payload["account_name"] = metadata.get("account_name")
        if error:
            review_payload = {"status": "unavailable", "error": str(error)}
        else:
            review_payload["status"] = "received"

        ai_consensus.update(
            {
                "professional_ai_enabled": True,
                "professional_ai_status": review_payload.get("status"),
                "professional_ai_direction": review_payload.get("direction"),
                "professional_ai_confidence": review_payload.get("confidence", 0),
                "professional_ai_model": metadata.get("model"),
                "professional_ai_account_name": metadata.get("account_name"),
                "professional_ai_reason": review_payload.get("reason", ""),
                "professional_ai_timeframes": review_payload.get("timeframe_analysis", {}),
            }
        )
        result["professional_ai_review"] = review_payload
        result["ai_participated"] = bool(not error)
        result["ai_model"] = metadata.get("model")
        result["ai_account_name"] = metadata.get("account_name")

        reason: Optional[str] = None
        rule_direction = result.get("best_action")
        if error:
            reason = f"专业AI不可用，已降级为 HOLD：{error}"
        elif not review:
            reason = "专业AI未返回有效结果，已降级为 HOLD"
        elif conflict or aligned not in ("long", "short"):
            reason = "专业多周期方向未一致（4H/30M/15M/10M/5M），等待下一根收盘信号"
        elif not result.get("allow_trade") or rule_direction not in ("long", "short"):
            reason = "规则预筛未形成可交易信号，专业AI不得单独开仓"
        elif review.get("direction") != rule_direction:
            reason = (
                f"专业AI方向 {review.get('direction')} 与规则方向 {rule_direction} 不一致，已拒绝"
            )
        elif float(review.get("confidence") or 0) < float(cfg.get("professional_ai_min_confidence") or 75):
            reason = (
                f"专业AI置信度 {float(review.get('confidence') or 0):.2f} < "
                f"{float(cfg.get('professional_ai_min_confidence') or 75):.2f}，已拒绝"
            )

        if reason:
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
            entry_reasons.append(reason)
            result.update(
                {
                    "allow_trade": False,
                    "best_action": "hold",
                    "signal_type": "hold_signal",
                    "event_signal_type": "HOLD",
                    "entry_warning": "；".join(item for item in entry_reasons if item),
                    "reason": f"{result.get('reason') or ''}；{reason}".strip("；"),
                }
            )
        elif review:
            # The final confidence is never higher than either decision layer.
            result["confidence"] = round(
                min(float(result.get("confidence") or 0), float(review.get("confidence") or 0)), 2
            )

        result["veto_reasons"] = blocked_reasons
        result["ai_consensus"] = ai_consensus
        event_signal = self._build_event_signal(
            cfg,
            latest,
            result["best_action"],
            bool(result.get("allow_trade")),
            result["signal_type"],
            float(result.get("confidence") or 0),
            float(result.get("signal_strength") or 0),
            {
                "long": float(result.get("long_5m_probability") or 0),
                "short": float(result.get("short_5m_probability") or 0),
                "hold": float(result.get("hold_probability") or 0),
            },
            {
                "fake_breakout": float(result.get("fake_breakout_risk") or 0),
                "bull_trap": float((result.get("ai_consensus") or {}).get("bull_trap_risk") or 0),
                "bear_trap": float((result.get("ai_consensus") or {}).get("bear_trap_risk") or 0),
                "trap": float(result.get("trap_risk") or 0),
                "range": float(result.get("range_risk") or 0),
            },
            blocked_reasons,
            result.get("factors") or [],
            ai_consensus,
        )
        event_signal["professional_ai_review"] = review_payload
        result["event_signal"] = event_signal
        result["event_signal_type"] = event_signal["signal_type"]
        return result
