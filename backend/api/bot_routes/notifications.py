"""Bot push notification configuration endpoints and helpers."""
import json

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db

from ._router import router


NOTIFICATION_CONFIG_KEY = "bot_notification_config"
DEFAULT_NOTIFICATION_CONFIG = {
    "ai_trader": True,
    "program_trader": True,
    "signal_pools": {}  # pool_id -> bool, default all False
}


class NotificationConfigRequest(BaseModel):
    ai_trader: bool = True
    program_trader: bool = True
    signal_pools: dict = {}  # {"pool_id": true/false}


@router.get("/notification-config")
def get_notification_config(db: Session = Depends(get_db)):
    """Get bot push notification configuration."""
    from database.models import SystemConfig
    config = db.query(SystemConfig).filter(
        SystemConfig.key == NOTIFICATION_CONFIG_KEY
    ).first()
    if not config:
        return {"config": DEFAULT_NOTIFICATION_CONFIG}
    try:
        return {"config": json.loads(config.value)}
    except json.JSONDecodeError:
        return {"config": DEFAULT_NOTIFICATION_CONFIG}


@router.put("/notification-config")
def update_notification_config(
    request: NotificationConfigRequest,
    db: Session = Depends(get_db)
):
    """Update bot push notification configuration."""
    from database.models import SystemConfig
    config_data = {
        "ai_trader": request.ai_trader,
        "program_trader": request.program_trader,
        "signal_pools": request.signal_pools,
    }
    config = db.query(SystemConfig).filter(
        SystemConfig.key == NOTIFICATION_CONFIG_KEY
    ).first()
    if config:
        config.value = json.dumps(config_data)
    else:
        config = SystemConfig(
            key=NOTIFICATION_CONFIG_KEY,
            value=json.dumps(config_data)
        )
        db.add(config)
    db.commit()
    return {"success": True, "config": config_data}


def get_notification_config_dict(db: Session) -> dict:
    """Helper function to get notification config as dict (for use in hooks)."""
    from database.models import SystemConfig
    config = db.query(SystemConfig).filter(
        SystemConfig.key == NOTIFICATION_CONFIG_KEY
    ).first()
    if not config:
        return DEFAULT_NOTIFICATION_CONFIG.copy()
    try:
        return json.loads(config.value)
    except json.JSONDecodeError:
        return DEFAULT_NOTIFICATION_CONFIG.copy()
