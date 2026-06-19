"""Tests for MicroCompact — tool result trimming."""

from roxy.context.micro_compact import trim_single_result, trim_tool_results


class TestSingleResultTrim:
    def test_short_content_untouched(self):
        result = trim_single_result("hello", max_chars=100)
        assert result == "hello"

    def test_long_content_trimmed(self):
        long_text = "x" * 5000
        result = trim_single_result(long_text, max_chars=1000)
        assert len(result) < len(long_text)
        assert "truncated" in result.lower()
        assert "1000" in result
        assert "5000" in result

    def test_none_returns_empty(self):
        assert trim_single_result(None) == ""
        assert trim_single_result("") == ""


class TestTrimToolResults:
    def test_trim_recent_tool_result(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "tool", "tool_call_id": "c1", "content": "x" * 5000},
        ]
        trim_tool_results(msgs)
        # Recent tool result (distance from end = 1 <= 4) → trimmed to 4000
        assert len(msgs[2]["content"]) < 5000
        assert "4000" in msgs[2]["content"]

    def test_trim_old_tool_result(self):
        msgs = [
            {"role": "tool", "tool_call_id": "old", "content": "y" * 5000},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
        trim_tool_results(msgs)
        # Old tool result (distance from end = 5 > 4) → trimmed to 1500
        assert "1500" in msgs[0]["content"]

    def test_non_tool_messages_untouched(self):
        msgs = [
            {"role": "user", "content": "keep me as is"},
            {"role": "assistant", "content": "keep me too"},
        ]
        trim_tool_results(msgs)
        assert msgs[0]["content"] == "keep me as is"
        assert msgs[1]["content"] == "keep me too"

    def test_empty_list_no_error(self):
        trim_tool_results([])
