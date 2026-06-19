"""Context & memory management — compaction, token counting."""

from roxy.context.manager import ContextManager
from roxy.context.micro_compact import trim_single_result, trim_tool_results
from roxy.context.auto_compact import AutoCompactor
from roxy.context.token_counter import estimate_tokens

__all__ = [
    "ContextManager",
    "trim_single_result",
    "trim_tool_results",
    "AutoCompactor",
    "estimate_tokens",
]
