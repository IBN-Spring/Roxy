"""Tests for AutoCompact — summary parsing, circuit breaker."""

from roxy.context.auto_compact import (
    AutoCompactor,
    _extract_block,
    _format_messages,
    _safe_recent_start,
    MAX_CONSECUTIVE_FAILURES,
)


class TestExtractBlock:
    def test_extracts_summary(self):
        text = "<analysis>junk</analysis>\n<summary>important stuff</summary>"
        assert _extract_block(text, "summary") == "important stuff"

    def test_extracts_analysis(self):
        text = "<analysis>scratchpad text here</analysis>\n<summary>ok</summary>"
        assert _extract_block(text, "analysis") == "scratchpad text here"

    def test_missing_block_returns_empty(self):
        assert _extract_block("no blocks here", "summary") == ""

    def test_multiline_block(self):
        text = """<summary>
        line one
        line two
        </summary>"""
        result = _extract_block(text, "summary")
        assert "line one" in result
        assert "line two" in result


class TestFormatMessages:
    def test_formats_user_assistant(self):
        msgs = [
            {"role": "user", "content": "Hello there"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ]
        result = _format_messages(msgs)
        assert "[User]: Hello there" in result
        assert "[Assistant]: Hi!" in result

    def test_formats_tool_call(self):
        msgs = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "file_read"}}],
        }]
        result = _format_messages(msgs)
        assert "file_read" in result


class TestSafeRecentStart:
    def test_keeps_normal_recent_window(self):
        msgs = [{"role": "user", "content": f"u{i}"} for i in range(10)]
        assert _safe_recent_start(msgs, keep_recent=4) == 6

    def test_moves_boundary_before_orphan_tool_result(self):
        msgs = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old"},
            {"role": "user", "content": "please read"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "file_read"}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
            {"role": "assistant", "content": "done"},
        ]

        assert _safe_recent_start(msgs, keep_recent=2) == 3


class TestAutoCompactor:
    def test_circuit_breaker_initial_state(self):
        comp = AutoCompactor(provider=None)
        assert not comp.circuit_broken

    def test_reset_circuit(self):
        comp = AutoCompactor(provider=None)
        comp._consecutive_failures = 5
        comp.reset_circuit()
        assert not comp.circuit_broken

    def test_too_few_messages_returns_unchanged(self):
        """When messages <= keep_recent + 4, compact returns messages unchanged."""
        comp = AutoCompactor(provider=None)
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ]
        # len(msgs)=2 <= keep_recent(6)+4=10 → too few
        import asyncio
        result = asyncio.run(comp.compact(msgs, keep_recent=6))
        assert result == msgs  # unchanged

    def test_circuit_broken_skips_compaction(self):
        comp = AutoCompactor(provider=None)
        comp._consecutive_failures = MAX_CONSECUTIVE_FAILURES
        msgs = [{"role": "user", "content": "x"}] * 50

        import asyncio
        result = asyncio.run(comp.compact(msgs))
        assert result is None  # skipped due to circuit breaker

    def test_compact_with_mock_provider(self):
        """End-to-end compaction with a mock LLM provider."""
        import asyncio

        class MockProvider:
            async def complete(self, prompt, system=None, model=None):
                return "<analysis>scratch</analysis>\n<summary>Compacted summary of the conversation.</summary>"

        comp = AutoCompactor(provider=MockProvider())
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(30)]  # 30 messages

        result = asyncio.run(comp.compact(msgs, keep_recent=6))
        assert result is not None
        # Should have: 1 summary message + 6 recent messages
        assert len(result) == 7
        assert result[0]["role"] == "system"
        assert "Compacted summary" in result[0]["content"]
