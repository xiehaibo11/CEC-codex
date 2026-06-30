from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from services.ai_stream_service import get_buffer_manager

from .schemas import ConfirmationRequest, ToolConfigRequest

router = APIRouter()


@router.post("/confirm-tool")
def confirm_tool(request: ConfirmationRequest):
    """Submit a runtime checkpoint response for a pending Hyper AI tool call."""
    manager = get_buffer_manager()
    accepted = manager.submit_confirmation(
        request.task_id,
        request.confirmation_id,
        request.confirmed,
    )
    if not accepted:
        raise HTTPException(status_code=404, detail="No matching pending confirmation")
    return {"success": True}


@router.get("/tools")
def list_tools(db: Session = Depends(get_db)):
    """List all registered external tools with their config status."""
    from services.hyper_ai_tool_registry import (
        EXTERNAL_TOOL_REGISTRY, get_tool_configs,
    )

    configs = get_tool_configs(db)
    tools = []
    for name, meta in EXTERNAL_TOOL_REGISTRY.items():
        tool_cfg = configs.get(name, {})
        has_key = bool(tool_cfg.get("api_key_encrypted"))
        tools.append({
            "name": name,
            "display_name": meta["display_name"],
            "display_name_zh": meta.get("display_name_zh", meta["display_name"]),
            "description": meta["description"],
            "description_zh": meta.get("description_zh", meta["description"]),
            "icon": meta.get("icon", "wrench"),
            "config_fields": meta["config_fields"],
            "get_url": meta.get("get_url"),
            "get_url_label": meta.get("get_url_label"),
            "get_url_label_zh": meta.get("get_url_label_zh"),
            "configured": has_key,
            "enabled": tool_cfg.get("enabled", False),
        })
    return {"tools": tools}


@router.put("/tools/{tool_name}/config")
async def save_tool_config(
    tool_name: str, body: ToolConfigRequest, db: Session = Depends(get_db)
):
    """Save configuration for an external tool. Optionally validates the key."""
    from services.hyper_ai_tool_registry import (
        EXTERNAL_TOOL_REGISTRY, TOOL_VALIDATORS, set_tool_api_key,
    )

    if tool_name not in EXTERNAL_TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    api_key = body.config.get("api_key", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Optional validation
    if body.validate_key and tool_name in TOOL_VALIDATORS:
        ok, err = await TOOL_VALIDATORS[tool_name](api_key)
        if not ok:
            return {"success": False, "error": err}

    set_tool_api_key(db, tool_name, api_key)
    return {"success": True, "tool_name": tool_name}


@router.delete("/tools/{tool_name}/config")
def delete_tool_config(tool_name: str, db: Session = Depends(get_db)):
    """Remove configuration for an external tool."""
    from services.hyper_ai_tool_registry import (
        EXTERNAL_TOOL_REGISTRY, remove_tool_config,
    )

    if tool_name not in EXTERNAL_TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    remove_tool_config(db, tool_name)
    return {"success": True, "tool_name": tool_name}
