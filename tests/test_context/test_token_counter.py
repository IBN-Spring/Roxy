"""Tests for token counter — heuristic estimation."""

from roxy.context.token_counter import estimate_tokens, _estimate_text_tokens


class TestTokenCounter:
    def test_empty_returns_zero(self):
        assert estimate_tokens([]) == 0
        assert _estimate_text_tokens("") == 0

    def test_english_text(self):
        tokens = _estimate_text_tokens("hello world this is a test")
        assert tokens > 5  # 6 words × 1.3 ≈ 8 tokens
        assert tokens < 20

    def test_cjk_text(self):
        tokens = _estimate_text_tokens("这是一段中文测试文本")
        assert tokens >= 4  # 10 chars × 0.5 = 5 tokens

    def test_message_overhead(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        tokens = estimate_tokens(msgs)
        # 2 messages × 4 overhead + content tokens
        assert tokens >= 8  # at minimum the overhead

    def test_long_content_estimates_higher(self):
        short = _estimate_text_tokens("short")
        long = _estimate_text_tokens("this is a much longer piece of text that should estimate more tokens")
        assert long > short

    def test_tool_calls_estimated(self):
        msgs = [{
            "role": "assistant",
            "content": "let me check",
            "tool_calls": [{
                "id": "c1",
                "function": {"name": "file_read", "arguments": '{"path": "/x"}'},
            }],
        }]
        tokens = estimate_tokens(msgs)
        assert tokens > 10  # overhead + content + tool_calls
