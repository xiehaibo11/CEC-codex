"""
Conversation history helpers for AI prompt generation.
"""
import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import AiPromptConversation, AiPromptMessage


def get_conversation_history(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> List[Dict]:
    """Get user's conversation history."""
    conversations = db.query(AiPromptConversation).filter(
        AiPromptConversation.user_id == user_id
    ).order_by(
        AiPromptConversation.updated_at.desc()
    ).limit(limit).all()

    result = []
    for conv in conversations:
        msg_count = db.query(AiPromptMessage).filter(
            AiPromptMessage.conversation_id == conv.id
        ).count()

        result.append({
            "id": conv.id,
            "title": conv.title,
            "promptId": conv.prompt_id,
            "messageCount": msg_count,
            "createdAt": conv.created_at.isoformat() if conv.created_at else None,
            "updatedAt": conv.updated_at.isoformat() if conv.updated_at else None,
        })

    return result


def get_conversation_messages(
    db: Session,
    conversation_id: int,
    user_id: int,
) -> Optional[List[Dict]]:
    """Get all messages in a conversation."""
    conversation = db.query(AiPromptConversation).filter(
        AiPromptConversation.id == conversation_id,
        AiPromptConversation.user_id == user_id,
    ).first()

    if not conversation:
        return None

    messages = db.query(AiPromptMessage).filter(
        AiPromptMessage.conversation_id == conversation_id
    ).order_by(AiPromptMessage.created_at).all()

    result = []
    for msg in messages:
        msg_data = {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "promptResult": msg.prompt_result,
            "createdAt": msg.created_at.isoformat() if msg.created_at else None,
            "is_complete": msg.is_complete if msg.is_complete is not None else True,
        }
        # Include tool_calls_log if present
        if msg.tool_calls_log:
            try:
                msg_data["tool_calls_log"] = json.loads(msg.tool_calls_log)
            except Exception:
                pass
        # Include reasoning_snapshot if present
        if msg.reasoning_snapshot:
            msg_data["reasoning_snapshot"] = msg.reasoning_snapshot
        result.append(msg_data)

    return result
