"""System and onboarding prompt loading for Hyper AI.

Holds the prompt file paths, default onboarding fallbacks, and the loader
functions. The paths resolve to ``backend/config`` regardless of where this
module physically lives inside the package.
"""
import logging
import os

logger = logging.getLogger(__name__)

# backend/ directory (this file lives at backend/services/hyper_ai_service/prompts.py)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# System prompt paths
SYSTEM_PROMPT_PATH = os.path.join(
    _BACKEND_DIR,
    "config",
    "hyper_ai_system_prompt.md"
)
ONBOARDING_PROMPT_EN_PATH = os.path.join(
    _BACKEND_DIR,
    "config",
    "hyper_ai_onboarding_prompt.md"
)
ONBOARDING_PROMPT_ZH_PATH = os.path.join(
    _BACKEND_DIR,
    "config",
    "hyper_ai_onboarding_prompt_zh.md"
)


def load_system_prompt() -> str:
    """Load the Hyper AI system prompt from markdown file."""
    try:
        with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load Hyper AI system prompt: {e}")
        return "You are Hyper AI, an intelligent trading assistant."


def load_onboarding_prompt(lang: str = "en") -> str:
    """Load the onboarding-specific system prompt based on language."""
    prompt_path = ONBOARDING_PROMPT_ZH_PATH if lang == "zh" else ONBOARDING_PROMPT_EN_PATH
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load onboarding prompt ({lang}): {e}")
        if lang == "zh":
            return DEFAULT_ONBOARDING_PROMPT_ZH
        return DEFAULT_ONBOARDING_PROMPT_EN


DEFAULT_ONBOARDING_PROMPT_EN = """You are Hyper AI, a friendly trading assistant helping a new user get started.

Your goal is to have a natural conversation to learn about the user's trading background and preferences.

Information to collect (through natural conversation, not interrogation):
- Trading experience level (beginner/intermediate/advanced)
- Risk preference (conservative/moderate/aggressive)
- Trading style (day trading/swing trading/position trading/scalping)
- Preferred trading symbols (BTC, ETH, SOL, etc.)

Be warm, conversational, and helpful. Ask follow-up questions naturally.
When you have enough information, let the user know they're all set to explore the system.
"""

DEFAULT_ONBOARDING_PROMPT_ZH = """你是 Hyper AI，一个友好的交易助手，正在帮助新用户入门。

你的目标是通过自然的对话了解用户的交易背景和偏好。

需要收集的信息（通过自然对话，而不是审问）：
- 交易经验水平（新手/有一定经验/资深）
- 风险偏好（保守/稳健/激进）
- 交易风格（日内交易/波段交易/趋势交易/超短线）
- 偏好的交易品种（BTC、ETH、SOL 等）

保持温暖、对话式的风格，自然地提出后续问题。
当你收集到足够的信息后，告诉用户他们已经准备好探索系统了。
"""
