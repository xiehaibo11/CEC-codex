"""
Custom factor CRUD routes.

GET    /api/factors/custom              → List user-created custom factors
POST   /api/factors/custom              → Create a custom factor expression
DELETE /api/factors/custom/{factor_id}  → Delete a custom factor
PUT    /api/factors/custom/{factor_id}  → Edit an existing custom factor
"""

from typing import Optional

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import CustomFactor
from services.factor_expression_engine import factor_expression_engine

from .base import router, get_db


class CustomFactorRequest(BaseModel):
    name: str
    expression: str
    description: str = ""
    category: str = "custom"
    source: str = "manual"


@router.get("/custom")
async def list_custom_factors(db: Session = Depends(get_db)):
    """List user-created custom factors (excludes builtin_expression)."""
    rows = db.query(CustomFactor).filter(
        CustomFactor.source != 'builtin_expression'
    ).order_by(CustomFactor.created_at.desc()).all()
    return {
        "items": [
            {
                "id": r.id, "name": r.name, "expression": r.expression,
                "description": r.description, "category": r.category,
                "source": r.source, "is_active": r.is_active,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/custom")
async def create_custom_factor(req: CustomFactorRequest, db: Session = Depends(get_db)):
    """Save a custom factor expression."""
    import re
    # Validate factor name: English letters, digits, underscores only
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', req.name):
        return {"status": "error", "error": "Factor name must start with a letter and contain only English letters, digits, and underscores (e.g., RSI_fast, momentum_v2)"}

    # Validate expression syntax
    ok, err = factor_expression_engine.validate(req.expression)
    if not ok:
        return {"status": "error", "error": err}

    # Check duplicate name
    existing = db.query(CustomFactor).filter(CustomFactor.name == req.name).first()
    if existing:
        return {"status": "error", "error": f"Factor name '{req.name}' already exists"}

    factor = CustomFactor(
        name=req.name,
        expression=req.expression,
        description=req.description,
        category=req.category,
        source=req.source,
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return {"status": "ok", "id": factor.id, "name": factor.name}


@router.delete("/custom/{factor_id}")
async def delete_custom_factor(factor_id: int, db: Session = Depends(get_db)):
    """Delete a custom factor."""
    factor = db.query(CustomFactor).filter(CustomFactor.id == factor_id).first()
    if not factor:
        return {"status": "error", "error": "Factor not found"}
    db.delete(factor)
    db.commit()
    return {"status": "ok"}


class EditCustomFactorRequest(BaseModel):
    name: Optional[str] = None
    expression: Optional[str] = None
    description: Optional[str] = None


@router.put("/custom/{factor_id}")
async def edit_custom_factor(factor_id: int, req: EditCustomFactorRequest, db: Session = Depends(get_db)):
    """Edit an existing custom factor."""
    factor = db.query(CustomFactor).filter(CustomFactor.id == factor_id).first()
    if not factor:
        return {"status": "error", "error": "Factor not found"}

    if req.expression:
        ok, err = factor_expression_engine.validate(req.expression)
        if not ok:
            return {"status": "error", "error": err}
        factor.expression = req.expression

    if req.name:
        dup = db.query(CustomFactor).filter(
            CustomFactor.name == req.name, CustomFactor.id != factor_id
        ).first()
        if dup:
            return {"status": "error", "error": f"Factor name '{req.name}' already exists"}
        factor.name = req.name

    if req.description is not None:
        factor.description = req.description

    db.commit()
    db.refresh(factor)
    return {"status": "ok", "id": factor.id, "name": factor.name}
