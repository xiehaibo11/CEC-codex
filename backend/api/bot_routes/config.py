"""Bot configuration CRUD endpoints (generic, platform-agnostic)."""
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from services.bot_service import (
    get_bot_config,
    get_all_bot_configs,
    save_bot_config,
    update_bot_status,
    delete_bot_config,
)

from ._router import router


class BotConfigRequest(BaseModel):
    platform: str  # telegram / discord / whatsapp / wechat / etc.
    bot_token: str
    bot_username: Optional[str] = None
    bot_app_id: Optional[str] = None


class BotStatusRequest(BaseModel):
    platform: str
    status: str  # disconnected / connecting / connected / error
    error_message: Optional[str] = None


@router.get("/configs")
def list_bot_configs(db: Session = Depends(get_db)):
    """List all bot configurations."""
    return {"configs": get_all_bot_configs(db)}


@router.get("/config/{platform}")
def get_bot_config_endpoint(platform: str, db: Session = Depends(get_db)):
    """Get bot configuration for a specific platform."""
    config = get_bot_config(db, platform)
    if not config:
        return {"config": None, "configured": False}
    return {"config": config, "configured": True}


@router.post("/config")
def save_bot_config_endpoint(request: BotConfigRequest, db: Session = Depends(get_db)):
    """Save or update bot configuration."""
    # Validate platform - allow known platforms (new platforms should be added here)
    known_platforms = ["telegram", "discord", "whatsapp", "wechat"]
    if request.platform not in known_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Must be one of: {', '.join(known_platforms)}")

    if not request.bot_token:
        raise HTTPException(status_code=400, detail="Bot token is required")

    config = save_bot_config(
        db=db,
        platform=request.platform,
        bot_token=request.bot_token,
        bot_username=request.bot_username,
        bot_app_id=request.bot_app_id,
    )
    return {"success": True, "config": config}


@router.put("/status")
def update_bot_status_endpoint(request: BotStatusRequest, db: Session = Depends(get_db)):
    """Update bot connection status."""
    success = update_bot_status(
        db=db,
        platform=request.platform,
        status=request.status,
        error_message=request.error_message,
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Bot config for {request.platform} not found")
    return {"success": True}


@router.delete("/config/{platform}")
def delete_bot_config_endpoint(platform: str, db: Session = Depends(get_db)):
    """Delete bot configuration."""
    success = delete_bot_config(db, platform)
    if not success:
        raise HTTPException(status_code=404, detail=f"Bot config for {platform} not found")
    return {"success": True}
