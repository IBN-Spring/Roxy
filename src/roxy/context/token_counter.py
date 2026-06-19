"""Token counting — heuristic estimator for context window management."""

from __future__ import annotations

import re
from typing import Any


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total token count for a list of messages.

    Uses a conservative heuristic that overestimates slightly, so compaction
    triggers before the real limit is reached.

    - English text: ~1.3 tokens per word
    - CJK text: ~0.5 tokens per character (conservative)
    - Overhead per message: 4 tokens (role markers)

    This is deliberately simple — no external dependency on tiktoken.
    Accurate enough for threshold detection; the real limit is enforced
    by the LLM provider's API.
    """
    total = 0
    for msg in messages:
        total += 4  # message overhead
        content = msg.get("content", "")
        if content is None:
            content = ""

        if isinstance(content, str):
            total += _estimate_text_tokens(content)

        # Count tool_calls text
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                args = func.get("arguments", "")
                name = func.get("name", "")
                total += _estimate_text_tokens(str(args)) + _estimate_text_tokens(name) + 10

    return total


def _estimate_text_tokens(text: str) -> int:
    """Estimate tokens in a single text string."""
    if not text:
        return 0

    # Count CJK characters (higher token density)
    cjk_chars = len(re.findall(r"[一-鿿㐀-䶿豈-﫿]", text))

    # Count words (latin/cyrillic/arabic etc.)
    words = len(re.findall(r"[a-zA-Z0-9Ѐ-ӿ؀-ۿ]+", text))

    # CJK: ~0.5 tokens per char, words: ~1.3 tokens per word
    cjk_tokens = int(cjk_chars * 0.5)
    word_tokens = int(words * 1.3)

    # Remaining chars (punctuation, whitespace, etc.): minimal token cost
    remaining = max(0, len(text) - cjk_chars - words)
    other_tokens = int(remaining * 0.1)

    return cjk_tokens + word_tokens + other_tokens
