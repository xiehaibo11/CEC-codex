"""Conversation generation rollover: archive -> compress -> fresh round.

In-conversation compression keeps a chat under the context limit forever, but
every generation of stacked summaries degrades the context ("lost in the
middle" drift) - the practical hallucination vector for a long-running
assistant. This module adds a hard boundary: once the raw conversation
outgrows the model's window budget, the output headroom is gone, or too many
compression generations have piled up, the conversation is retired in three
ordered steps (the order is the contract - trading text must be durable
BEFORE the reset):

1. **Archive** - full message log (including tool calls, i.e. the trading
   text) written to ``HYPER_AI_ARCHIVE_DIR`` as JSON.
2. **Compress** - long-term memories extracted (async) and a final summary
   generated from the recent tail.
3. **New round** - a fresh conversation is created, seeded with that summary
   as its first compression point, so the next message starts from a clean
   window that still knows where the story left off.

Model limits are resolved from the shared context-window table; DeepSeek V4's
1M context / 384K max output are covered explicitly.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import HyperAiConversation, HyperAiMessage
from services.ai_context_compression_service import (
    estimate_tokens,
    get_context_window,
)

logger = logging.getLogger(__name__)

# Hard-reset once the RAW conversation (all messages, pre-compression) has
# consumed this share of the model window. Compression can keep the API call
# smaller than this, but by then the summaries are doing the remembering.
ROLLOVER_CONTEXT_RATIO = 0.85

# Each compression point is one generation of lossy summarization stacked on
# the last. Past a few generations the early conversation is folklore.
MAX_COMPRESSION_GENERATIONS = 3

# Per-model max output tokens (DeepSeek V4 officially supports up to 384K).
MODEL_MAX_OUTPUT_TOKENS = {
    "deepseek": 384_000,
}
DEFAULT_MAX_OUTPUT_TOKENS = 8_192

# Never plan for a full-size maximum response; cap the headroom we insist on.
OUTPUT_HEADROOM_CAP = 64_000


def get_max_output_tokens(model: str) -> int:
    model_lower = (model or "").lower()
    for key, limit in MODEL_MAX_OUTPUT_TOKENS.items():
        if key in model_lower:
            return limit
    return DEFAULT_MAX_OUTPUT_TOKENS


def _archive_dir() -> Path:
    configured = os.getenv("HYPER_AI_ARCHIVE_DIR", "").strip()
    if configured:
        return Path(configured)
    # /app/data is the persistent volume in the container; fall back to a
    # backend-local data dir for dev checkouts.
    docker_data = Path("/app/data")
    base = docker_data if docker_data.is_dir() else Path("data")
    return base / "hyper_ai_archives"


def _compression_generations(conversation: HyperAiConversation) -> int:
    if not conversation.compression_points:
        return 0
    try:
        return len(json.loads(conversation.compression_points))
    except (TypeError, ValueError):
        return 0


def _conversation_raw_tokens(db: Session, conversation_id: int) -> int:
    total = 0
    rows = (
        db.query(HyperAiMessage.content, HyperAiMessage.tool_calls_log)
        .filter(HyperAiMessage.conversation_id == conversation_id)
        .all()
    )
    for content, tool_log in rows:
        total += estimate_tokens(content or "")
        total += estimate_tokens(tool_log or "")
    return total


def should_rollover(
    db: Session, conversation: HyperAiConversation, model: str
) -> Optional[str]:
    """Reason string when this conversation should be retired, else None."""
    generations = _compression_generations(conversation)
    if generations >= MAX_COMPRESSION_GENERATIONS:
        return (
            f"已经历 {generations} 代上下文压缩（上限 {MAX_COMPRESSION_GENERATIONS}），"
            "摘要叠摘要会持续劣化上下文"
        )

    window = get_context_window(model)
    raw_tokens = _conversation_raw_tokens(db, conversation.id)
    if raw_tokens >= window * ROLLOVER_CONTEXT_RATIO:
        return (
            f"会话累计约 {raw_tokens:,} tokens，已达模型窗口 {window:,} 的 "
            f"{ROLLOVER_CONTEXT_RATIO:.0%} 检测点"
        )

    headroom = min(get_max_output_tokens(model), OUTPUT_HEADROOM_CAP)
    if raw_tokens >= window - headroom:
        return (
            f"剩余窗口不足以容纳输出预算（约 {headroom:,} tokens），"
            "继续追加将面临截断"
        )
    return None


def _extract_memories_async(messages: List[Dict[str, Any]], api_config: Dict[str, Any]) -> None:
    """Fire-and-forget long-term memory extraction (mirrors the compression path)."""

    def _run() -> None:
        try:
            from database.connection import SessionLocal
            from services.hyper_ai_memory_service import process_compression_memories

            conv_text = "\n".join(
                f"{m.get('role')}: {m.get('content') or ''}" for m in messages
            )
            with SessionLocal() as db:
                process_compression_memories(db, conv_text, api_config)
        except Exception as exc:  # noqa: BLE001 - memory extraction is best-effort
            logger.warning("rollover memory extraction failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


def rollover_conversation(
    db: Session,
    conversation: HyperAiConversation,
    api_config: Dict[str, Any],
) -> HyperAiConversation:
    """Retire ``conversation`` and return the fresh seeded replacement.

    Step order is deliberate: the archive write happens BEFORE any reset so
    the trading text is durable even if summary generation fails."""
    import services.ai_context_compression_service as compression_service

    rows = (
        db.query(HyperAiMessage)
        .filter(HyperAiMessage.conversation_id == conversation.id)
        .order_by(HyperAiMessage.created_at)
        .all()
    )
    message_dicts = [
        {
            "role": m.role,
            "content": m.content,
            "tool_calls_log": m.tool_calls_log,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]

    # 1. Archive first - the durable trading text.
    archive_dir = _archive_dir()
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"conversation_{conversation.id}_{stamp}.json"
    archive_path.write_text(
        json.dumps(
            {
                "conversation_id": conversation.id,
                "title": conversation.title,
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "compression_points": conversation.compression_points,
                "messages": message_dicts,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    logger.info(
        "[Rollover] conversation %s archived to %s (%s messages)",
        conversation.id, archive_path, len(message_dicts),
    )

    # 2. Compress: async memory extraction + final summary of the recent tail.
    _extract_memories_async(message_dicts, api_config)
    summary = None
    try:
        tail = [
            {"role": m["role"], "content": m["content"] or ""}
            for m in message_dicts[-40:]
        ]
        summary = compression_service.generate_summary(tail, api_config)
    except Exception as exc:  # noqa: BLE001 - a failed summary must not block the reset
        logger.warning("rollover summary generation failed: %s", exc)
    if not summary:
        summary = f"上一轮对话（#{conversation.id}，{len(message_dicts)} 条消息）已归档至 {archive_path.name}。"

    # 3. New round, seeded so build_messages_for_api injects the summary and
    # message_id=0 filters nothing out of the new history.
    new_conv = HyperAiConversation(
        title=f"{conversation.title} (续)",
        compression_points=json.dumps(
            [
                {
                    "message_id": 0,
                    "summary": summary,
                    "compressed_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        ),
    )
    db.add(new_conv)
    conversation.title = f"{conversation.title} [已归档 → #待分配]"
    db.commit()
    db.refresh(new_conv)
    conversation.title = conversation.title.replace("#待分配", f"#{new_conv.id}")
    db.commit()
    logger.info(
        "[Rollover] conversation %s -> new round %s", conversation.id, new_conv.id
    )
    return new_conv
