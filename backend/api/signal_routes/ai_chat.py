"""AI signal generation chat endpoints (sync, listing, and SSE streaming)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.ai_signal_generation_service import (
    generate_signal_with_ai,
    generate_signal_with_ai_stream,
    get_signal_conversation_history,
    get_signal_conversation_messages
)
from database.models import User

from ._base import get_db, router


class AiSignalChatRequest(BaseModel):
    """Request to send a message to AI signal generation chat"""
    account_id: int = Field(..., alias="accountId")
    user_message: str = Field(..., alias="userMessage")
    conversation_id: Optional[int] = Field(None, alias="conversationId")
    # SSE direct streaming is unstable (frontend disconnect = task abort). Do NOT set to False.
    use_background_task: bool = Field(True, alias="useBackgroundTask")

    class Config:
        populate_by_name = True


class AiSignalChatResponse(BaseModel):
    """Response from AI signal generation chat"""
    success: bool
    conversation_id: Optional[int] = Field(None, alias="conversationId")
    message_id: Optional[int] = Field(None, alias="messageId")
    content: Optional[str] = None
    signal_configs: Optional[List[dict]] = Field(None, alias="signalConfigs")
    error: Optional[str] = None

    class Config:
        populate_by_name = True


# ============ AI Signal Generation Chat APIs ============

@router.post("/ai-chat", response_model=AiSignalChatResponse)
def ai_signal_chat(
    request: AiSignalChatRequest,
    db: Session = Depends(get_db)
) -> AiSignalChatResponse:
    """Send a message to AI signal generation assistant"""
    # Get user (default user for now)
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = generate_signal_with_ai(
        db=db,
        account_id=request.account_id,
        user_message=request.user_message,
        conversation_id=request.conversation_id,
        user_id=user.id
    )

    return AiSignalChatResponse(
        success=result.get("success", False),
        conversation_id=result.get("conversation_id"),
        message_id=result.get("message_id"),
        content=result.get("content"),
        signal_configs=result.get("signal_configs"),
        error=result.get("error")
    )


@router.get("/ai-conversations")
def list_ai_signal_conversations(
    limit: int = 20,
    db: Session = Depends(get_db)
) -> dict:
    """Get list of AI signal generation conversations"""
    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conversations = get_signal_conversation_history(
        db=db,
        user_id=user.id,
        limit=limit
    )

    return {"conversations": conversations}


@router.get("/ai-conversations/{conversation_id}/messages")
def get_ai_signal_conversation_messages(
    conversation_id: int,
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
) -> dict:
    """Get all messages in a specific conversation with compression points and token usage"""
    import json as json_module
    from database.models import AiSignalConversation, HyperAiProfile
    from services.ai_context_compression_service import calculate_token_usage, restore_tool_calls_to_messages

    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages = get_signal_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=user.id
    )

    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get compression points from conversation
    compression_points = []
    conversation = db.query(AiSignalConversation).filter(
        AiSignalConversation.id == conversation_id
    ).first()
    if conversation and conversation.compression_points:
        try:
            compression_points = json_module.loads(conversation.compression_points)
        except (json_module.JSONDecodeError, TypeError):
            compression_points = []

    # Determine model for token calculation: prefer account model, fallback to global
    token_model = None
    api_format = "openai"
    if account_id:
        from database.models import Account
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
        from database.models import AiSignalMessage

        cp = get_last_compression_point(conversation) if conversation else None
        cp_msg_id = cp.get("message_id", 0) if cp else 0

        history_orm = db.query(AiSignalMessage).filter(
            AiSignalMessage.conversation_id == conversation_id,
            AiSignalMessage.id > cp_msg_id
        ).order_by(AiSignalMessage.created_at).all()

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


# ============ AI Signal Generation SSE Streaming ============

@router.post("/ai-chat-stream")
async def ai_signal_chat_stream(
    request: AiSignalChatRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to AI signal generation assistant.

    Supports two modes:
    - SSE streaming (default): Returns Server-Sent Events directly
    - Background task (useBackgroundTask=true): Returns task_id for polling

    Event types (SSE mode):
    - status: Progress status message
    - tool_call: Tool being called with arguments
    - tool_result: Result from tool execution
    - reasoning: AI reasoning content (for reasoning models)
    - content: AI response content chunk
    - signal_config: Parsed signal configuration
    - done: Completion with final result
    - error: Error occurred
    """
    from services.ai_stream_service import get_buffer_manager, generate_task_id, run_ai_task_in_background
    from database.connection import SessionLocal

    user = db.query(User).filter(User.username == "default").first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Background task mode
    if request.use_background_task:
        task_id = generate_task_id("signal")
        manager = get_buffer_manager()

        # Check for existing running task
        if request.conversation_id:
            existing = manager.get_pending_task_for_conversation(request.conversation_id)
            if existing:
                return {"task_id": existing.task_id, "status": "already_running"}

        manager.create_task(task_id, conversation_id=request.conversation_id)

        # Capture request data
        account_id = request.account_id
        user_message = request.user_message
        conversation_id = request.conversation_id
        user_id = user.id

        def generator_func():
            bg_db = SessionLocal()
            try:
                yield from generate_signal_with_ai_stream(
                    db=bg_db,
                    account_id=account_id,
                    user_message=user_message,
                    conversation_id=conversation_id,
                    user_id=user_id
                )
            finally:
                bg_db.close()

        run_ai_task_in_background(task_id, generator_func)
        return {"task_id": task_id, "status": "started"}

    # SSE streaming mode (default)
    def event_generator():
        for event in generate_signal_with_ai_stream(
            db=db,
            account_id=request.account_id,
            user_message=request.user_message,
            conversation_id=request.conversation_id,
            user_id=user.id
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
