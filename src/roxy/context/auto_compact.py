"""AutoCompact — LLM-driven conversation summarization.

When the estimated context token count exceeds a threshold, the oldest
messages are summarised by an LLM call. The summary replaces the
summarised messages, keeping the system prompt + summary + last N turns.

Includes a circuit breaker to prevent runaway API costs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────

# Trigger auto-compact when estimated tokens exceed this
AUTOCOMPACT_TOKEN_THRESHOLD: int = 40_000

# Keep at least this many recent messages after compaction
KEEP_RECENT_MESSAGES: int = 6  # ~3 user+assistant pairs

# Circuit breaker
MAX_CONSECUTIVE_FAILURES: int = 3

# ── Summary prompt ───────────────────────────────────────────────

COMPACT_SYSTEM_PROMPT = """\
You are a context summariser. Your task is to produce a concise summary of a
conversation between a user and an AI research assistant named Roxy.

Output format (strictly two blocks):

<analysis>
Your scratchpad thoughts about what to include. This will be discarded.
</analysis>

<summary>
The structured summary to inject back into the conversation context.
</summary>

The summary MUST cover these sections:

1. **Primary intent & goals**: What the user is trying to accomplish.
2. **Technical concepts & domain knowledge**: Key terms, frameworks, or domain
   knowledge established during the conversation.
3. **Key files & code examined**: Paths only, not full content.
4. **Errors encountered & fixes applied**: What went wrong and how it was fixed.
5. **Problem solving decisions & rationale**: Why certain approaches were chosen.
6. **User constraints still affecting the task**: Short factual summary of
   unfulfilled requests, stated preferences, and active constraints.
   Short phrases preserved verbatim; long messages summarised.
   **Sensitive content (keys, tokens, passwords, PII) MUST NOT appear.**
7. **Pending tasks & open questions**: What still needs to be done.
8. **Current work in progress**: What was being done when compaction triggered.
9. **Recommended next steps**: What the assistant should do next.

Be concise. The summary should be 500-1500 words. Include file paths but NOT
full file contents. Do NOT include API keys, tokens, or passwords.
"""


class AutoCompactor:
    """Compresses old conversation messages via LLM summarisation.

    Usage:
        compactor = AutoCompactor(provider)
        new_messages = await compactor.compact(messages)
    """

    def __init__(self, provider: Any):
        """provider must have a .complete(prompt, system=..., model=...) async method."""
        self.provider = provider
        self._consecutive_failures: int = 0

    @property
    def circuit_broken(self) -> bool:
        """True if the circuit breaker has tripped."""
        return self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    def reset_circuit(self) -> None:
        """Reset the circuit breaker (e.g. on fresh session)."""
        self._consecutive_failures = 0

    async def compact(
        self,
        messages: list[dict[str, Any]],
        keep_recent: int = KEEP_RECENT_MESSAGES,
    ) -> list[dict[str, Any]] | None:
        """Compress old messages into a summary.

        Args:
            messages: Full message list.
            keep_recent: Number of most recent messages to keep uncompressed.

        Returns:
            A new, shorter message list, or None if compaction failed.
        """
        if self.circuit_broken:
            logger.warning("AutoCompact: circuit breaker tripped — skipping compaction")
            return None

        if len(messages) <= keep_recent + 4:
            # Too few messages to compact
            return messages

        # Split: old messages to summarise, recent messages to keep
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Build the prompt with the old messages
        transcript = _format_messages(old_messages)
        user_prompt = (
            "Summarise the following conversation segment.\n\n"
            f"{transcript}\n\n"
            "Output ONLY the <analysis> and <summary> blocks. No other text."
        )

        try:
            response = await self.provider.complete(
                prompt=user_prompt,
                system=COMPACT_SYSTEM_PROMPT,
            )

            # Parse <analysis> and <summary> blocks
            summary = _extract_block(response, "summary")
            if not summary:
                logger.warning("AutoCompact: could not extract <summary> from response")
                self._consecutive_failures += 1
                return None

            # Build compacted message list:
            # [system prompt kept by caller] + [summary as system message] + [recent]
            compacted: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "[Context from earlier in the conversation]\n\n" + summary
                    ),
                }
            ]
            compacted.extend(recent_messages)

            self._consecutive_failures = 0
            logger.info(f"AutoCompact: compressed {len(old_messages)} messages → summary ({len(summary)} chars)")
            return compacted

        except Exception as exc:
            logger.error(f"AutoCompact failed: {exc}")
            self._consecutive_failures += 1
            return None


# ── helpers ──────────────────────────────────────────────────────

def _format_messages(messages: list[dict[str, Any]]) -> str:
    """Format messages into a readable transcript for the compaction prompt."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "system":
            lines.append(f"[System]: {content[:300]}")
        elif role == "user":
            lines.append(f"[User]: {content}")
        elif role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            tc_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            prefix = f"[Assistant]: "
            if content:
                lines.append(prefix + content[:500])
            if tc_names:
                lines.append(f"  (called tools: {', '.join(tc_names)})")
        elif role == "tool":
            lines.append(f"[Tool result]: {content[:300]}")

    return "\n".join(lines)


def _extract_block(text: str, tag: str) -> str:
    """Extract content between <tag> and </tag>. Returns empty string if not found."""
    import re
    pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""
