"""Prompt template API route entry point."""

from fastapi import APIRouter

from .prompts.ai_chat_routes import (
    AiChatRequest,
    AiChatResponse,
    ai_chat,
    ai_chat_stream,
    get_conversation_messages_api,
    list_ai_conversations,
    router as ai_chat_router,
)
from .prompts.binding_routes import (
    delete_prompt_binding_endpoint,
    router as binding_router,
    upsert_prompt_binding,
)
from .prompts.dependencies import get_db
from .prompts.preview_routes import _generate_single_preview, preview_prompt, router as preview_router
from .prompts.template_routes import (
    copy_prompt_template,
    create_prompt_template,
    delete_prompt_template_endpoint,
    list_prompt_templates,
    router as template_router,
    update_prompt_template,
    update_prompt_template_name,
)
from .prompts.variables_routes import get_variables_reference, router as variables_router

PROMPTS_PREFIX = "/api/prompts"
PROMPTS_TAGS = ["Prompt Templates"]

router = APIRouter()

router.include_router(template_router, prefix=PROMPTS_PREFIX, tags=PROMPTS_TAGS)
router.include_router(binding_router, prefix=PROMPTS_PREFIX, tags=PROMPTS_TAGS)
router.include_router(preview_router, prefix=PROMPTS_PREFIX, tags=PROMPTS_TAGS)
router.include_router(ai_chat_router, prefix=PROMPTS_PREFIX, tags=PROMPTS_TAGS)
router.include_router(variables_router, prefix=PROMPTS_PREFIX, tags=PROMPTS_TAGS)

__all__ = [
    "AiChatRequest",
    "AiChatResponse",
    "PROMPTS_PREFIX",
    "PROMPTS_TAGS",
    "_generate_single_preview",
    "ai_chat",
    "ai_chat_stream",
    "copy_prompt_template",
    "create_prompt_template",
    "delete_prompt_binding_endpoint",
    "delete_prompt_template_endpoint",
    "get_conversation_messages_api",
    "get_db",
    "get_variables_reference",
    "list_ai_conversations",
    "list_prompt_templates",
    "preview_prompt",
    "router",
    "update_prompt_template",
    "update_prompt_template_name",
    "upsert_prompt_binding",
]
