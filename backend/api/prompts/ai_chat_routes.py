from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Account, User
from services.ai_prompt_generation_service import (
    generate_prompt_with_ai,
    generate_prompt_with_ai_stream,
    get_conversation_history,
    get_conversation_messages,
)

from .dependencies import get_db

router = APIRouter()


class AiChatRequest(BaseModel):
    """Request to send a message to AI prompt generation chat"""
    account_id: int = Field(..., alias="accountId")
    user_message: str = Field(..., alias="userMessage")
    conversation_id: Optional[int] = Field(None, alias="conversationId")
    prompt_id: Optional[int] = Field(None, alias="promptId")
    # SSE direct streaming is unstable (frontend disconnect = task abort). Do NOT set to False.
    use_background_task: bool = Field(True, alias="useBackgroundTask")

    class Config:
        populate_by_name = True


class AiChatResponse(BaseModel):
    """Response from AI prompt generation chat"""
    success: bool
    conversation_id: Optional[int] = Field(None, alias="conversationId")
    message_id: Optional[int] = Field(None, alias="messageId")
    content: Optional[str] = None
    prompt_result: Optional[str] = Field(None, alias="promptResult")
    error: Optional[str] = None

    class Config:
        populate_by_name = True


@router.post("/ai-chat", response_model=AiChatResponse)
def ai_chat(
    request: AiChatRequest,
    db: Session = Depends(get_db)
) -> AiChatResponse:
    """
    Send a message to AI prompt generation assistant

    Premium feature - requires active subscription
    """
    # Get user (default user for now)
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get AI Trader account
    account = db.query(Account).filter(Account.id == request.account_id, Account.is_deleted != True).first()
    if not account:
        raise HTTPException(status_code=404, detail="AI Trader not found")

    if account.account_type != "AI":
        raise HTTPException(status_code=400, detail="Selected account is not an AI Trader")

    # Generate response
    result = generate_prompt_with_ai(
        db=db,
        account=account,
        user_message=request.user_message,
        conversation_id=request.conversation_id,
        user_id=user.id,
        prompt_id=request.prompt_id
    )

    return AiChatResponse(
        success=result.get("success", False),
        conversation_id=result.get("conversation_id"),
        message_id=result.get("message_id"),
        content=result.get("content"),
        prompt_result=result.get("prompt_result"),
        error=result.get("error")
    )


@router.post("/ai-chat-stream")
def ai_chat_stream(
    request: AiChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to AI prompt generation assistant.

    Supports two modes:
    - SSE streaming (default): Returns Server-Sent Events directly
    - Background task (useBackgroundTask=true): Returns task_id for polling

    Premium feature - requires active subscription.
    """
    from services.ai_stream_service import get_buffer_manager, generate_task_id, run_ai_task_in_background
    from database.connection import SessionLocal

    # Get user (default user for now)
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get AI Trader account
    account = db.query(Account).filter(Account.id == request.account_id, Account.is_deleted != True).first()
    if not account:
        raise HTTPException(status_code=404, detail="AI Trader not found")

    if account.account_type != "AI":
        raise HTTPException(status_code=400, detail="Selected account is not an AI Trader")

    # Background task mode
    if request.use_background_task:
        task_id = generate_task_id("prompt")
        manager = get_buffer_manager()

        # Check for existing running task on this conversation
        if request.conversation_id:
            existing = manager.get_pending_task_for_conversation(request.conversation_id)
            if existing:
                return {"task_id": existing.task_id, "status": "already_running"}

        # Create task
        manager.create_task(task_id, conversation_id=request.conversation_id)

        # Capture request data for background thread
        account_id = account.id
        user_message = request.user_message
        conversation_id = request.conversation_id
        user_id = user.id
        prompt_id = request.prompt_id

        def generator_func():
            # Create new db session for background thread
            bg_db = SessionLocal()
            try:
                bg_account = bg_db.query(Account).filter(Account.id == account_id, Account.is_deleted != True).first()
                yield from generate_prompt_with_ai_stream(
                    db=bg_db,
                    account=bg_account,
                    user_message=user_message,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    prompt_id=prompt_id
                )
            finally:
                bg_db.close()

        run_ai_task_in_background(task_id, generator_func)
        return {"task_id": task_id, "status": "started"}

    # SSE streaming mode (default, backward compatible)
    return StreamingResponse(
        generate_prompt_with_ai_stream(
            db=db,
            account=account,
            user_message=request.user_message,
            conversation_id=request.conversation_id,
            user_id=user.id,
            prompt_id=request.prompt_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/ai-conversations")
def list_ai_conversations(
    limit: int = 20,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get list of AI prompt generation conversations

    Premium feature - requires active subscription
    """
    # Get user (default user for now)
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conversations = get_conversation_history(
        db=db,
        user_id=user.id,
        limit=limit
    )

    return {"conversations": conversations}


@router.get("/ai-conversations/{conversation_id}/messages")
def get_conversation_messages_api(
    conversation_id: int,
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get all messages in a specific conversation with token usage

    Premium feature - requires active subscription
    """
    # Get user (default user for now)
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages = get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=user.id
    )

    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get compression points
    from database.models import AiPromptConversation, HyperAiProfile
    from services.ai_context_compression_service import calculate_token_usage, restore_tool_calls_to_messages
    import json as json_module

    conversation = db.query(AiPromptConversation).filter(
        AiPromptConversation.id == conversation_id,
        AiPromptConversation.user_id == user.id
    ).first()

    compression_points = []
    if conversation and conversation.compression_points:
        try:
            compression_points = json_module.loads(conversation.compression_points)
        except (json_module.JSONDecodeError, TypeError):
            compression_points = []

    # Determine model for token calculation: prefer account model, fallback to global
    token_model = None
    api_format = "openai"
    if account_id:
        acct = db.query(Account).filter(Account.id == account_id, Account.is_deleted != True).first()
        if acct and acct.model:
            token_model = acct.model
            from services.ai_decision_service import detect_api_format
            _, fmt = detect_api_format(acct.base_url or "")
            api_format = fmt or "openai"
    if not token_model:
        profile = db.query(HyperAiProfile).first()
        if profile and profile.llm_model:
            token_model = profile.llm_model
            from services.hyper_ai_service import get_llm_config
            llm_config = get_llm_config(db)
            api_format = llm_config.get("api_format", "openai")

    # Calculate token usage (only messages after compression point + summary)
    token_usage = None
    if token_model and messages:
        from services.ai_context_compression_service import get_last_compression_point
        from database.models import AiPromptMessage

        cp = get_last_compression_point(conversation) if conversation else None
        cp_msg_id = cp.get("message_id", 0) if cp else 0

        history_orm = db.query(AiPromptMessage).filter(
            AiPromptMessage.conversation_id == conversation_id,
            AiPromptMessage.id > cp_msg_id
        ).order_by(AiPromptMessage.created_at).all()

        msg_dicts = [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls_log": m.tool_calls_log,
                "reasoning_snapshot": m.reasoning_snapshot,
            }
            for m in history_orm
        ]
        msg_list = restore_tool_calls_to_messages(msg_dicts, api_format, model=token_model or "")
        if cp and cp.get("summary"):
            msg_list.insert(0, {"role": "system", "content": cp["summary"]})
        token_usage = calculate_token_usage(msg_list, token_model)

    return {
        "messages": messages,
        "compression_points": compression_points,
        "token_usage": token_usage
    }
