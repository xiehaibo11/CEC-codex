"""
Hyper AI Routes - API endpoints for Hyper AI main agent

Endpoints:
- GET  /api/hyper-ai/providers - List available LLM providers
- GET  /api/hyper-ai/profile - Get user profile and LLM config status
- POST /api/hyper-ai/profile/llm - Save LLM configuration (with connection test)
- POST /api/hyper-ai/test-connection - Test LLM connection without saving
- POST /api/hyper-ai/profile/preferences - Save trading preferences
- GET  /api/hyper-ai/conversations - List conversations
- POST /api/hyper-ai/conversations - Create new conversation
- GET  /api/hyper-ai/conversations/{id}/messages - Get conversation messages
- POST /api/hyper-ai/chat - Start chat (returns task_id for polling)
- GET  /api/hyper-ai/skills - List all skills with enabled status
- PUT  /api/hyper-ai/skills/{name}/toggle - Enable/disable a skill
- GET  /api/hyper-ai/tools - List external tools with config status
- PUT  /api/hyper-ai/tools/{tool_name}/config - Save tool configuration
- DELETE /api/hyper-ai/tools/{tool_name}/config - Remove tool configuration
"""
from fastapi import APIRouter

from .hyper_ai.conversation_routes import router as conversation_router
from .hyper_ai.memory_routes import router as memory_router
from .hyper_ai.profile_routes import router as profile_router
from .hyper_ai.skill_routes import router as skill_router
from .hyper_ai.tool_routes import router as tool_router

router = APIRouter(prefix="/api/hyper-ai", tags=["Hyper AI"])

router.include_router(profile_router)
router.include_router(conversation_router)
router.include_router(memory_router)
router.include_router(skill_router)
router.include_router(tool_router)
