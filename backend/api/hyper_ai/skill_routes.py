from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from services.hyper_ai_service import get_or_create_profile

from .schemas import SkillToggleRequest

router = APIRouter()


@router.get("/skills")
def list_skills(db: Session = Depends(get_db)):
    """List all available skills with their enabled/disabled status."""
    from services.hyper_ai_skill_engine import scan_all_skills, get_enabled_skills

    all_skills = scan_all_skills()
    profile = get_or_create_profile(db)
    enabled = get_enabled_skills(all_skills, profile.enabled_skills)
    enabled_names = {s["name"] for s in enabled}

    return {
        "skills": [
            {
                "name": s["name"],
                "description": s["description"],
                "description_zh": s.get("description_zh", ""),
                "command": f"/{s.get('shortcut') or s['name']}",
                "enabled": s["name"] in enabled_names,
            }
            for s in all_skills
        ]
    }


@router.put("/skills/{skill_name}/toggle")
def toggle_skill(skill_name: str, body: SkillToggleRequest, db: Session = Depends(get_db)):
    """Enable or disable a specific skill for the current user."""
    import json as _json
    from services.hyper_ai_skill_engine import scan_all_skills

    all_skills = scan_all_skills()
    valid_names = {s["name"] for s in all_skills}
    if skill_name not in valid_names:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    profile = get_or_create_profile(db)

    # Parse current enabled list (None = all enabled)
    if profile.enabled_skills is None:
        current = [s["name"] for s in all_skills]
    else:
        try:
            current = _json.loads(profile.enabled_skills)
        except (ValueError, TypeError):
            current = [s["name"] for s in all_skills]

    if body.enabled and skill_name not in current:
        current.append(skill_name)
    elif not body.enabled and skill_name in current:
        current.remove(skill_name)

    # If all skills enabled, store None (default behavior)
    if set(current) == valid_names:
        profile.enabled_skills = None
    else:
        profile.enabled_skills = _json.dumps(current)

    db.commit()
    return {"success": True, "skill_name": skill_name, "enabled": body.enabled}
