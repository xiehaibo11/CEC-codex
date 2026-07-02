"""
Core helpers for AI prompt generation.
"""
import logging
import os
import random
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Retry configuration for API calls
API_MAX_RETRIES = 5
API_BASE_DELAY = 1.0  # seconds
API_MAX_DELAY = 16.0  # seconds
RETRYABLE_STATUS_CODES = {502, 503, 504, 429}


def _should_retry_api(status_code: Optional[int], error: Optional[str]) -> bool:
    """Check if API error is retryable."""
    if status_code and status_code in RETRYABLE_STATUS_CODES:
        return True
    if error and any(x in error.lower() for x in ["timeout", "connection", "reset", "eof"]):
        return True
    return False


def _get_retry_delay(attempt: int) -> float:
    """Calculate retry delay with exponential backoff and jitter."""
    delay = min(API_BASE_DELAY * (2 ** attempt), API_MAX_DELAY)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter


# Path to system prompt file
SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "prompt_generation_system_prompt.md",
)

# Path to variables reference file
VARIABLES_REFERENCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "PROMPT_VARIABLES_REFERENCE.md",
)


def load_system_prompt() -> str:
    """Load the system prompt from markdown file."""
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}")
        return "You are a trading strategy prompt generation assistant."


def load_variables_reference() -> str:
    """Load the variables reference document."""
    try:
        with open(VARIABLES_REFERENCE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load variables reference: {e}")
        return "Variables reference not available."


def extract_prompt_from_response(content: str) -> Optional[str]:
    """Extract prompt content from AI response.

    Parsing priority:
    1. Exact ```prompt code block
    2. Fallback: Generic code block (``` without language)
    3. Fallback: Detect prompt structure markers (=== sections)

    Returns extracted prompt text or None.
    """
    # === Priority 1: Exact ```prompt code block ===
    pattern = r"```prompt\s*\n(.*?)\n```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # === Priority 2: Generic code block without language specifier ===
    # Match ``` followed by newline (not ```json, ```python, etc.)
    generic_pattern = r"```\s*\n(.*?)\n```"
    matches = re.findall(generic_pattern, content, re.DOTALL)
    for match_content in matches:
        # Check if it looks like a prompt (has section markers)
        if _looks_like_prompt(match_content):
            logger.info("Fallback: extracted prompt from generic code block")
            return match_content.strip()

    # === Priority 3: Detect prompt structure in plain text ===
    # Look for content with prompt section markers
    if _looks_like_prompt(content):
        # Try to extract the prompt portion
        # Find first section marker and last section content
        section_pattern = r"(===\s*[A-Z][A-Z\s]+===)"
        sections = re.findall(section_pattern, content)
        if len(sections) >= 2:
            # Find the span of prompt content
            first_section = re.search(section_pattern, content)
            if first_section:
                # Extract from first section to end, but trim trailing non-prompt text
                prompt_start = first_section.start()
                prompt_content = content[prompt_start:]
                # Trim common AI closing remarks
                closing_patterns = [
                    r"\n\n\*\*Explanation",
                    r"\n\nThis prompt",
                    r"\n\nI hope this",
                    r"\n\nLet me know",
                    r"\n\nFeel free",
                    r"\n\n---\n",
                ]
                for cp in closing_patterns:
                    closing_match = re.search(cp, prompt_content, re.IGNORECASE)
                    if closing_match:
                        prompt_content = prompt_content[:closing_match.start()]
                        break
                if prompt_content.strip():
                    logger.info("Fallback: extracted prompt from plain text with section markers")
                    return prompt_content.strip()

    return None


def _looks_like_prompt(text: str) -> bool:
    """Check if text looks like a trading prompt.

    Heuristics:
    - Has section markers (=== SECTION NAME ===)
    - Has variable placeholders ({variable_name})
    """
    # Must have at least one section marker
    has_section = bool(re.search(r"===\s*[A-Z][A-Z\s]+===", text))
    # Should have variable placeholders
    has_variables = bool(re.search(r"\{[a-zA-Z_]+\}", text))
    return has_section and has_variables
