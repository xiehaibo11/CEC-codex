"""
Hyper AI Service - Main Agent for Full-Site AI Intelligence

Hyper AI is the master agent that:
- Guides users through onboarding to collect trading preferences
- Maintains user profile and long-term memory across conversations
- Orchestrates sub-agents (Prompt AI, Program AI, Signal AI, Attribution AI)
- Implements context compression for long conversations
- Supports multiple LLM providers with user selection

Architecture:
- StreamBuffer-based async streaming (same as other AI services)
- Long-term memory auto-injected into system prompt alongside user profile
- Mem0-style batch deduplication for memory management
- Context compression at 70% of context window
- Memory extraction runs async in background thread during compression

This module has been split by responsibility into the ``hyper_ai_service``
package. It remains the public import path: every name that was previously
importable from ``services.hyper_ai_service`` is re-exported below.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Promote this module to a package whose submodules live in hyper_ai_service/.
__path__ = [os.path.join(os.path.dirname(__file__), "hyper_ai_service")]

from services.hyper_ai_service.prompts import (  # noqa: E402
    DEFAULT_ONBOARDING_PROMPT_EN as DEFAULT_ONBOARDING_PROMPT_EN,
    DEFAULT_ONBOARDING_PROMPT_ZH as DEFAULT_ONBOARDING_PROMPT_ZH,
    ONBOARDING_PROMPT_EN_PATH as ONBOARDING_PROMPT_EN_PATH,
    ONBOARDING_PROMPT_ZH_PATH as ONBOARDING_PROMPT_ZH_PATH,
    SYSTEM_PROMPT_PATH as SYSTEM_PROMPT_PATH,
    load_onboarding_prompt as load_onboarding_prompt,
    load_system_prompt as load_system_prompt,
)
from services.hyper_ai_service.retry import (  # noqa: E402
    API_BASE_DELAY as API_BASE_DELAY,
    API_MAX_DELAY as API_MAX_DELAY,
    API_MAX_RETRIES as API_MAX_RETRIES,
    RETRYABLE_STATUS_CODES as RETRYABLE_STATUS_CODES,
    _get_retry_delay as _get_retry_delay,
    _should_retry_api as _should_retry_api,
)
from services.hyper_ai_service.llm_config import (  # noqa: E402
    get_llm_config as get_llm_config,
    get_or_create_profile as get_or_create_profile,
    save_llm_config as save_llm_config,
    test_llm_connection as test_llm_connection,
)
from services.hyper_ai_service.conversations import (  # noqa: E402
    get_conversation_messages as get_conversation_messages,
    get_or_create_conversation as get_or_create_conversation,
    save_message as save_message,
)
from services.hyper_ai_service.context import (  # noqa: E402
    _build_memory_context as _build_memory_context,
    _build_profile_context as _build_profile_context,
    build_messages_for_api as build_messages_for_api,
)
from services.hyper_ai_service.tool_execution import (  # noqa: E402
    SUBAGENT_TOOL_NAMES as SUBAGENT_TOOL_NAMES,
    _await_tool_confirmation as _await_tool_confirmation,
    _execute_harnessed_tool_call as _execute_harnessed_tool_call,
    _tool_error_event_data as _tool_error_event_data,
)
from services.hyper_ai_service.streaming import (  # noqa: E402
    MAX_TOOL_ITERATIONS as MAX_TOOL_ITERATIONS,
    start_chat_task as start_chat_task,
    stream_chat_response as stream_chat_response,
)
from services.hyper_ai_service.onboarding import (  # noqa: E402
    _parse_profile_data as _parse_profile_data,
    _process_onboarding_stream_response as _process_onboarding_stream_response,
    _save_profile_from_onboarding as _save_profile_from_onboarding,
    _strip_profile_markers as _strip_profile_markers,
    start_onboarding_chat_task as start_onboarding_chat_task,
    stream_onboarding_response as stream_onboarding_response,
)
from services.hyper_ai_service.insight import (  # noqa: E402
    _build_insight_messages as _build_insight_messages,
    start_insight_task as start_insight_task,
    stream_insight_response as stream_insight_response,
)
from services.hyper_ai_service.suggestions import (  # noqa: E402
    SUGGESTION_CACHE_HOURS as SUGGESTION_CACHE_HOURS,
    build_suggestions_prompt as build_suggestions_prompt,
    generate_suggested_questions as generate_suggested_questions,
    get_or_update_suggestions as get_or_update_suggestions,
    get_suggestions_context as get_suggestions_context,
)
