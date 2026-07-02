"""Signal config extraction helpers."""
import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def extract_signal_configs(content: str) -> List[Dict]:
    """Extract signal configurations from AI response.

    Supports two formats:
    - signal-config: Single signal configuration
    - signal-pool-config: Signal pool with multiple signals

    Parsing priority:
    1. Exact code block format (```signal-config / ```signal-pool-config)
    2. Fallback: ```json code block
    3. Fallback: Plain JSON object detection

    Returns list of configs with '_type' field: 'signal' or 'pool'
    """
    configs = []

    # === Priority 1: Exact code block format (existing logic, preserved) ===
    signal_pattern = r"```signal-config\s*([\s\S]*?)```"
    signal_matches = re.findall(signal_pattern, content)

    for match in signal_matches:
        try:
            config = json.loads(match.strip())
            config["_type"] = "signal"
            configs.append(config)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse signal config: {e}")
            continue

    pool_pattern = r"```signal-pool-config\s*([\s\S]*?)```"
    pool_matches = re.findall(pool_pattern, content)

    for match in pool_matches:
        try:
            config = json.loads(match.strip())
            config["_type"] = "pool"
            configs.append(config)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse signal pool config: {e}")
            continue

    # If exact match succeeded, return immediately
    if configs:
        return configs

    # === Priority 2: Fallback parsing (only when exact match fails) ===
    logger.info("No exact code block match, attempting fallback parsing")

    # Try ```json code block first
    json_pattern = r"```json\s*([\s\S]*?)```"
    json_matches = re.findall(json_pattern, content)

    for match in json_matches:
        config = _try_parse_signal_json(match.strip())
        if config:
            configs.append(config)

    if configs:
        return configs

    # Try plain JSON object detection using bracket matching
    # Find { "name": pattern and extract complete JSON object
    json_start_pattern = r'\{\s*"name"\s*:'
    for match in re.finditer(json_start_pattern, content):
        start_idx = match.start()
        json_obj = _extract_balanced_json(content, start_idx)
        if json_obj:
            config = _try_parse_signal_json(json_obj)
            if config:
                configs.append(config)
                break  # Only take the first valid plain JSON to avoid duplicates

    return configs


def _extract_balanced_json(content: str, start_idx: int) -> Optional[str]:
    """Extract a complete JSON object using bracket matching.

    Starting from start_idx (which should be at '{'), finds the matching '}'.
    """
    if start_idx >= len(content) or content[start_idx] != '{':
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(content)):
        char = content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return content[start_idx:i + 1]

    return None  # Unbalanced brackets


def _try_parse_signal_json(json_str: str) -> Optional[Dict]:
    """Try to parse a JSON string as signal config.

    Determines type based on content:
    - Has 'signals' array -> pool
    - Has 'trigger_condition' -> signal
    - Has 'logic' field -> pool
    - Otherwise -> signal (default)
    """
    try:
        config = json.loads(json_str)
        if not isinstance(config, dict):
            return None

        # Must have 'name' field to be a valid signal config
        if "name" not in config:
            return None

        # Determine type based on content
        if "signals" in config and isinstance(config.get("signals"), list):
            config["_type"] = "pool"
        elif "logic" in config:
            config["_type"] = "pool"
        elif "trigger_condition" in config:
            config["_type"] = "signal"
        else:
            # Default to signal for simple configs
            config["_type"] = "signal"

        logger.info(f"Fallback parsing succeeded: type={config['_type']}, name={config.get('name')}")
        return config

    except json.JSONDecodeError as e:
        logger.warning(f"Fallback JSON parse failed: {e}")
        return None
