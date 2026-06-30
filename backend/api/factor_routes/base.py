"""
Shared router and DB-session dependency for the factor routes package.

The single APIRouter defined here is imported and decorated by every endpoint
module in this package. Importing those modules (done in __init__.py) registers
their routes on this router.
"""

from fastapi import APIRouter

from database.connection import SessionLocal

router = APIRouter(prefix="/api/factors", tags=["factors"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
