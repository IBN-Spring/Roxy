"""Proposer — analyze eval failures and generate improvement proposals.

Outputs a markdown document with per-failure analysis and suggested changes.
Does NOT modify any files. Human review required.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProposalGenerator:
    """Analyze eval report failures and generate improvement proposals.

    Output: markdown file with per-case analysis. No auto-apply.

    Usage:
        gen = ProposalGenerator()
        gen.generate("baseline.json", "proposals.md", target="all")
    """

    def generate(self, report_path: Path, output_path: Path, target: str = "all") -> int:
        """Generate proposals from an eval report. Returns count of proposals."""
        if not report_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        results = report.get("results", [])
        failures = report.get("failures", [])

        # Build proposals
        proposals = []
        for result in results:
            if result.get("passed"):
                continue

            proposal = self._analyze_case(result, target)
            if proposal:
                proposals.append(proposal)

        if not proposals and not failures:
            proposals.append({
                "title": "No failures — no proposals needed",
                "summary": "All eval cases passed. The current agent configuration is performing well on this eval set.",
                "sections": [],
            })

        # Write markdown
        self._write_markdown(proposals, report, output_path)
        return len([p for p in proposals if p.get("sections")])

    def _analyze_case(self, result: dict, target: str) -> dict | None:
        """Analyze one failed case and generate a proposal."""
        case_id = result.get("case_id", "unknown")
        tool_score = result.get("tool_use_match", 0)
        kw_score = result.get("keyword_recall", 0)
        no_error = result.get("no_error", True)
        task_input = result.get("task_input", "")
        tools_used = result.get("tools_used", [])
        final_score = result.get("final_score", 0)

        sections = []

        # Tool use failure
        if tool_score < 0.5 and target in ("all", "tool-descriptions"):
            sections.append({
                "title": "Tool not called when expected",
                "detail": f"tool_use_match = {tool_score} (used: {tools_used})",
                "cause": self._diagnose_tool_failure(tools_used, task_input),
                "proposal": {
                    "target": "tool-descriptions",
                    "suggestion": (
                        f"Review the tool descriptions to ensure the model "
                        f"understands when to use the expected tool for inputs "
                        f"like: '{task_input[:80]}'"
                    ),
                },
                "risk": "Low — tool description changes only affect when tools are called",
                "test": f"Re-run case '{case_id}' and confirm tool_use_match = 1.0",
            })

        # Keyword failure
        if kw_score < 0.5 and target in ("all", "system-prompt"):
            sections.append({
                "title": "Response missing expected keywords",
                "detail": f"keyword_recall = {kw_score}",
                "cause": (
                    f"The model's response did not contain expected content "
                    f"for the task: '{task_input[:80]}'. The system prompt may "
                    f"not guide the model to include the expected information."
                ),
                "proposal": {
                    "target": "system-prompt",
                    "suggestion": (
                        f"Add guidance to the system prompt ensuring responses "
                        f"cover: relevant details, source URLs, dates, and "
                        f"actionable next steps."
                    ),
                },
                "risk": "Low — system prompt changes affect response style, not behavior",
                "test": f"Re-run case '{case_id}' and confirm keyword_recall >= 0.5",
            })

        # Error failure
        if not no_error and target in ("all", "system-prompt"):
            sections.append({
                "title": "Agent encountered an error",
                "detail": "no_error = False",
                "cause": (
                    f"The agent failed to produce a valid response for: "
                    f"'{task_input[:80]}'. This may indicate a provider issue, "
                    f"missing API key, or permission block."
                ),
                "proposal": {
                    "target": "error-handling",
                    "suggestion": (
                        f"Ensure the provider is configured and the agent has "
                        f"access to the required tools. Check: roxy doctor"
                    ),
                },
                "risk": "Low — error handling improvement",
                "test": f"Re-run case '{case_id}' and confirm no_error = True",
            })

        if not sections:
            return None

        return {
            "title": f"Case {case_id} (score: {final_score})",
            "summary": f"Task: {task_input[:120]}",
            "sections": sections,
        }

    def _diagnose_tool_failure(self, used: list[str], task_input: str) -> str:
        if not used:
            return (
                f"No tools were called for: '{task_input[:80]}'. "
                f"The model may not recognize this as a tool-appropriate request, "
                f"or the tool descriptions may not clearly match this use case."
            )
        return (
            f"The model used {used} instead of the expected tool for: "
            f"'{task_input[:80]}'. The expected tool's description may need "
            f"clarification to better match this type of request."
        )

    def _write_markdown(self, proposals: list[dict], report: dict, output_path: Path) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# Roxy Improvement Proposals",
            f"**Generated**: {now}",
            f"**Source**: {report.get('model', 'unknown')} (live: {report.get('live', False)})",
            f"**Baseline**: {report.get('total', 0)} cases, avg score {report.get('avg_score', 0)}",
            "",
            "---",
            "",
        ]

        for i, prop in enumerate(proposals, 1):
            lines.append(f"## Proposal {i} — {prop['title']}")
            lines.append("")
            if prop.get("summary"):
                lines.append(f"{prop['summary']}")
                lines.append("")

            for sec in prop.get("sections", []):
                lines.append(f"### {sec['title']}")
                lines.append("")
                lines.append(f"**Detail**: {sec['detail']}")
                lines.append("")
                lines.append(f"**Suspected cause**: {sec['cause']}")
                lines.append("")

                p = sec.get("proposal", {})
                lines.append(f"**Suggested change** (target: `{p.get('target', 'unknown')}`):")
                lines.append("")
                lines.append(f"> {p.get('suggestion', '')}")
                lines.append("")
                lines.append(f"**Risk**: {sec.get('risk', 'Unknown')}")
                lines.append("")
                lines.append(f"**Test**: {sec.get('test', '')}")
                lines.append("")
                lines.append("---")
                lines.append("")

        lines.append("## Next Steps")
        lines.append("")
        lines.append("1. Review each proposal above")
        lines.append("2. Apply the suggested changes manually to the relevant file")
        lines.append("3. Re-run: `roxy eval run --live --out baseline-v2.json`")
        lines.append("4. Compare: `roxy eval report baseline-v2.json`")
        lines.append("5. If scores improved, commit the changes")
        lines.append("")
        lines.append(f"*Generated by Roxy Proposer — {now}*")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
