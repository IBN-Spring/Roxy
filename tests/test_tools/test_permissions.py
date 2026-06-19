"""Tests for PermissionManager — workspace boundary, risk elevation, approval."""

from pathlib import Path

from roxy.tools.base import RiskLevel, ToolContext, ToolResult, BaseTool
from roxy.tools.permissions import PermissionManager, ApprovalMode


class _SafeReadTool(BaseTool):
    name = "safe_read"
    description = "Reads a file safely"
    risk_level = RiskLevel.safe
    workspace_bounded = True

    async def execute(self, params, ctx):
        return ToolResult.ok("read")


class _NonBoundedReadTool(BaseTool):
    name = "open_read"
    description = "Reads any file, not bounded"
    risk_level = RiskLevel.caution
    workspace_bounded = False

    async def execute(self, params, ctx):
        return ToolResult.ok("read")


class _BlockedTool(BaseTool):
    name = "rm"
    description = "Remove files"
    risk_level = RiskLevel.blocked
    workspace_bounded = False

    async def execute(self, params, ctx):
        return ToolResult.ok("deleted")


class _DangerousTool(BaseTool):
    name = "unsafe_write"
    description = "Writes anywhere"
    risk_level = RiskLevel.dangerous
    workspace_bounded = False

    async def execute(self, params, ctx):
        return ToolResult.ok("written")


# ── workspaced-bounded: outside = DENY ──────────────────────────

class TestWorkspaceBoundary:
    """workspace_bounded tools: outside workspace = DENIED, not elevated."""

    def test_bounded_tool_denies_absolute_outside_path(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)
        result = pm.check_tool(_SafeReadTool(), {"path": "/tmp/somefile"}, ctx)
        assert not result.allowed, f"Expected deny, got: {result}"
        assert "workspace-bounded" in result.reason.lower()

    def test_bounded_tool_denies_relative_escaping_path(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)
        result = pm.check_tool(_SafeReadTool(), {"path": "../../etc/passwd"}, ctx)
        assert not result.allowed

    def test_bounded_tool_allows_inside_workspace(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)
        (tmp_path / "f.txt").write_text("hi")
        result = pm.check_tool(_SafeReadTool(), {"path": "f.txt"}, ctx)
        assert result.allowed
        assert result.risk_level == RiskLevel.safe

    def test_non_bounded_tool_allows_outside_read(self, tmp_path: Path):
        """Non-bounded tools (like web_fetch) can still read outside workspace."""
        pm = PermissionManager(workspace_root=tmp_path)
        ctx = ToolContext(workspace_root=tmp_path)
        result = pm.check_tool(_NonBoundedReadTool(), {"path": "/tmp/somefile"}, ctx)
        assert result.allowed
        # Non-bounded tool, risk_level stays at caution (tool's declared level)
        assert result.risk_level == RiskLevel.caution


# ── path resolution ─────────────────────────────────────────────

class TestPathResolution:
    """Relative paths are resolved against workspace_root, not cwd."""

    def test_relative_path_resolves_to_workspace(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        (tmp_path / "data.txt").write_text("hello")
        result = pm.check_file_access(Path("data.txt"), "r", workspace_root=tmp_path)
        assert result.allowed
        assert result.risk_level == RiskLevel.safe

    def test_relative_path_outside_workspace_is_caution(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path / "subdir")
        result = pm.check_file_access(Path("../outside.txt"), "r", workspace_root=tmp_path / "subdir")
        # Resolves to tmp_path/outside.txt which is outside tmp_path/subdir
        assert result.allowed  # read-only, caution
        assert result.risk_level == RiskLevel.caution

    def test_absolute_path_stays_absolute(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        inside = tmp_path / "inside.txt"
        inside.write_text("hi")
        result = pm.check_file_access(Path(str(inside)), "r", workspace_root=tmp_path)
        assert result.allowed
        assert result.risk_level == RiskLevel.safe


# ── blocked / approval ──────────────────────────────────────────

class TestBlockedAndApproval:
    def test_blocked_tool_always_denied(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        result = pm.check_tool(_BlockedTool(), {})
        assert not result.allowed

    def test_blocked_system_path(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        result = pm.check_file_access(Path("/etc/passwd"), "r", workspace_root=tmp_path)
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_approval_mode_always(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="always")
        (tmp_path / "f.txt").write_text("hi")
        ctx = ToolContext(workspace_root=tmp_path)
        result = pm.check_tool(_SafeReadTool(), {"path": str(tmp_path / "f.txt")}, ctx)
        assert result.allowed
        assert result.requires_approval

    def test_approval_mode_dangerous_only_safe_tool_passes(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="dangerous_only")
        (tmp_path / "f.txt").write_text("hi")
        ctx = ToolContext(workspace_root=tmp_path)
        result = pm.check_tool(_SafeReadTool(), {"path": str(tmp_path / "f.txt")}, ctx)
        assert result.allowed
        assert not result.requires_approval

    def test_approval_mode_none(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path, approval_mode="none")
        result = pm.check_tool(_DangerousTool(), {})
        assert result.allowed
        assert not result.requires_approval

    def test_dangerous_tool_needs_approval_in_default_mode(self, tmp_path: Path):
        pm = PermissionManager(workspace_root=tmp_path)
        result = pm.check_tool(_DangerousTool(), {})
        assert result.allowed
        assert result.requires_approval
