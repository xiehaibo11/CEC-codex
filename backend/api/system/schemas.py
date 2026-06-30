"""Schemas for system API routes."""

from pydantic import BaseModel


class RetentionDaysRequest(BaseModel):
    days: int
    exchange: str = "hyperliquid"


class RetentionDaysResponse(BaseModel):
    days: int
    exchange: str = "hyperliquid"
