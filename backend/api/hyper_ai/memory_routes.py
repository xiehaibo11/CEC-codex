from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db

router = APIRouter()


@router.get("/memories")
def list_memories(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List user memories, optionally filtered by category."""
    from services.hyper_ai_memory_service import get_memories, MEMORY_CATEGORIES

    if category and category not in MEMORY_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Valid: {MEMORY_CATEGORIES}")

    memories = get_memories(db, category=category, limit=limit)
    return {"memories": memories, "categories": MEMORY_CATEGORIES}


@router.delete("/memories/{memory_id}")
def delete_memory_endpoint(memory_id: int, db: Session = Depends(get_db)):
    """Delete (deactivate) a memory."""
    from services.hyper_ai_memory_service import delete_memory

    success = delete_memory(db, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"success": True}
