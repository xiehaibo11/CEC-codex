"""
Hyper AI Memory Service - User insights and memory management

This module provides:
1. Memory storage and retrieval with automatic system prompt injection
2. Batch LLM-based deduplication (single call for all memories)
3. Memory categories for organized storage
4. Importance scoring and automatic limit enforcement (max 50)

Memory Categories:
- preference: User trading preferences and style
- decision: Important trading decisions made
- lesson: Lessons learned from trades
- insight: Market insights and observations
- context: General context about user's situation

Architecture:
- Memory is extracted during context compression (async, non-blocking)
- Batch deduplication: 1 LLM call handles all new memories vs all existing
- Memories auto-injected into system prompt alongside user profile
- user_info category (from onboarding) is excluded from dedup/eviction
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import HyperAiMemory
from services.hyper_ai_memory.constants import MAX_MEMORIES, MEMORY_CATEGORIES
from services.hyper_ai_memory.llm import call_memory_llm
from services.hyper_ai_memory.parsing import (
    parse_dedup_actions,
    parse_extracted_memories,
)
from services.hyper_ai_memory.prompts import (
    BATCH_DEDUP_PROMPT,
    EXTRACT_MEMORIES_PROMPT,
)
from services.hyper_ai_memory.serialization import (
    format_existing_memories,
    format_new_memories,
    memory_to_dict,
    valid_memory_candidates,
)

logger = logging.getLogger(__name__)


def get_memories(
    db: Session,
    category: Optional[str] = None,
    limit: int = 20,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Retrieve memories, optionally filtered by category.

    Args:
        db: Database session
        category: Filter by category (None for all)
        limit: Maximum number of memories to return
        active_only: Only return active memories

    Returns:
        List of memory dictionaries
    """
    query = db.query(HyperAiMemory)

    if active_only:
        query = query.filter(HyperAiMemory.is_active == True)

    if category:
        query = query.filter(HyperAiMemory.category == category)

    # Order by importance and recency
    memories = query.order_by(
        HyperAiMemory.importance.desc(),
        HyperAiMemory.created_at.desc()
    ).limit(limit).all()

    return [memory_to_dict(memory) for memory in memories]


def add_memory(
    db: Session,
    category: str,
    content: str,
    source: str = "conversation",
    importance: float = 0.5
) -> HyperAiMemory:
    """
    Add a new memory entry.

    Args:
        db: Database session
        category: Memory category
        content: Memory content
        source: Source of the memory (conversation, compression, manual)
        importance: Importance score (0.0 to 1.0)

    Returns:
        Created memory object
    """
    memory = HyperAiMemory(
        category=category,
        content=content,
        source=source,
        importance=importance,
        is_active=True
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def update_memory(
    db: Session,
    memory_id: int,
    content: Optional[str] = None,
    importance: Optional[float] = None,
    is_active: Optional[bool] = None
) -> Optional[HyperAiMemory]:
    """Update an existing memory."""
    memory = db.query(HyperAiMemory).filter(HyperAiMemory.id == memory_id).first()
    if not memory:
        return None

    if content is not None:
        memory.content = content
    if importance is not None:
        memory.importance = importance
    if is_active is not None:
        memory.is_active = is_active

    memory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(memory)
    return memory


def delete_memory(db: Session, memory_id: int) -> bool:
    """Soft delete a memory by marking it inactive."""
    memory = db.query(HyperAiMemory).filter(HyperAiMemory.id == memory_id).first()
    if not memory:
        return False

    memory.is_active = False
    memory.updated_at = datetime.utcnow()
    db.commit()
    return True


def batch_dedup_memories(
    db: Session,
    new_memories: List[Dict[str, Any]],
    api_config: Dict[str, Any],
    source: str = "compression"
) -> int:
    """
    Batch deduplication: compare all new memories against all existing in 1 LLM call.
    Replaces the old per-memory dedup loop.

    Args:
        new_memories: List of {"category", "content", "importance"} dicts
        api_config: LLM config
        source: Memory source tag

    Returns:
        Number of memories added/updated
    """
    if not new_memories:
        return 0

    # Get all active memories (exclude user_info from onboarding)
    existing = get_memories(db, limit=MAX_MEMORIES)
    existing = [m for m in existing if m.get("category") != "user_info"]

    # If no existing memories, just add all
    if not existing:
        count = 0
        for mem in valid_memory_candidates(new_memories):
            cat = mem.get("category", "context")
            add_memory(db, cat, mem["content"], source, mem.get("importance", 0.5))
            count += 1
        enforce_memory_limit(db)
        return count

    # Build prompt with existing and new memories
    prompt = BATCH_DEDUP_PROMPT.format(
        existing_memories=format_existing_memories(existing),
        new_memories=format_new_memories(new_memories)
    )

    # Single LLM call for all dedup decisions
    actions = _call_llm_for_dedup(prompt, api_config)
    if actions is None:
        # LLM failed, fallback: add all as new
        logger.warning("[Memory] Batch dedup LLM failed, adding all as new")
        count = 0
        for mem in valid_memory_candidates(new_memories):
            cat = mem.get("category", "context")
            add_memory(db, cat, mem["content"], source, mem.get("importance", 0.5))
            count += 1
        enforce_memory_limit(db)
        return count

    # Execute actions
    count = 0
    for act in actions:
        idx = act.get("new_index")
        if idx is None or idx >= len(new_memories):
            continue
        mem = new_memories[idx]
        cat = mem.get("category", "context")
        content = mem.get("content", "")
        importance = mem.get("importance", 0.5)
        if not content or cat not in MEMORY_CATEGORIES:
            continue

        action = act.get("action", "ADD").upper()

        if action == "ADD":
            add_memory(db, cat, content, source, importance)
            count += 1
        elif action == "UPDATE":
            eid = act.get("existing_id")
            merged = act.get("merged") or content
            if eid:
                old = next((m for m in existing if m["id"] == eid), None)
                old_imp = old.get("importance", 0.5) if old else 0.5
                update_memory(db, eid, content=merged, importance=max(importance, old_imp))
                count += 1
            else:
                add_memory(db, cat, content, source, importance)
                count += 1
        elif action == "DELETE":
            eid = act.get("existing_id")
            if eid:
                delete_memory(db, eid)
            add_memory(db, cat, content, source, importance)
            count += 1
        # NONE: discard, do nothing

    enforce_memory_limit(db)
    return count


def _call_llm_for_dedup(
    prompt: str,
    api_config: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """
    Single LLM call for batch deduplication. Returns list of action dicts or None on failure.
    """
    text = call_memory_llm(
        prompt,
        api_config,
        max_tokens=800,
        purpose="Dedup",
        log_incomplete_config=True,
    )
    if text is None:
        return None

    try:
        actions = parse_dedup_actions(text)
    except ValueError as e:
        logger.warning(f"[Memory] Dedup response JSON parse error: {e}")
        return None

    if actions is None:
        logger.warning(f"[Memory] Dedup response not valid JSON: {text[:200]}")
        return None

    return actions


def enforce_memory_limit(db: Session) -> int:
    """
    Enforce MAX_MEMORIES limit by soft-deleting lowest importance memories.
    Excludes user_info category (managed by onboarding).
    Returns number of memories evicted.
    """
    active_count = db.query(HyperAiMemory).filter(
        HyperAiMemory.is_active == True,
        HyperAiMemory.category != "user_info"
    ).count()

    if active_count <= MAX_MEMORIES:
        return 0

    excess = active_count - MAX_MEMORIES
    # Get lowest importance memories to evict
    to_evict = db.query(HyperAiMemory).filter(
        HyperAiMemory.is_active == True,
        HyperAiMemory.category != "user_info"
    ).order_by(
        HyperAiMemory.importance.asc(),
        HyperAiMemory.created_at.asc()
    ).limit(excess).all()

    for m in to_evict:
        m.is_active = False
        m.updated_at = datetime.utcnow()

    db.commit()
    logger.warning(f"[Memory] Evicted {len(to_evict)} memories (limit={MAX_MEMORIES})")
    return len(to_evict)


def extract_memories_from_conversation(
    conversation_text: str,
    api_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extract memories from conversation using LLM.

    Returns:
        List of {"category", "content", "importance"} dicts
    """
    prompt = EXTRACT_MEMORIES_PROMPT.format(
        conversation=conversation_text[:6000]
    )
    text = call_memory_llm(
        prompt,
        api_config,
        max_tokens=500,
        purpose="Extraction",
    )
    if text is None:
        return []

    try:
        return parse_extracted_memories(text)
    except ValueError as e:
        logger.warning(f"[Memory] Extraction response JSON parse error: {e}")

    return []


def process_compression_memories(
    db: Session,
    conversation_text: str,
    api_config: Dict[str, Any]
) -> int:
    """
    Extract and store memories during context compression.
    Uses batch dedup: 1 LLM call for extraction + 1 for dedup = 2 total.

    Returns:
        Number of memories added/updated
    """
    memories = extract_memories_from_conversation(conversation_text, api_config)

    if not memories:
        return 0

    # Filter valid memories
    valid = valid_memory_candidates(memories)

    if not valid:
        return 0

    count = batch_dedup_memories(db, valid, api_config, source="compression")
    logger.warning(f"[Memory] Processed {count} memories from compression (batch mode)")
    return count
