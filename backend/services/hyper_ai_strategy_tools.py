"""Strategy listing tools for Hyper AI."""

import json
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def execute_list_strategies(db: Session, strategy_id: int = None, strategy_type: str = None) -> str:
    """List all prompts and programs with binding status."""
    from database.models import (
        PromptTemplate,
        TradingProgram,
        AccountProgramBinding,
        AccountPromptBinding,
        Account,
    )

    try:
        if strategy_id and strategy_type:
            if strategy_type == "prompt":
                template = db.query(PromptTemplate).filter(
                    PromptTemplate.id == strategy_id,
                    PromptTemplate.is_deleted == "false",
                ).first()
                if not template:
                    return json.dumps({"error": f"Prompt {strategy_id} not found"})

                bindings = db.query(AccountPromptBinding).filter(
                    AccountPromptBinding.prompt_template_id == template.id,
                    AccountPromptBinding.is_deleted != True,
                ).all()
                bound_traders = []
                for binding in bindings:
                    account = db.get(Account, binding.account_id)
                    if account:
                        bound_traders.append({"trader_id": account.id, "trader_name": account.name})

                return json.dumps({
                    "prompt_id": template.id,
                    "name": template.name,
                    "description": getattr(template, "description", None),
                    "template_text": template.template_text,
                    "bound_traders": bound_traders,
                }, indent=2)

            if strategy_type == "program":
                program = db.query(TradingProgram).filter(
                    TradingProgram.id == strategy_id,
                    TradingProgram.is_deleted != True,
                ).first()
                if not program:
                    return json.dumps({"error": f"Program {strategy_id} not found"})

                bindings = db.query(AccountProgramBinding).filter(
                    AccountProgramBinding.program_id == program.id,
                    AccountProgramBinding.is_deleted != True,
                ).all()
                bound_traders = []
                for binding in bindings:
                    account = db.get(Account, binding.account_id)
                    if account:
                        bound_traders.append({
                            "trader_id": account.id,
                            "trader_name": account.name,
                            "is_active": binding.is_active,
                        })

                return json.dumps({
                    "program_id": program.id,
                    "name": program.name,
                    "description": program.description,
                    "code": program.code,
                    "bound_traders": bound_traders,
                }, indent=2)

        templates = db.query(PromptTemplate).filter(
            PromptTemplate.is_deleted == "false"
        ).all()
        prompts = []
        for template in templates:
            bindings = db.query(AccountPromptBinding).filter(
                AccountPromptBinding.prompt_template_id == template.id,
                AccountPromptBinding.is_deleted != True,
            ).all()
            bound_traders = []
            for binding in bindings:
                account = db.get(Account, binding.account_id)
                if account:
                    bound_traders.append({"trader_id": account.id, "trader_name": account.name})
            prompts.append({
                "prompt_id": template.id,
                "name": template.name,
                "description": getattr(template, "description", None),
                "bound_traders": bound_traders,
            })

        programs_db = db.query(TradingProgram).filter(TradingProgram.is_deleted != True).all()
        programs = []
        for program in programs_db:
            bindings = db.query(AccountProgramBinding).filter(
                AccountProgramBinding.program_id == program.id,
                AccountProgramBinding.is_deleted != True,
            ).all()
            bound_traders = []
            for binding in bindings:
                account = db.get(Account, binding.account_id)
                if account:
                    bound_traders.append({
                        "trader_id": account.id,
                        "trader_name": account.name,
                        "is_active": binding.is_active,
                    })
            programs.append({
                "program_id": program.id,
                "name": program.name,
                "description": program.description,
                "bound_traders": bound_traders,
            })

        return json.dumps({
            "prompts": prompts,
            "programs": programs,
            "prompt_count": len(prompts),
            "program_count": len(programs),
        }, indent=2)

    except Exception as exc:
        logger.error(f"[list_strategies] Error: {exc}")
        return json.dumps({"error": str(exc)})
