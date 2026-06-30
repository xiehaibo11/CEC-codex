"""Shared APIRouter for Bot Integration routes.

Defined in one place so that each endpoint module can import and decorate the
same router instance, keeping prefix/tags consistent across the package.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/bot", tags=["Bot Integration"])
