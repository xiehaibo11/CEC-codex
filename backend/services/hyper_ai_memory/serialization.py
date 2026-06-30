"""Serialization and formatting helpers for Hyper AI memories."""

from typing import Any, Dict, Iterable, List

from services.hyper_ai_memory.constants import MEMORY_CATEGORIES


def memory_to_dict(memory: Any) -> Dict[str, Any]:
    """Convert a HyperAiMemory ORM object into the API dictionary shape."""
    return {
        "id": memory.id,
        "category": memory.category,
        "content": memory.content,
        "source": memory.source,
        "importance": memory.importance,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
    }


def format_existing_memories(memories: Iterable[Dict[str, Any]]) -> str:
    """Format stored memories for the batch dedup prompt."""
    return "\n".join(
        f"[ID:{memory['id']}] ({memory['category']}) {memory['content']}"
        for memory in memories
    )


def format_new_memories(memories: Iterable[Dict[str, Any]]) -> str:
    """Format candidate memories for the batch dedup prompt."""
    return "\n".join(
        f"[{index}] ({memory.get('category', 'context')}) {memory.get('content', '')}"
        for index, memory in enumerate(memories)
    )


def valid_memory_candidates(memories: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return candidates that have content and a supported category."""
    return [
        memory
        for memory in memories
        if memory.get("content")
        and memory.get("category", "context") in MEMORY_CATEGORIES
    ]
