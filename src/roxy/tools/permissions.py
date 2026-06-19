"""PermissionManager — gates tool execution behind workspace boundaries and risk policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from roxy.tools.base import BaseTool, RiskLevel


class ApprovalMode(Enum):
    """When to require user approval before executing a tool.

    always:         every tool (even safe) prompts for approval
    dangerous_only: only caution+ tools need approval (recommended default)
    none:           never prompt (⚠ only for trusted/automated environments)
    """

    always = "always"
    dangerous_only = "dangerous_only"
    none = "none"


# ── PermissionResult ────────────────────────────────────────────

@dataclass
class PermissionResult:
    """The outcome of a permission check.

    allowed: True if the tool can execute.
    reason: Human-readable explanation.
    risk_level: The tool's risk level (or elevated level from path check).
    requires_approval: True if this needs explicit user confirmation.
    """

    allowed: bool
    reason: str
    risk_level: RiskLevel
    requires_approval: bool = False

    @classmethod
    def grant(cls, risk: RiskLevel, reason: str = "") -> "PermissionResult":
        return cls(allowed=True, reason=reason, risk_level=risk)

    @classmethod
    def deny(cls, risk: RiskLevel, reason: str) -> "PermissionResult":
        return cls(allowed=False, reason=reason, risk_level=risk)


# ── PermissionManager ───────────────────────────────────────────

class PermissionManager:
    """Gates tool execution behind workspace boundaries, risk policy, and blocklists.

    Usage:
        pm = PermissionManager(workspace_root=Path.cwd(), approval_mode="dangerous_only")
        result = pm.check_tool(tool, {"path": "/etc/passwd"}, ctx)
        if not result.allowed:
            raise PermissionError(result.reason)
        if result.requires_approval:
            # In the future: approved = await pm.request_approval(tool, params)
            # For now: ToolExecutor returns denied — approval UI hasn't been built yet.
            pass
    """

    # Patterns always blocked in file paths (checked against resolved absolute path)
    BLOCKED_PATH_PATTERNS: list[str] = [
        # Unix system-critical
        "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        # Windows system
        "C:\\Windows\\System32", "C:\\Windows\\System",
        # Kernel / device / proc pseudo-filesystems
        "/dev/", "/proc/", "/sys/",
    ]

    def __init__(
        self,
        workspace_root: Path | None = None,
        approval_mode: str = "dangerous_only",
    ):
        self.workspace_root = workspace_root or Path.cwd().resolve()
        self.approval_mode = ApprovalMode(approval_mode)

    # ── public API ───────────────────────────────────────────────

    def check_tool(
        self,
        tool: BaseTool,
        params: dict[str, Any],
        ctx: Any = None,
    ) -> PermissionResult:
        """Check whether a tool can execute with the given parameters.

        Returns a PermissionResult — callers MUST respect:
        - allowed=False → execution blocked
        - requires_approval=True → must prompt user before executing
        """
        # 1. Blocked-level tools are never allowed
        if tool.risk_level == RiskLevel.blocked:
            return PermissionResult.deny(
                RiskLevel.blocked,
                f"Tool '{tool.name}' is permanently blocked by policy.",
            )

        # 2. Workspace containment check for bounded tools
        if tool.workspace_bounded:
            path_key = params.get("path") or params.get("file_path") or params.get("file")
            if path_key:
                ws_root = _resolve_workspace(ctx, self.workspace_root)
                path_result = self.check_file_access(Path(path_key), "r", workspace_root=ws_root)

                if not path_result.allowed:
                    return path_result

                # workspace_bounded tools: outside workspace = DENY (not elevated to caution)
                if path_result.risk_level >= RiskLevel.caution:
                    return PermissionResult.deny(
                        RiskLevel.blocked,
                        f"Access to '{path_key}' is denied: "
                        f"workspace-bounded tools can only access files within the workspace.",
                    )

        # 3. Determine if approval is required based on the tool's declared risk
        requires_approval = self._needs_approval(tool.risk_level)

        return PermissionResult(
            allowed=True,
            reason="ok",
            risk_level=tool.risk_level,
            requires_approval=requires_approval,
        )

    def check_file_access(
        self,
        path: Path,
        mode: str = "r",
        workspace_root: Path | None = None,
    ) -> PermissionResult:
        """Check whether a file path is safe to access.

        Args:
            path: The path to check (absolute or relative).
            mode: Access mode — "r", "w", "a", "x". Write modes are more restrictive.
            workspace_root: Base for resolving relative paths.
                            Defaults to self.workspace_root.

        Rules:
        1. Relative paths are resolved against workspace_root (NOT cwd).
        2. Resolved path must not match any BLOCKED_PATH_PATTERNS.
        3. Write access outside workspace is always denied.
        4. Read access outside workspace returns caution-level (caller decides).
        """
        base = workspace_root or self.workspace_root

        # Resolve relative paths against workspace_root
        if not path.is_absolute():
            path = base / path

        try:
            resolved = path.resolve()
        except Exception:
            return PermissionResult.deny(
                RiskLevel.blocked,
                f"Cannot resolve path: {path}",
            )

        # Check blocked patterns
        path_str = str(resolved).replace("\\", "/")
        for pattern in self.BLOCKED_PATH_PATTERNS:
            if pattern.replace("\\", "/") in path_str:
                return PermissionResult.deny(
                    RiskLevel.blocked,
                    f"Access to '{path}' is blocked (matches protected path pattern).",
                )

        # Check workspace containment
        try:
            resolved.relative_to(base)
        except ValueError:
            # Outside workspace
            if "w" in mode or "a" in mode or "x" in mode:
                return PermissionResult.deny(
                    RiskLevel.dangerous,
                    f"Write access to '{path}' is denied (outside workspace).",
                )
            # Read-only outside workspace → caution (caller decides whether to deny)
            return PermissionResult(
                allowed=True,
                reason=f"Read-only access outside workspace: {path}",
                risk_level=RiskLevel.caution,
                requires_approval=self._needs_approval(RiskLevel.caution),
            )

        # Inside workspace → safe
        return PermissionResult.grant(RiskLevel.safe)

    # ── helpers ──────────────────────────────────────────────────

    def _needs_approval(self, risk: RiskLevel) -> bool:
        """Return True if this risk level requires user approval under current mode."""
        if self.approval_mode == ApprovalMode.none:
            return False
        if self.approval_mode == ApprovalMode.always:
            return True
        # dangerous_only: approve if risk >= caution
        return risk != RiskLevel.safe


def _resolve_workspace(ctx: Any, fallback: Path) -> Path:
    """Extract workspace_root from ctx, falling back to given default."""
    if ctx is not None:
        ws = getattr(ctx, "workspace_root", None)
        if ws is not None:
            return ws
    return fallback
