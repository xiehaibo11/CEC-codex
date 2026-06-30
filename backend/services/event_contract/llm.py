"""LLM-backed 30-role consensus for event-contract candidates."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from database.models import Account
from services.ai_decision_service import (
    _extract_text_from_message,
    build_chat_completion_endpoints,
    build_llm_headers,
    build_llm_payload,
    detect_api_format,
    get_max_tokens,
    strip_thinking_tags,
)
from services.event_contract.constants import DEFAULT_API_KEYS, EVENT_AI_NAMES


logger = logging.getLogger(__name__)


class EventContractLlmMixin:
    def _call_llm_consensus(
        self,
        db: Session,
        cfg: Dict[str, Any],
        history: List[Dict[str, Any]],
        rule_analysis: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        llm = self._resolve_llm_config(db, cfg)
        api_format = llm.get("api_format") or detect_api_format(llm["base_url"])[1] or "openai"
        headers = build_llm_headers(api_format, llm["api_key"], llm["base_url"])
        from services.event_contract.reviewer_expertise import expertise_summary_for_prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a 30-person quant trading panel. Each reviewer is a domain specialist "
                    "with a distinct discipline (see Reviewer playbook). Stay in role: each reviewer "
                    "must reason from its own focus area and emit risk_flags consistent with its discipline. "
                    "Evaluate ONLY the data supplied in the prompt. Do not use future prices, external live data, "
                    "or unstated assumptions. Critical risk gates (Fake Breakout, Trap Detection, Market Regime, "
                    "Final Risk) MUST hold when their signature risk thresholds are breached. Return valid JSON only.\n\n"
                    + expertise_summary_for_prompt()
                ),
            },
            {"role": "user", "content": self._build_llm_consensus_prompt(history, cfg, rule_analysis)},
        ]
        payload = build_llm_payload(
            model=llm["model"],
            messages=messages,
            api_format=api_format,
            max_tokens=min(max(get_max_tokens(llm["model"]), 4000), 12000),
            temperature=cfg["ai_temperature"],
        )
        endpoints = self._build_llm_endpoints(llm["base_url"], llm["model"], api_format)
        if not endpoints:
            raise ValueError("AI consensus failed: invalid LLM base_url")

        last_error = ""
        for endpoint in endpoints:
            for attempt in range(cfg["ai_max_retries"]):
                try:
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=cfg["llm_timeout_seconds"],
                        verify=False,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        raw_text = self._extract_llm_text(result, api_format)
                        decisions = self._parse_llm_decisions(raw_text, llm)
                        return decisions, {
                            "account_id": llm.get("account_id"),
                            "account_name": llm["account_name"],
                            "model": llm["model"],
                            "provider": llm.get("provider"),
                            "api_format": api_format,
                        }

                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if response.status_code == 429 and attempt < cfg["ai_max_retries"] - 1:
                        time.sleep((2**attempt) + random.uniform(0, 1))
                        continue
                    break
                except requests.Timeout:
                    last_error = f"timeout after {cfg['llm_timeout_seconds']}s"
                except requests.RequestException as exc:
                    last_error = str(exc)
                except (ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                    raise ValueError(f"AI consensus failed: {last_error}")

        logger.warning(
            "Event contract AI consensus failed for %s %s using %s: %s",
            cfg["exchange"],
            cfg["symbol"],
            llm["model"],
            last_error,
        )
        raise ValueError(f"AI consensus failed: {last_error or 'request failed'}")

    def _resolve_llm_config(self, db: Session, cfg: Dict[str, Any]) -> Dict[str, Any]:
        if cfg.get("ai_trader_id"):
            account = db.query(Account).filter(
                Account.id == cfg["ai_trader_id"],
                Account.account_type == "AI",
                Account.is_active == "true",
                Account.is_deleted != True,
            ).first()
            if not account:
                raise ValueError(f"AI Trader {cfg['ai_trader_id']} not found or inactive")
            if self._is_default_api_key(account.api_key):
                raise ValueError(f"AI Trader {account.name} has no valid API key configured")
            return self._account_llm_config(account)

        account = db.query(Account).filter(
            Account.account_type == "AI",
            Account.is_active == "true",
            Account.is_deleted != True,
        ).order_by(Account.id).all()
        for candidate in account:
            if not self._is_default_api_key(candidate.api_key):
                return self._account_llm_config(candidate)

        try:
            from services.hyper_ai_service import get_llm_config

            llm_config = get_llm_config(db)
            if llm_config.get("configured") and not self._is_default_api_key(llm_config.get("api_key")):
                return {
                    "account_id": None,
                    "account_name": "Hyper AI LLM",
                    "provider": llm_config.get("provider"),
                    "model": llm_config.get("model"),
                    "base_url": llm_config.get("base_url"),
                    "api_key": llm_config.get("api_key"),
                    "api_format": llm_config.get("api_format") or "openai",
                }
        except Exception as exc:
            logger.warning("Failed to load Hyper AI LLM config for event backtest: %s", exc)

        raise ValueError(
            "AI-confirmed backtest requires a valid AI Trader API key or Hyper AI LLM configuration. "
            "No AI result was generated."
        )

    def _account_llm_config(self, account: Account) -> Dict[str, Any]:
        _, api_format = detect_api_format(account.base_url)
        return {
            "account_id": account.id,
            "account_name": account.name,
            "provider": "ai_trader",
            "model": account.model,
            "base_url": account.base_url,
            "api_key": account.api_key,
            "api_format": api_format or "openai",
        }

    def _is_default_api_key(self, api_key: Optional[str]) -> bool:
        return api_key in DEFAULT_API_KEYS

    def _build_llm_endpoints(self, base_url: str, model: str, api_format: str) -> List[str]:
        endpoint, detected_format = detect_api_format(base_url)
        if (api_format or detected_format) == "anthropic":
            return [endpoint] if endpoint else []
        return build_chat_completion_endpoints(base_url, model)

    def _build_llm_consensus_prompt(
        self,
        history: List[Dict[str, Any]],
        cfg: Dict[str, Any],
        rule_analysis: Dict[str, Any],
    ) -> str:
        latest = history[-1]
        recent = [
            {
                "time": self._to_iso(self._decision_timestamp(k, cfg)),
                "open": round(k["open"], 6),
                "high": round(k["high"], 6),
                "low": round(k["low"], 6),
                "close": round(k["close"], 6),
                "volume": round(k["volume"], 4),
            }
            for k in history[-40:]
        ]
        payload = {
            "task": "5-minute event contract direction review",
            "symbol": cfg["symbol"],
            "exchange": cfg["exchange"],
            "period": cfg["period"],
            "entry_time": self._to_iso(self._decision_timestamp(latest, cfg)),
            "entry_price": latest["close"],
            "expiry_minutes": cfg["expiry_minutes"],
            "rule_prefilter": {
                "final_direction": rule_analysis["final_direction"],
                "allow_trade": rule_analysis["allow_trade"],
                "signal_strength": rule_analysis["signal_strength"],
                "confidence": rule_analysis["confidence"],
                "long_votes": rule_analysis["ai_consensus"]["long_votes"],
                "short_votes": rule_analysis["ai_consensus"]["short_votes"],
                "hold_votes": rule_analysis["ai_consensus"]["hold_votes"],
                "market_state": rule_analysis["market_state"],
                "trap_risk": rule_analysis["trap_risk"],
                "fake_breakout_risk": rule_analysis["fake_breakout_risk"],
                "range_risk": rule_analysis["range_risk"],
                "blocked_reasons": rule_analysis["blocked_reasons"],
            },
            "factors": rule_analysis["factors"],
            "recent_klines_oldest_to_newest": recent,
            "required_ai_reviewers": EVENT_AI_NAMES,
            "output_schema": {
                "decisions": [
                    {
                        "ai_name": "one exact name from required_ai_reviewers",
                        "direction": "long|short|hold",
                        "confidence": "number 0-100",
                        "reason": "short reason using supplied K-line/factor evidence only",
                        "risk_flags": ["short strings"],
                        "evidence": ["short strings"],
                        "invalid_conditions": ["short strings, empty if none"],
                    }
                ]
            },
        }
        return (
            "Return a JSON object with exactly 30 decisions, one for each required_ai_reviewers item and no extra text. "
            "A long decision means expiry close is expected above entry price; short means below; hold means no valid edge. "
            "Critical risk reviewers should hold when fake breakout, trap, range-middle, or data quality risk is too high.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
        )

    def _extract_llm_text(self, result: Dict[str, Any], api_format: str) -> str:
        if api_format == "anthropic":
            return _extract_text_from_message(result.get("content"))
        choices = result.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        text = _extract_text_from_message(message.get("content"))
        if not text:
            text = _extract_text_from_message(message.get("reasoning_content"))
        return text

    def _parse_llm_decisions(self, raw_text: str, llm: Dict[str, Any]) -> List[Dict[str, Any]]:
        clean_text, _ = strip_thinking_tags(raw_text or "")
        clean_text = clean_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?", "", clean_text, flags=re.IGNORECASE).strip()
            clean_text = re.sub(r"```$", "", clean_text).strip()
        start = clean_text.find("{")
        end = clean_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI returned no JSON object")

        data = json.loads(clean_text[start : end + 1])
        raw_decisions = data.get("decisions") or data.get("ai_decisions")
        if not isinstance(raw_decisions, list) or len(raw_decisions) < 30:
            raise ValueError("AI returned fewer than 30 reviewer decisions")

        decisions_by_name = {
            str(item.get("ai_name", "")).strip(): item
            for item in raw_decisions
            if isinstance(item, dict)
        }
        normalized: List[Dict[str, Any]] = []
        for idx, expected_name in enumerate(EVENT_AI_NAMES):
            item = decisions_by_name.get(expected_name)
            if item is None and idx < len(raw_decisions) and isinstance(raw_decisions[idx], dict):
                item = raw_decisions[idx]
            if item is None:
                raise ValueError(f"AI omitted reviewer decision: {expected_name}")

            direction = str(item.get("direction") or "hold").lower().strip()
            if direction not in ("long", "short", "hold"):
                direction = "hold"
            try:
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                confidence = 0

            normalized.append(
                {
                    "ai_name": expected_name,
                    "source": "llm_ai",
                    "model": llm.get("model"),
                    "account_name": llm.get("account_name"),
                    "direction": direction,
                    "confidence": round(max(0, min(100, confidence)), 2),
                    "reason": str(item.get("reason") or "").strip()[:500],
                    "risk_flags": self._string_list(item.get("risk_flags")),
                    "evidence": self._string_list(item.get("evidence")),
                    "timeframes": self._string_list(item.get("timeframes")) or [cfg_period for cfg_period in ("1m", "3m", "5m", "15m")],
                    "invalid_conditions": self._string_list(item.get("invalid_conditions")),
                }
            )
        return normalized

    def _string_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item)[:160] for item in value if item is not None]
        if value is None or value == "":
            return []
        return [str(value)[:160]]
