"""Hyper AI binding and update handlers: bind prompt/program, update trader strategy,
trader config, program binding, signal pool, and prompt binding."""

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
# Binding Tools: assemble components
# =============================================================================

def execute_bind_prompt_to_trader(db: Session, trader_id: int, prompt_id: int) -> str:
    """Bind a prompt template to an AI Trader. Reuses prompt_repo.upsert_binding."""
    from database.models import Account, PromptTemplate
    from repositories import prompt_repo

    try:
        account = db.query(Account).filter(Account.id == trader_id, Account.is_deleted != True).first()
        if not account:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        template = db.get(PromptTemplate, prompt_id)
        if not template:
            return json.dumps({"error": f"Prompt template {prompt_id} not found"})

        binding = prompt_repo.upsert_binding(
            db,
            account_id=trader_id,
            prompt_template_id=prompt_id,
            updated_by="hyper_ai"
        )

        return json.dumps({
            "success": True,
            "binding_id": binding.id,
            "trader_id": trader_id,
            "trader_name": account.name,
            "prompt_id": prompt_id,
            "prompt_name": template.name
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[bind_prompt_to_trader] Error: {e}")
        return json.dumps({"error": str(e)})


def _validate_signal_pool_exchange_consistency(
    db: Session, binding_exchange: str, signal_pool_ids: list
) -> dict:
    """
    Validate that signal pool exchanges match the binding's target exchange.
    Returns {"valid": True} or {"valid": False, "error": "...", "details": {...}}
    """
    from database.models import SignalPool

    if not signal_pool_ids:
        return {"valid": True}

    # Get signal pool exchanges
    pools = db.query(SignalPool).filter(
        SignalPool.id.in_(signal_pool_ids),
        SignalPool.is_deleted != True
    ).all()

    # Check for mismatches
    mismatched = []
    for pool in pools:
        pool_exchange = pool.exchange or "hyperliquid"
        if pool_exchange != binding_exchange:
            mismatched.append({
                "pool_id": pool.id,
                "pool_name": pool.pool_name,
                "pool_exchange": pool_exchange,
                "binding_exchange": binding_exchange
            })

    if mismatched:
        return {
            "valid": False,
            "error": f"Exchange mismatch: Signal pool(s) exchange does not match binding's target exchange '{binding_exchange}'.",
            "mismatched_pools": mismatched,
            "suggestion": f"Use signal pools with exchange='{binding_exchange}', or change the binding exchange to match the signal pools."
        }

    return {"valid": True}


def execute_bind_program_to_trader(
    db: Session, trader_id: int, program_id: int,
    exchange: str = "hyperliquid",
    signal_pool_ids: list = None, trigger_interval: int = 300,
    is_active: bool = True
) -> str:
    """Create a program binding for an AI Trader. Reuses AccountProgramBinding model."""
    from database.models import Account, TradingProgram, AccountProgramBinding

    try:
        account = db.query(Account).filter(Account.id == trader_id, Account.is_deleted != True).first()
        if not account:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        program = db.get(TradingProgram, program_id)
        if not program:
            return json.dumps({"error": f"Program {program_id} not found"})

        # Validate signal pool exchange consistency with binding exchange
        if signal_pool_ids:
            validation = _validate_signal_pool_exchange_consistency(db, exchange, signal_pool_ids)
            if not validation.get("valid"):
                return json.dumps(validation)

        # Check duplicate
        existing = db.query(AccountProgramBinding).filter(
            AccountProgramBinding.account_id == trader_id,
            AccountProgramBinding.program_id == program_id,
            AccountProgramBinding.is_deleted != True
        ).first()
        if existing:
            return json.dumps({
                "error": f"Binding already exists (binding_id={existing.id})",
                "binding_id": existing.id
            })

        binding = AccountProgramBinding(
            account_id=trader_id,
            program_id=program_id,
            signal_pool_ids=json.dumps(signal_pool_ids) if signal_pool_ids else None,
            trigger_interval=trigger_interval,
            is_active=is_active,
            exchange=exchange
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)

        return json.dumps({
            "success": True,
            "binding_id": binding.id,
            "trader_id": trader_id,
            "trader_name": account.name,
            "program_id": program_id,
            "program_name": program.name,
            "signal_pool_ids": signal_pool_ids or [],
            "trigger_interval": trigger_interval,
            "is_active": is_active
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[bind_program_to_trader] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_update_trader_strategy(
    db: Session, trader_id: int,
    signal_pool_ids: list = None,
    scheduled_trigger_enabled: bool = None,
    trigger_interval: int = None,
    exchange: str = "hyperliquid"
) -> str:
    """Update trigger config for a Prompt-based AI Trader. Reuses upsert_strategy."""
    from database.models import Account
    from repositories.strategy_repo import upsert_strategy

    try:
        account = db.query(Account).filter(Account.id == trader_id, Account.is_deleted != True).first()
        if not account:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        strategy = upsert_strategy(
            db,
            account_id=trader_id,
            signal_pool_ids=signal_pool_ids,
            scheduled_trigger_enabled=scheduled_trigger_enabled,
            trigger_interval=trigger_interval,
            exchange=exchange
        )

        return json.dumps({
            "success": True,
            "trader_id": trader_id,
            "trader_name": account.name,
            "exchange": exchange,
            "signal_pool_ids": signal_pool_ids,
            "scheduled_trigger_enabled": scheduled_trigger_enabled,
            "trigger_interval": trigger_interval
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[update_trader_strategy] Error: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Update Tools
# =============================================================================

def execute_update_ai_trader(
    db: Session, trader_id: int,
    name: str = None, model: str = None,
    base_url: str = None, api_key: str = None
) -> str:
    """Update AI Trader settings. Tests LLM connection if credentials change."""
    from database.models import Account

    try:
        account = db.query(Account).filter(
            Account.id == trader_id, Account.is_active == "true",
            Account.is_deleted != True
        ).first()
        if not account:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        # Test LLM connection if any credential field changes
        new_model = model or account.model
        new_base_url = base_url or account.base_url
        new_api_key = api_key or account.api_key
        need_test = any([model, base_url, api_key])

        if need_test and new_model and new_base_url and new_api_key:
            from api.account_routes import test_llm_connection
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            test_result = loop.run_until_complete(test_llm_connection({
                "model": new_model,
                "base_url": new_base_url,
                "api_key": new_api_key
            }))
            if not test_result.get("success"):
                return json.dumps({
                    "success": False,
                    "error": "LLM connection test failed",
                    "details": test_result.get("message", "Unknown error")
                })

        updated = []
        if name:
            account.name = name
            updated.append("name")
        if model:
            account.model = model
            updated.append("model")
        if base_url:
            account.base_url = base_url
            updated.append("base_url")
        if api_key:
            account.api_key = api_key
            updated.append("api_key")

        db.commit()
        return json.dumps({
            "success": True, "trader_id": trader_id,
            "trader_name": account.name,
            "updated_fields": updated,
            "llm_tested": need_test
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[update_ai_trader] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_update_program_binding(
    db: Session, binding_id: int,
    signal_pool_ids: list = None, trigger_interval: int = None,
    scheduled_trigger_enabled: bool = None, is_active: bool = None,
    params_override: dict = None
) -> str:
    """Update a program binding's configuration."""
    from database.models import AccountProgramBinding, Account

    try:
        binding = db.query(AccountProgramBinding).filter(
            AccountProgramBinding.id == binding_id,
            AccountProgramBinding.is_deleted != True
        ).first()
        if not binding:
            return json.dumps({"error": f"Program binding {binding_id} not found"})

        updated = []
        if signal_pool_ids is not None:
            binding.signal_pool_ids = json.dumps(signal_pool_ids)
            updated.append("signal_pool_ids")
        if trigger_interval is not None:
            binding.trigger_interval = trigger_interval
            updated.append("trigger_interval")
        if scheduled_trigger_enabled is not None:
            binding.scheduled_trigger_enabled = scheduled_trigger_enabled
            updated.append("scheduled_trigger_enabled")
        if is_active is not None:
            binding.is_active = is_active
            updated.append("is_active")
        if params_override is not None:
            binding.params_override = json.dumps(params_override)
            updated.append("params_override")

        db.commit()
        account = db.get(Account, binding.account_id)
        return json.dumps({
            "success": True, "binding_id": binding_id,
            "trader_name": account.name if account else "unknown",
            "updated_fields": updated
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[update_program_binding] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_update_signal_pool(
    db: Session, pool_id: int,
    pool_name: str = None, enabled: bool = None, logic: str = None,
    signal_ids: list = None
) -> str:
    """Update signal pool settings."""
    from database.models import SignalPool, SignalDefinition

    try:
        pool = db.query(SignalPool).filter(SignalPool.id == pool_id, SignalPool.is_deleted != True).first()
        if not pool:
            return json.dumps({"error": f"Signal pool {pool_id} not found"})

        updated = []

        # Validate signal_ids exchange match
        if signal_ids is not None:
            pool_exchange = pool.exchange or "hyperliquid"
            mismatched = []
            for sid in signal_ids:
                sig = db.query(SignalDefinition).filter(SignalDefinition.id == sid, SignalDefinition.is_deleted != True).first()
                if not sig:
                    return json.dumps({"error": f"Signal definition {sid} not found"})
                sig_exchange = sig.exchange or "hyperliquid"
                if sig_exchange != pool_exchange:
                    mismatched.append(f"Signal {sid} ({sig_exchange})")
            if mismatched:
                return json.dumps({
                    "error": f"Exchange mismatch: pool is {pool_exchange}, but {', '.join(mismatched)}"
                })
            pool.signal_ids = json.dumps(signal_ids)
            updated.append("signal_ids")

        if pool_name is not None:
            pool.pool_name = pool_name
            updated.append("pool_name")
        if enabled is not None:
            pool.enabled = enabled
            updated.append("enabled")
        if logic is not None:
            pool.logic = logic
            updated.append("logic")

        db.commit()
        return json.dumps({
            "success": True, "pool_id": pool_id,
            "pool_name": pool.pool_name,
            "updated_fields": updated
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[update_signal_pool] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_update_prompt_binding(db: Session, trader_id: int, prompt_id: int) -> str:
    """Update which prompt is bound to a trader. Reuses upsert_binding."""
    from database.models import Account, PromptTemplate
    from repositories import prompt_repo

    try:
        account = db.query(Account).filter(Account.id == trader_id, Account.is_deleted != True).first()
        if not account:
            return json.dumps({"error": f"AI Trader {trader_id} not found"})

        template = db.get(PromptTemplate, prompt_id)
        if not template:
            return json.dumps({"error": f"Prompt template {prompt_id} not found"})

        binding = prompt_repo.upsert_binding(
            db, account_id=trader_id,
            prompt_template_id=prompt_id, updated_by="hyper_ai"
        )
        return json.dumps({
            "success": True, "binding_id": binding.id,
            "trader_id": trader_id, "trader_name": account.name,
            "prompt_id": prompt_id, "prompt_name": template.name
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[update_prompt_binding] Error: {e}")
        return json.dumps({"error": str(e)})


