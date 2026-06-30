from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import HyperAiConversation
from services.hyper_ai_service import (
    get_conversation_messages,
    get_llm_config,
    get_or_create_conversation,
    start_chat_task,
    start_insight_task,
    start_onboarding_chat_task,
)

from .schemas import ChatRequest, InsightRequest

router = APIRouter()


@router.get("/conversations")
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List recent conversations (excluding onboarding). Bot conversations pinned first."""
    conversations = db.query(HyperAiConversation).filter(
        HyperAiConversation.is_onboarding != True
    ).order_by(
        HyperAiConversation.is_bot_conversation.desc(),
        HyperAiConversation.updated_at.desc()
    ).limit(limit).all()

    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "message_count": c.message_count,
                "is_bot_conversation": bool(c.is_bot_conversation),
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    }


@router.post("/conversations")
def create_conversation(db: Session = Depends(get_db)):
    """Create a new conversation."""
    conv = get_or_create_conversation(db)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None
    }


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get messages from a conversation with compression points and token usage."""
    from database.models import HyperAiConversation, HyperAiProfile
    from services.ai_context_compression_service import calculate_token_usage, restore_tool_calls_to_messages
    import json as json_module

    messages = get_conversation_messages(db, conversation_id, limit)

    # Get compression points from conversation
    conversation = db.query(HyperAiConversation).filter(
        HyperAiConversation.id == conversation_id
    ).first()

    compression_points = []
    if conversation and conversation.compression_points:
        try:
            compression_points = json_module.loads(conversation.compression_points)
        except (json_module.JSONDecodeError, TypeError):
            compression_points = []

    # Calculate token usage (only messages after compression point + summary)
    token_usage = None
    profile = db.query(HyperAiProfile).first()
    if profile and profile.llm_model and messages:
        from services.ai_context_compression_service import get_last_compression_point
        from database.models import HyperAiMessage
        llm_config = get_llm_config(db)
        api_format = llm_config.get("api_format", "openai")

        # Load ORM objects for id-based filtering
        cp = get_last_compression_point(conversation) if conversation else None
        cp_msg_id = cp.get("message_id", 0) if cp else 0

        history_orm = db.query(HyperAiMessage).filter(
            HyperAiMessage.conversation_id == conversation_id,
            HyperAiMessage.id > cp_msg_id
        ).order_by(HyperAiMessage.created_at).all()

        msg_dicts = [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls_log": m.tool_calls_log,
                "reasoning_snapshot": m.reasoning_snapshot,
            }
            for m in history_orm
        ]
        msg_list = restore_tool_calls_to_messages(msg_dicts, api_format, model=profile.llm_model or "")
        if cp and cp.get("summary"):
            msg_list.insert(0, {"role": "system", "content": cp["summary"]})
        token_usage = calculate_token_usage(msg_list, profile.llm_model)

    return {
        "messages": messages,
        "compression_points": compression_points,
        "token_usage": token_usage
    }


@router.post("/chat")
def start_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Start a chat with Hyper AI.
    Returns task_id for polling via /api/ai-stream/{task_id}.

    mode="onboarding" uses a special prompt for profile collection.
    """
    # Check LLM config
    llm_config = get_llm_config(db)
    if not llm_config.get("configured"):
        raise HTTPException(
            status_code=400,
            detail="LLM not configured. Please complete onboarding first."
        )

    # Get or create conversation (mark as onboarding if in onboarding mode)
    is_onboarding = request.mode == "onboarding"
    conv = get_or_create_conversation(db, request.conversation_id, is_onboarding=is_onboarding)

    # Start background task based on mode
    if is_onboarding:
        task_id = start_onboarding_chat_task(db, conv.id, request.message, request.lang)
    else:
        task_id = start_chat_task(db, conv.id, request.message, request.lang)

    return {
        "task_id": task_id,
        "conversation_id": conv.id
    }


@router.post("/insight")
def start_insight(request: InsightRequest, db: Session = Depends(get_db)):
    """Start a one-shot Insight analysis task without chat conversation persistence."""
    llm_config = get_llm_config(db)
    if not llm_config.get("configured"):
        raise HTTPException(
            status_code=400,
            detail="LLM not configured. Please complete onboarding first."
        )

    task_id = start_insight_task(
        db=db,
        context=request.context,
        selected_event=request.selected_event,
        lang=request.lang,
    )
    return {"task_id": task_id}
