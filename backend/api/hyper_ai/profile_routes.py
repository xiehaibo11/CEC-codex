from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from services.hyper_ai_llm_providers import get_all_providers, get_provider
from services.hyper_ai_service import (
    get_llm_config,
    get_or_create_profile,
    save_llm_config,
    test_llm_connection,
)

from .schemas import LLMConfigRequest, PreferencesRequest, TestConnectionRequest

router = APIRouter()


@router.get("/providers")
def list_providers():
    """List all available LLM providers with their configurations."""
    return {"providers": get_all_providers()}


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    """Get user profile including LLM config status and trading preferences."""
    profile = get_or_create_profile(db)
    llm_config = get_llm_config(db)

    # Get base_url for display
    base_url = llm_config.get("base_url", "") if llm_config.get("configured") else ""

    return {
        "llm_configured": llm_config.get("configured", False),
        "llm_provider": profile.llm_provider,
        "llm_model": profile.llm_model,
        "llm_base_url": base_url,
        "onboarding_completed": profile.onboarding_completed,
        "nickname": profile.nickname,
        "trading_style": profile.trading_style,
        "risk_preference": profile.risk_preference,
        "experience_level": profile.experience_level,
        "preferred_symbols": profile.preferred_symbols,
        "preferred_timeframe": profile.preferred_timeframe,
        "capital_scale": profile.capital_scale,
    }


@router.post("/test-connection")
def test_connection(request: TestConnectionRequest):
    """Test LLM connection without saving configuration."""
    # Validate provider
    if request.provider != "custom":
        provider = get_provider(request.provider)
        if not provider:
            raise HTTPException(status_code=400, detail="Invalid provider")

    # For custom provider, base_url is required
    if request.provider == "custom" and not request.base_url:
        raise HTTPException(
            status_code=400,
            detail="base_url is required for custom provider"
        )

    # Get default model if not provided
    model = request.model
    if not model and request.provider != "custom":
        provider = get_provider(request.provider)
        if provider and provider.models:
            model = provider.models[0]

    result = test_llm_connection(
        provider=request.provider,
        api_key=request.api_key,
        model=model or "",
        base_url=request.base_url
    )

    return result


@router.post("/profile/llm")
def save_llm_configuration(request: LLMConfigRequest, db: Session = Depends(get_db)):
    """Save LLM provider configuration after testing connection."""
    # Validate provider
    if request.provider != "custom":
        provider = get_provider(request.provider)
        if not provider:
            raise HTTPException(status_code=400, detail="Invalid provider")

    # For custom provider, base_url is required
    if request.provider == "custom" and not request.base_url:
        raise HTTPException(
            status_code=400,
            detail="base_url is required for custom provider"
        )

    # Get default model if not provided
    model = request.model
    if not model and request.provider != "custom":
        provider = get_provider(request.provider)
        if provider and provider.models:
            model = provider.models[0]

    # Test connection before saving
    test_result = test_llm_connection(
        provider=request.provider,
        api_key=request.api_key,
        model=model or "",
        base_url=request.base_url
    )

    if not test_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=test_result.get("error", "Connection test failed")
        )

    # Save configuration
    profile = save_llm_config(
        db,
        provider=request.provider,
        api_key=request.api_key,
        model=model,
        base_url=request.base_url
    )

    return {"success": True, "provider": profile.llm_provider, "model": profile.llm_model}


@router.post("/profile/preferences")
def save_preferences(request: PreferencesRequest, db: Session = Depends(get_db)):
    """Save trading preferences and mark onboarding as completed."""
    profile = get_or_create_profile(db)

    if request.trading_style is not None:
        profile.trading_style = request.trading_style
    if request.risk_preference is not None:
        profile.risk_preference = request.risk_preference
    if request.experience_level is not None:
        profile.experience_level = request.experience_level
    if request.preferred_symbols is not None:
        profile.preferred_symbols = request.preferred_symbols
    if request.preferred_timeframe is not None:
        profile.preferred_timeframe = request.preferred_timeframe
    if request.capital_scale is not None:
        profile.capital_scale = request.capital_scale

    # Mark onboarding as completed if we have basic info
    if profile.trading_style and profile.risk_preference:
        profile.onboarding_completed = True

    db.commit()
    db.refresh(profile)

    return {
        "success": True,
        "onboarding_completed": profile.onboarding_completed
    }


@router.get("/suggestions")
def get_suggestions(db: Session = Depends(get_db)):
    """
    Get suggested questions for welcome screen.
    Returns cached suggestions or triggers async update if stale (>6 hours).
    For new users (no conversations), returns is_new_user=True.
    """
    from services.hyper_ai_service import get_or_update_suggestions
    return get_or_update_suggestions(db)
