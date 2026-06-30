"""JSON parsing helpers for Hyper AI memory LLM responses."""

import json
import re
from typing import Any, Dict, List, Optional


def extract_json_object(text: str) -> Optional[str]:
    """Extract the first JSON object-looking payload from an LLM response."""
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        return None
    return json_match.group()


def parse_dedup_actions(text: str) -> Optional[List[Dict[str, Any]]]:
    """Parse batch dedup actions, returning None when no JSON object exists."""
    json_text = extract_json_object(text)
    if not json_text:
        return None
    result = json.loads(json_text)
    return result.get("actions", [])


def parse_extracted_memories(text: str) -> List[Dict[str, Any]]:
    """Parse extracted memory objects from an LLM response."""
    json_text = extract_json_object(text)
    if not json_text:
        return []
    result = json.loads(json_text)
    return result.get("memories", [])
