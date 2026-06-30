"""Request builders for Hyper AI sub-agent stream calls."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


def build_prompt_ai_request(
    db: Session,
    task: str,
    conversation_id: Optional[int],
    prompt_id: Optional[int],
    user_id: int,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "db": db,
        "user_message": task,
        "conversation_id": conversation_id,
        "prompt_id": prompt_id,
        "user_id": user_id,
        "llm_config": llm_config,
    }


def build_program_ai_request(
    db: Session,
    task: str,
    conversation_id: Optional[int],
    program_id: Optional[int],
    user_id: int,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "db": db,
        "user_message": task,
        "conversation_id": conversation_id,
        "program_id": program_id,
        "user_id": user_id,
        "llm_config": llm_config,
    }


def build_signal_ai_request(
    db: Session,
    task: str,
    conversation_id: Optional[int],
    user_id: int,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "db": db,
        "user_message": task,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "llm_config": llm_config,
    }


def build_attribution_ai_request(
    db: Session,
    task: str,
    conversation_id: Optional[int],
    user_id: int,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "db": db,
        "user_message": task,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "llm_config": llm_config,
    }
