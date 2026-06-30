"""
Hyper AI harness guardrails.

This module keeps runtime guardrails separate from tool implementations:
- tool execution metadata for circuit-breaker decisions
- risk matrix and preflight checks for runtime checkpoints
- sub-agent result contract checks

Tool result strings remain unchanged for the LLM and frontend.
"""
import json
import logging
import os
from typing import Any, Callable, Dict, Optional, Tuple

from sqlalchemy.orm import Session

__path__ = [os.path.join(os.path.dirname(__file__), "hyper_ai_harness")]

from services.hyper_ai_harness.confirmation import (  # noqa: E402
    SENSITIVE_ARG_PATTERNS as SENSITIVE_ARG_PATTERNS,
    _mask_value as _mask_value,
    blocked_meta as blocked_meta,
    blocked_tool_result as blocked_tool_result,
    build_confirmation_description as build_confirmation_description,
    circuit_breaker_result as circuit_breaker_result,
    generate_confirmation_id as generate_confirmation_id,
    mask_tool_args as mask_tool_args,
)
from services.hyper_ai_harness.types import (  # noqa: E402
    CIRCUIT_BREAKER_THRESHOLD as CIRCUIT_BREAKER_THRESHOLD,
    CONTRACT_FAIL_PREFIX as CONTRACT_FAIL_PREFIX,
    RISK_HIGH as RISK_HIGH,
    RISK_LOW_WRITE as RISK_LOW_WRITE,
    RISK_READONLY as RISK_READONLY,
    TOOL_STATUS_BLOCKED as TOOL_STATUS_BLOCKED,
    TOOL_STATUS_DOMAIN_ERROR as TOOL_STATUS_DOMAIN_ERROR,
    TOOL_STATUS_INFRA_ERROR as TOOL_STATUS_INFRA_ERROR,
    TOOL_STATUS_SUCCESS as TOOL_STATUS_SUCCESS,
    TOOL_STATUS_WARNING as TOOL_STATUS_WARNING,
    ToolExecutionMeta as ToolExecutionMeta,
    ToolFailureTracker as ToolFailureTracker,
    ToolRiskAssessment as ToolRiskAssessment,
)
from database.models import (
    Account,
    AccountProgramBinding,
    AccountPromptBinding,
    AccountStrategyConfig,
)
from services.hyper_ai_tools import execute_hyper_ai_tool

logger = logging.getLogger(__name__)


READONLY_TOOLS = {
    "get_system_overview",
    "get_wallet_status",
    "get_api_reference",
    "get_klines",
    "get_market_regime",
    "get_market_flow",
    "get_system_logs",
    "get_contact_config",
    "get_trading_environment",
    "get_watchlist",
    "diagnose_trader_issues",
    "analyze_tracked_address",
    "get_tracked_wallets",
    "list_traders",
    "list_signal_pools",
    "list_strategies",
    "query_factors",
    "evaluate_factor",
    "get_factor_functions",
    "web_search",
    "fetch_url",
    "load_skill",
    "load_skill_reference",
    "call_prompt_ai",
    "call_program_ai",
    "call_signal_ai",
    "call_attribution_ai",
}

LOW_WRITE_TOOLS = {
    "save_signal_pool",
    "save_prompt",
    "save_program",
    "create_ai_trader",
    "update_signal_pool",
    "save_factor",
    "edit_factor",
    "compute_factor",
    "update_watchlist",
    "save_memory",
}

HIGH_RISK_TOOLS = {
    "bind_prompt_to_trader",
    "bind_program_to_trader",
    "update_trader_strategy",
    "update_ai_trader",
    "update_program_binding",
    "update_prompt_binding",
    "delete_trader",
    "delete_prompt_template",
    "delete_signal_definition",
    "delete_signal_pool",
    "delete_trading_program",
    "delete_prompt_binding",
    "delete_program_binding",
}


def _parse_json_result(result: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


INFRA_PATTERNS = (
    "connection error",
    "connection refused",
    "connection reset",
    "connect timeout",
    "read timeout",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "http 502",
    "http 503",
    "http 504",
    "upstream",
)


def _contains_infra_pattern(text: Any) -> bool:
    if text is None:
        return False
    lower = str(text).lower()
    return any(pattern in lower for pattern in INFRA_PATTERNS)


def _extract_error_text(parsed: Dict[str, Any]) -> str:
    parts = []
    for key in ("error", "message", "details", "note"):
        value = parsed.get(key)
        if value:
            parts.append(str(value))
    next_steps = parsed.get("next_steps")
    if isinstance(next_steps, list):
        parts.extend(str(item) for item in next_steps)
    return " ".join(parts)


def _classify_generic_error(tool_name: str, parsed: Dict[str, Any]) -> ToolExecutionMeta:
    code = "error"
    status = TOOL_STATUS_DOMAIN_ERROR
    retryable = False
    text = _extract_error_text(parsed)
    error_class = str(parsed.get("_error_class") or "")

    if error_class in {"Timeout", "ConnectionError", "ReadTimeout", "ConnectTimeout"}:
        status = TOOL_STATUS_INFRA_ERROR
        code = "upstream_unavailable"
        retryable = True

    return ToolExecutionMeta(
        tool_name=tool_name,
        status=status,
        code=code,
        message=text or "Tool returned an error.",
        retryable=retryable,
    )


def _classify_wallet_status(tool_name: str, parsed: Dict[str, Any]) -> ToolExecutionMeta:
    wallets = parsed.get("wallets")
    if not isinstance(wallets, list):
        return classify_default(tool_name, parsed)

    errors = [wallet.get("error") for wallet in wallets if isinstance(wallet, dict) and wallet.get("error")]
    if not errors:
        return ToolExecutionMeta(tool_name=tool_name)
    if len(errors) == len(wallets) and all(_contains_infra_pattern(error) for error in errors):
        return ToolExecutionMeta(
            tool_name=tool_name,
            status=TOOL_STATUS_INFRA_ERROR,
            code="upstream_unavailable",
            message="Wallet status upstream call failed.",
            retryable=True,
        )
    return ToolExecutionMeta(
        tool_name=tool_name,
        status=TOOL_STATUS_WARNING,
        code="partial_wallet_status",
        message="Some wallet status entries returned errors.",
    )


def _classify_infra_prone(tool_name: str, parsed: Dict[str, Any]) -> ToolExecutionMeta:
    if not parsed.get("error") and not parsed.get("_error_class"):
        return ToolExecutionMeta(tool_name=tool_name)

    text = _extract_error_text(parsed)
    if _contains_infra_pattern(text) or str(parsed.get("_error_class") or "") in {
        "Timeout",
        "ConnectionError",
        "ReadTimeout",
        "ConnectTimeout",
    }:
        return ToolExecutionMeta(
            tool_name=tool_name,
            status=TOOL_STATUS_INFRA_ERROR,
            code="upstream_unavailable",
            message=text or "Upstream service unavailable.",
            retryable=True,
        )
    return _classify_generic_error(tool_name, parsed)


def classify_default(tool_name: str, parsed: Optional[Dict[str, Any]]) -> ToolExecutionMeta:
    if parsed and parsed.get("error"):
        return _classify_generic_error(tool_name, parsed)
    if parsed and parsed.get("success") is False:
        return ToolExecutionMeta(
            tool_name=tool_name,
            status=TOOL_STATUS_DOMAIN_ERROR,
            code="operation_failed",
            message=_extract_error_text(parsed) or "Tool reported success=false.",
        )
    return ToolExecutionMeta(tool_name=tool_name)


TOOL_CLASSIFIERS: Dict[str, Callable[[str, Dict[str, Any]], ToolExecutionMeta]] = {
    "get_wallet_status": _classify_wallet_status,
    "get_klines": _classify_infra_prone,
    "get_market_regime": _classify_infra_prone,
    "get_market_flow": _classify_infra_prone,
    "web_search": _classify_infra_prone,
    "fetch_url": _classify_infra_prone,
    "analyze_tracked_address": _classify_infra_prone,
    "get_tracked_wallets": _classify_infra_prone,
    "query_factors": _classify_infra_prone,
    "evaluate_factor": _classify_infra_prone,
    "compute_factor": _classify_infra_prone,
    "create_ai_trader": _classify_infra_prone,
    "update_ai_trader": _classify_infra_prone,
}


def classify_tool_result(tool_name: str, result: str) -> ToolExecutionMeta:
    parsed = _parse_json_result(result)
    if parsed is None:
        if _contains_infra_pattern(result):
            return ToolExecutionMeta(
                tool_name=tool_name,
                status=TOOL_STATUS_INFRA_ERROR,
                code="upstream_unavailable",
                message="Unstructured tool result appears to be an infrastructure error.",
                retryable=True,
            )
        return ToolExecutionMeta(tool_name=tool_name)

    classifier = TOOL_CLASSIFIERS.get(tool_name)
    if classifier:
        return classifier(tool_name, parsed)
    return classify_default(tool_name, parsed)


def execute_tool_with_meta(
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
    user_id: int = 1,
    api_config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, ToolExecutionMeta]:
    result = execute_hyper_ai_tool(
        db,
        tool_name,
        arguments,
        user_id=user_id,
        api_config=api_config,
    )
    return result, classify_tool_result(tool_name, result)


def _json_id_list_contains(raw: Any, target_id: int) -> bool:
    if raw is None:
        return False
    if isinstance(raw, str):
        try:
            values = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            values = []
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return int(target_id) in {int(value) for value in values if str(value).isdigit()}


def _prompt_bound_to_active_trader(db: Session, prompt_id: int) -> bool:
    return db.query(AccountPromptBinding).join(
        Account, Account.id == AccountPromptBinding.account_id
    ).filter(
        AccountPromptBinding.prompt_template_id == prompt_id,
        AccountPromptBinding.is_deleted != True,
        Account.is_active == "true",
        Account.is_deleted != True,
    ).first() is not None


def _program_bound_to_active_trader(db: Session, program_id: int) -> bool:
    return db.query(AccountProgramBinding).join(
        Account, Account.id == AccountProgramBinding.account_id
    ).filter(
        AccountProgramBinding.program_id == program_id,
        AccountProgramBinding.is_deleted != True,
        AccountProgramBinding.is_active == True,
        Account.is_active == "true",
        Account.is_deleted != True,
    ).first() is not None


def _signal_pool_bound_to_active_trader(db: Session, pool_id: int) -> bool:
    strategy_configs = db.query(AccountStrategyConfig).join(
        Account, Account.id == AccountStrategyConfig.account_id
    ).filter(
        Account.is_active == "true",
        Account.is_deleted != True,
    ).all()
    for config in strategy_configs:
        if _json_id_list_contains(config.signal_pool_ids, pool_id):
            return True

    program_bindings = db.query(AccountProgramBinding).join(
        Account, Account.id == AccountProgramBinding.account_id
    ).filter(
        AccountProgramBinding.is_deleted != True,
        AccountProgramBinding.is_active == True,
        Account.is_active == "true",
        Account.is_deleted != True,
    ).all()
    for binding in program_bindings:
        if _json_id_list_contains(binding.signal_pool_ids, pool_id):
            return True

    return False


def assess_tool_risk(
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
) -> ToolRiskAssessment:
    if tool_name in HIGH_RISK_TOOLS:
        return ToolRiskAssessment(
            tool_name=tool_name,
            risk_level=RISK_HIGH,
            reason="static_high_risk",
            description=build_confirmation_description(tool_name, arguments),
        )

    risk_level = RISK_LOW_WRITE if tool_name in LOW_WRITE_TOOLS else RISK_READONLY
    reason = "static_low_write" if risk_level == RISK_LOW_WRITE else "static_readonly"

    try:
        if tool_name == "save_prompt" and arguments.get("prompt_id"):
            prompt_id = int(arguments["prompt_id"])
            if _prompt_bound_to_active_trader(db, prompt_id):
                risk_level = RISK_HIGH
                reason = "prompt_bound_to_active_trader"
        elif tool_name == "save_program" and arguments.get("program_id"):
            program_id = int(arguments["program_id"])
            if _program_bound_to_active_trader(db, program_id):
                risk_level = RISK_HIGH
                reason = "program_bound_to_active_trader"
        elif tool_name == "update_signal_pool" and arguments.get("pool_id"):
            pool_id = int(arguments["pool_id"])
            if _signal_pool_bound_to_active_trader(db, pool_id):
                risk_level = RISK_HIGH
                reason = "signal_pool_bound_to_active_trader"
    except Exception as exc:
        logger.warning("[HyperAI Harness] Preflight failed for %s: %s", tool_name, exc)
        risk_level = RISK_HIGH
        reason = "preflight_failed"

    return ToolRiskAssessment(
        tool_name=tool_name,
        risk_level=risk_level,
        reason=reason,
        description=build_confirmation_description(tool_name, arguments),
    )


class SubAgentContractChecker:
    @staticmethod
    def check(tool_name: str, result: str) -> Tuple[bool, str]:
        try:
            parsed = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return False, f"{CONTRACT_FAIL_PREFIX} Non-JSON result from {tool_name}"

        if not isinstance(parsed, dict):
            return False, f"{CONTRACT_FAIL_PREFIX} Non-object result from {tool_name}"

        status = parsed.get("status")
        if status is None:
            return False, f"{CONTRACT_FAIL_PREFIX} Missing status from {tool_name}"
        if status == "failed":
            return False, f"{CONTRACT_FAIL_PREFIX} {tool_name} reported failure: {parsed.get('error') or 'Unknown error'}"

        content = parsed.get("content")
        if not isinstance(content, str) or not content.strip():
            return False, f"{CONTRACT_FAIL_PREFIX} {tool_name} returned empty content"

        return True, ""
