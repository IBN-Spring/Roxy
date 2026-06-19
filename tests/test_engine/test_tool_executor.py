"""Tests for ToolExecutor — approval gate, permission enforcement, error isolation."""

from pathlib import Path

import pytest

from roxy.tools.base import RiskLevel, ToolContext, ToolResult, BaseTool
from roxy.tools.permissions import PermissionManager
from roxy.tools.registry import ToolRegistry
from roxy.engine.tool_executor import ToolExecutor


# ── test tools ──────────────────────────────────────────────────

class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes input"
    risk_level = RiskLevel.safe
    workspace_bounded = False
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, params, ctx):
        return ToolResult.ok(f"echo: {params['text']}")


class _CautionTool(BaseTool):
    name = "caution_op"
    description = "A caution-level operation"
    risk_level = RiskLevel.caution
    workspace_bounded = False
    parameters = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }

    async def execute(self, params, ctx):
        return ToolResult.ok(f"caution: {params['x']}")


class _BoundedReadTool(BaseTool):
    name = "bounded_read"
    description = "Reads workspace files"
    risk_level = RiskLevel.safe
    workspace_bounded = True
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    async def execute(self, params, ctx):
        return ToolResult.ok(f"read: {params['path']}")


# ── helper ──────────────────────────────────────────────────────

def _make_tool_call(name: str, args: dict, call_id: str = "call_1") -> dict:
    import json
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": json.dumps(args),
        },
    }


# ── tests ───────────────────────────────────────────────────────

class TestToolExecutorApprovalGate:
    """requires_approval=True must BLOCK execution, not skip it."""

    @pytest.mark.asyncio
    async def test_caution_tool_blocked_when_requires_approval(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_CautionTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        ctx = ToolContext(workspace_root=tmp_path)

        executor = ToolExecutor(registry, pm, ctx)
        batch = await executor.execute_batch([_make_tool_call("caution_op", {"x": "test"})])

        assert batch.denied_count == 1
        tcr = batch.results[0]
        assert not tcr.approved
        assert tcr.denied_reason == "approval_required"
        assert "approval" in tcr.result.content.lower()

    @pytest.mark.asyncio
    async def test_safe_tool_passes_without_approval(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_EchoTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        ctx = ToolContext(workspace_root=tmp_path)

        executor = ToolExecutor(registry, pm, ctx)
        batch = await executor.execute_batch([_make_tool_call("echo", {"text": "hi"})])

        assert batch.denied_count == 0
        assert batch.results[0].approved
        assert batch.results[0].result.success

    @pytest.mark.asyncio
    async def test_approval_mode_none_allows_caution(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_CautionTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="none")
        ctx = ToolContext(workspace_root=tmp_path)

        executor = ToolExecutor(registry, pm, ctx)
        batch = await executor.execute_batch([_make_tool_call("caution_op", {"x": "ok"})])

        assert batch.denied_count == 0
        assert batch.results[0].approved
        assert batch.results[0].result.success


class TestToolExecutorWorkspaceGate:
    """workspace_bounded tools outside workspace = denied at executor level."""

    @pytest.mark.asyncio
    async def test_bounded_tool_denied_outside_workspace(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_BoundedReadTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        ctx = ToolContext(workspace_root=tmp_path)

        batch = await ToolExecutor(registry, pm, ctx).execute_batch(
            [_make_tool_call("bounded_read", {"path": "/etc/passwd"})]
        )

        assert batch.denied_count == 1
        assert not batch.results[0].approved
        # Denial can be from either blocked-path or workspace-bounded check —
        # both are correct; the important thing is it was denied.
        denied = batch.results[0].denied_reason.lower()
        assert "blocked" in denied or "workspace-bounded" in denied or "denied" in denied

    @pytest.mark.asyncio
    async def test_bounded_tool_denied_non_blocked_outside_path(self, tmp_path: Path):
        """A path outside workspace but NOT in blocklist still gets denied."""
        registry = ToolRegistry()
        registry.register(_BoundedReadTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        ctx = ToolContext(workspace_root=tmp_path)

        batch = await ToolExecutor(registry, pm, ctx).execute_batch(
            [_make_tool_call("bounded_read", {"path": "/tmp/not_blocked.txt"})]
        )

        assert batch.denied_count == 1
        assert not batch.results[0].approved
        assert "workspace-bounded" in batch.results[0].denied_reason.lower()

    @pytest.mark.asyncio
    async def test_bounded_tool_allowed_inside_workspace(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_BoundedReadTool())

        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        ctx = ToolContext(workspace_root=tmp_path)
        (tmp_path / "f.txt").write_text("hi")

        batch = await ToolExecutor(registry, pm, ctx).execute_batch(
            [_make_tool_call("bounded_read", {"path": "f.txt"})]
        )

        assert batch.denied_count == 0
        assert batch.results[0].approved


class TestToolExecutorErrorIsolation:
    """One misbehaving tool shouldn't crash the batch."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, tmp_path: Path):
        registry = ToolRegistry()
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)

        batch = await ToolExecutor(registry, pm, ctx).execute_batch(
            [_make_tool_call("nonexistent", {})]
        )

        assert batch.error_count == 1
        assert not batch.results[0].result.success

    @pytest.mark.asyncio
    async def test_mixed_batch_isolates_failures(self, tmp_path: Path):
        registry = ToolRegistry()
        registry.register(_EchoTool())
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)

        batch = await ToolExecutor(registry, pm, ctx).execute_batch([
            _make_tool_call("echo", {"text": "ok"}, call_id="c1"),
            _make_tool_call("nonexistent", {}, call_id="c2"),
        ])

        assert batch.total == 2
        assert batch.results[0].result.success  # echo worked
        assert not batch.results[1].result.success  # unknown failed
        assert batch.error_count == 1
