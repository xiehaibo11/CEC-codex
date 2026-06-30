"""LLM prompts for Hyper AI memory management."""

BATCH_DEDUP_PROMPT = """You are a memory deduplication assistant for a crypto trading AI.

## Existing Memories (already stored):
{existing_memories}

## New Memories (candidates to add):
{new_memories}

For EACH new memory, decide ONE action by comparing against ALL existing memories:
- ADD: New memory is different and valuable, add it
- UPDATE: New memory refines/updates an existing one. Provide existing_id and merged content
- DELETE: New memory contradicts/replaces an existing one. Provide existing_id to delete, then add new
- NONE: New memory is redundant/duplicate of existing, discard it

Respond in JSON only:
{{"actions": [
  {{"new_index": 0, "action": "ADD"}},
  {{"new_index": 1, "action": "UPDATE", "existing_id": 4, "merged": "merged content here"}},
  {{"new_index": 2, "action": "NONE"}},
  {{"new_index": 3, "action": "DELETE", "existing_id": 8}}
]}}"""


EXTRACT_MEMORIES_PROMPT = """You are a memory extraction assistant for a crypto trading AI platform.
Analyze this conversation and extract key user insights worth remembering long-term.

Conversation:
{conversation}

## Categories and what to extract:

**preference** (importance 0.7-0.9):
- Trading style (scalping, swing, intraday), risk tolerance, leverage preferences
- Preferred coins/pairs, timeframes, position sizing rules
- Daily routines (e.g. close all positions before UTC 23:30)

**decision** (importance 0.6-0.8):
- Strategy parameters chosen (e.g. EMA periods, RSI thresholds, TP/SL percentages)
- Specific trading rules or conditions the user confirmed
- Configuration changes (e.g. switched model, changed leverage from 5x to 3x)

**lesson** (importance 0.7-0.9):
- Losses or mistakes and what the user learned
- What worked well and why
- Market behavior patterns the user identified

**insight** (importance 0.5-0.7):
- Market observations (e.g. "BTC tends to dump after funding rate > 0.1%")
- Correlations or patterns discussed
- Backtesting results and conclusions

## Rules:
- Each memory should be specific and self-contained (readable without context)
- Include concrete numbers/parameters when available
- Max 5 memories per extraction, only truly important ones
- If nothing significant, return empty list

Respond in JSON:
{{"memories": [{{"category": "...", "content": "...", "importance": 0.8}}]}}"""
