from __future__ import annotations

from pydantic import BaseModel, Field


class CoinGlassKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=16, max_length=200)
