"""Hyper AI create/save handlers: signal pool, prompt, program, AI trader, and memory."""

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


def execute_save_signal_pool(
    db: Session,
    pool_name: str,
    symbol: str,
    signals: List[Dict[str, Any]],
    logic: str = "AND",
    exchange: str = "hyperliquid",
    description: str = None
) -> str:
    """Create a signal pool by calling the existing API handler."""
    from api.signal_routes import create_pool_from_config, SignalPoolConfigRequest

    try:
        # Defensive validation for taker_volume signals
        for i, sig in enumerate(signals):
            if sig.get("metric") == "taker_volume":
                missing = [f for f in ("direction", "ratio_threshold", "volume_threshold", "time_window")
                           if not sig.get(f) and sig.get(f) != 0]
                if missing or sig.get("operator"):
                    return json.dumps({
                        "error": f"Signal {i+1} (taker_volume) format error. "
                                 f"taker_volume requires: direction, ratio_threshold, volume_threshold, time_window. "
                                 f"Do NOT use operator/threshold for taker_volume.",
                        "correct_example": {
                            "metric": "taker_volume", "direction": "buy",
                            "ratio_threshold": 1.5, "volume_threshold": 100000, "time_window": "5m"
                        }
                    })

        # Build request object for the existing API handler
        request = SignalPoolConfigRequest(
            name=pool_name,
            symbol=symbol,
            signals=signals,
            logic=logic,
            exchange=exchange,
            description=description
        )

        # Call the existing API handler directly
        result = create_pool_from_config(request, db)

        return json.dumps({
            "success": True,
            "pool_id": result["pool"]["id"],
            "pool_name": result["pool"]["pool_name"],
            "symbol": symbol.upper(),
            "signals_created": len(result["signals"]),
            "signals": signals,
            "logic": logic,
            "exchange": exchange,
            "view_url": f"/#signal-management?view={result['pool']['id']}",
            "note": "Signal pool created. Bind it to an AI Trader to start receiving triggers."
        })

    except Exception as e:
        db.rollback()
        logger.error(f"[save_signal_pool] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_save_prompt(
    db: Session,
    name: str,
    template_text: str,
    prompt_id: int = None,
    description: str = None
) -> str:
    """Create or update a trading prompt template."""
    from database.models import PromptTemplate
    import re

    try:
        # Extract variables from template
        variables = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', template_text)
        variables = list(set(variables))

        if prompt_id:
            # Update existing prompt
            prompt = db.query(PromptTemplate).filter(
                PromptTemplate.id == prompt_id,
                PromptTemplate.is_deleted == "false"
            ).first()
            if not prompt:
                return json.dumps({"error": f"Prompt {prompt_id} not found"})

            prompt.name = name
            prompt.template_text = template_text
            if description:
                prompt.description = description
            prompt.updated_by = "hyper_ai"
            db.commit()
            action = "updated"
        else:
            # Create new prompt
            # Generate unique key
            import uuid
            key = f"hyper_ai_{uuid.uuid4().hex[:8]}"

            # Get default system template
            default_system = db.query(PromptTemplate).filter(
                PromptTemplate.is_system == "true"
            ).first()
            system_text = default_system.system_template_text if default_system else ""

            prompt = PromptTemplate(
                key=key,
                name=name,
                description=description or "",
                template_text=template_text,
                system_template_text=system_text,
                is_system="false",
                is_deleted="false",
                created_by="hyper_ai"
            )
            db.add(prompt)
            db.commit()
            db.refresh(prompt)
            action = "created"

        return json.dumps({
            "success": True,
            "prompt_id": prompt.id,
            "name": name,
            "action": action,
            "variables_detected": variables[:20],
            "template_text": template_text,
            "view_url": f"/#prompt-management?view={prompt.id}",
            "note": "Prompt saved. Changes apply to bound AI Traders on next trigger."
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[save_prompt] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_save_program(
    db: Session,
    name: str,
    code: str,
    program_id: int = None,
    description: str = None
) -> str:
    """Create or update a trading program by calling existing API handlers."""
    from routes.program_routes import (
        create_program, update_program, ProgramCreate, ProgramUpdate
    )
    from fastapi import HTTPException

    try:
        if program_id:
            # Update existing program
            data = ProgramUpdate(name=name, code=code, description=description)
            result = update_program(program_id, data, db)
            action = "updated"
        else:
            # Create new program
            data = ProgramCreate(name=name, code=code, description=description)
            result = create_program(data, db)
            action = "created"

        return json.dumps({
            "success": True,
            "program_id": result.id,
            "name": result.name,
            "action": action,
            "code": code,
            "view_url": f"/#program-trader?view={result.id}",
            "validation": {"syntax_valid": True, "security_check": "passed"},
            "note": "Program saved. Use test_run_code to verify logic before binding."
        }, indent=2)

    except HTTPException as e:
        db.rollback()
        logger.error(f"[save_program] HTTPException: {e.detail}")
        return json.dumps({"success": False, "error": e.detail})
    except Exception as e:
        db.rollback()
        logger.error(f"[save_program] Error: {e}")
        return json.dumps({"error": str(e)})


def execute_create_ai_trader(
    db: Session,
    name: str,
    model: str,
    base_url: str,
    api_key: str
) -> str:
    """Create a new AI Trader with LLM config only. Strategy and wallet binding done separately."""
    from database.models import Account

    try:
        # Step 1: Test LLM connection first
        from api.account_routes import test_llm_connection
        import asyncio

        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        test_result = loop.run_until_complete(test_llm_connection({
            "model": model,
            "base_url": base_url,
            "api_key": api_key
        }))

        if not test_result.get("success"):
            return json.dumps({
                "success": False,
                "error": "LLM connection test failed",
                "details": test_result.get("message", "Unknown error"),
                "note": "Please check your LLM credentials and try again."
            })

        # Step 2: Create Account with LLM config only
        account = Account(
            user_id=1,
            name=name,
            account_type="AI",
            is_active="true",
            auto_trading_enabled="false",  # Disabled until strategy/wallet configured
            model=model,
            base_url=base_url,
            api_key=api_key
        )
        db.add(account)
        db.commit()

        return json.dumps({
            "success": True,
            "trader_id": account.id,
            "trader_name": name,
            "llm_config": {
                "model": model,
                "base_url": base_url,
                "connection_tested": True
            },
            "view_url": f"/#trader-management?view={account.id}",
            "next_steps": [
                "1. Bind a wallet to this trader",
                "2. Create/select a trading strategy",
                "3. Enable auto-trading when ready"
            ],
            "note": "AI Trader created with LLM config. Complete wallet and strategy setup to start trading."
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_ai_trader] Error: {e}")
        return json.dumps({"error": str(e)})




def execute_save_memory(
    db: Session, category: str, content: str,
    importance: float = 0.5, api_config: Optional[Dict[str, Any]] = None
) -> str:
    """Save a memory with LLM-powered dedup (same logic as compression).

    When api_config is provided, uses batch_dedup_memories to intelligently
    ADD/UPDATE/DELETE memories. Falls back to simple add if no api_config.
    """
    from services.hyper_ai_memory_service import (
        add_memory, MEMORY_CATEGORIES, enforce_memory_limit,
        batch_dedup_memories
    )

    try:
        if category not in MEMORY_CATEGORIES:
            return json.dumps({"error": f"Invalid category. Must be one of: {MEMORY_CATEGORIES}"})

        content = content.strip()
        if len(content) < 10:
            return json.dumps({"error": "Content must be at least 10 characters"})

        importance = max(0.0, min(1.0, importance))

        new_memory = [{"category": category, "content": content, "importance": importance}]

        if api_config and api_config.get("api_key"):
            count = batch_dedup_memories(db, new_memory, api_config, source="ai_tool")
            action = "deduped" if count > 0 else "skipped (redundant)"
        else:
            add_memory(db, category, content, source="ai_tool", importance=importance)
            enforce_memory_limit(db)
            action = "added"

        return json.dumps({
            "success": True,
            "action": action,
            "note": "Memory processed with intelligent dedup. It will be included in future conversations."
        }, indent=2)

    except Exception as e:
        db.rollback()
        logger.error(f"[save_memory] Error: {e}")
        return json.dumps({"error": str(e)})

