"""MicroCompact — per-turn tool result trimming.

Runs BEFORE tool results are added to the message history.
Large results get trimmed to a maximum length with a truncation note.
Old results (earlier than N turns ago) get trimmed more aggressively.
"""

from __future__ import annotations

from typing import Any

# Maximum chars for a fresh tool result
MAX_TOOL_RESULT_CHARS: int = 4000

# Maximum chars for a tool result older than RECENT_TURNS
MAX_OLD_TOOL_RESULT_CHARS: int = 1500

# How many recent turns to keep at full length
RECENT_TURNS: int = 4


def trim_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trim tool result messages to prevent context bloat.

    This mutates the list in-place but also returns it for convenience.

    Rules:
    1. Tool results in the most recent RECENT_TURNS messages get trimmed to
       MAX_TOOL_RESULT_CHARS.
    2. Older tool results get trimmed to MAX_OLD_TOOL_RESULT_CHARS.
    3. Non-tool messages are untouched.
    4. If content is already shorter than the limit, it's left alone.
    """
    total = len(messages)

    for i, msg in enumerate(messages):
        if msg.get("role") != "tool":
            continue

        content = msg.get("content", "")
        if not content or not isinstance(content, str):
            continue

        # Determine the trim limit based on recency
        distance_from_end = total - i
        if distance_from_end <= RECENT_TURNS:
            max_chars = MAX_TOOL_RESULT_CHARS
        else:
            max_chars = MAX_OLD_TOOL_RESULT_CHARS

        if len(content) > max_chars:
            msg["content"] = (
                content[:max_chars]
                + f"\n\n[...truncated to {max_chars} chars, original: {len(content)} chars]"
            )

    return messages


def trim_single_result(content: str | None, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """Trim a single tool result string. Used before insertion.

    Returns the original string if it's within the limit.
    Returns empty string for None input.
    """
    if content is None:
        return ""
    if not content or len(content) <= max_chars:
        return content
    return (
        content[:max_chars]
        + f"\n\n[...truncated to {max_chars} chars, original: {len(content)} chars]"
    )
