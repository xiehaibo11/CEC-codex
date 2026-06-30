from typing import Any, Dict, Optional

from pydantic import BaseModel


class LLMConfigRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None


class PreferencesRequest(BaseModel):
    trading_style: Optional[str] = None
    risk_preference: Optional[str] = None
    experience_level: Optional[str] = None
    preferred_symbols: Optional[str] = None
    preferred_timeframe: Optional[str] = None
    capital_scale: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    mode: Optional[str] = None  # "onboarding" for profile collection
    lang: Optional[str] = None  # "zh" or "en" for language preference


class InsightRequest(BaseModel):
    context: Dict[str, Any]
    selected_event: Optional[Dict[str, Any]] = None
    lang: Optional[str] = None


class ConfirmationRequest(BaseModel):
    task_id: str
    confirmation_id: str
    confirmed: bool


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None


class SkillToggleRequest(BaseModel):
    enabled: bool


class ToolConfigRequest(BaseModel):
    config: dict  # {"api_key": "tvly-xxx", ...}
    validate_key: bool = True
