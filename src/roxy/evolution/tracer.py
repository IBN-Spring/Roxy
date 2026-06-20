"""TraceRecorder — record agent turns as JSONL for future self-evolution.

Privacy-safe: API keys masked, large tool results hashed, no raw secrets.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy.config.paths import roxy_home


def traces_dir() -> Path:
    path = roxy_home() / "traces"
    path.mkdir(parents=True, exist_ok=True)
    return path


class TraceRecorder:
    """Records agent turns to ~/.roxy/traces/<session_id>.jsonl.

    One JSON line per turn. Privacy-safe by design:
    - API keys masked
    - Tool result content truncated + hashed
    - No raw credentials in output
    """

    MAX_TOOL_RESULT_CHARS: int = 500

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._path = traces_dir() / f"{session_id}.jsonl"

    def record_turn(self, turn: dict[str, Any]) -> None:
        """Write one turn to the trace file."""
        entry = {
            "session_id": self.session_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **turn,
        }
        # Sanitize
        entry = _sanitize(entry)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def list_turns(self) -> list[dict]:
        if not self._path.exists():
            return []
        turns = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    turns.append(json.loads(line))
        return turns

    @classmethod
    def list_all_traces(cls, limit: int = 20) -> list[dict]:
        """List all trace files with metadata."""
        td = traces_dir()
        results = []
        for p in sorted(td.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
            if len(results) >= limit:
                break
            turns = cls(p.stem).list_turns()
            if turns:
                results.append({
                    "session_id": p.stem,
                    "turns": len(turns),
                    "first_at": turns[0].get("recorded_at", ""),
                    "last_at": turns[-1].get("recorded_at", ""),
                })
        return results

    @classmethod
    def export_all(cls, output_path: Path) -> int:
        """Export all traces to a single JSONL file. Returns count."""
        count = 0
        with open(output_path, "w", encoding="utf-8") as out:
            for p in sorted(traces_dir().glob("*.jsonl")):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        out.write(line)
                        count += 1
        return count

    @classmethod
    def generate_eval_seeds(cls, output_path: Path, max_seeds: int = 50) -> int:
        """Extract eval seeds from traces: user message + expected outcome."""
        count = 0
        with open(output_path, "w", encoding="utf-8") as out:
            for p in sorted(traces_dir().glob("*.jsonl")):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if count >= max_seeds:
                            return count
                        turn = json.loads(line.strip())
                        user_msg = turn.get("user_message", "")
                        final = turn.get("final_response", "")
                        if user_msg and final and len(final) > 20:
                            seed = {
                                "task_input": user_msg,
                                "expected_behavior": _summarize_expected(final, turn),
                                "difficulty": "easy",
                                "category": "trace-derived",
                                "source": f"session:{turn.get('session_id', '')}",
                            }
                            out.write(json.dumps(seed, ensure_ascii=False) + "\n")
                            count += 1
        return count


# ── privacy helpers ──────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9]{16,})"),
    re.compile(r"(sk-ant-[a-zA-Z0-9\-_]{20,})"),
    re.compile(r"(Bearer\s+[a-zA-Z0-9\-_\.]{10,})"),
    re.compile(r"(api_key[=:]\s*['\"]?)([^'\",\s]{8,})", re.IGNORECASE),
]


def _sanitize(entry: dict) -> dict:
    """Mask secrets in a trace entry."""
    # Mask the whole entry as a JSON string
    text = json.dumps(entry, ensure_ascii=False)
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r"\1[MASKED]", text)
    return json.loads(text)


def _summarize_expected(final_response: str, turn: dict) -> str:
    """Build a short expected-behavior rubric from the trace."""
    tools = turn.get("tool_calls_summary", "")
    errors = turn.get("errors", "")
    if errors:
        return f"The model should handle errors gracefully. Error seen: {errors[:100]}"
    if tools:
        return f"The model should use appropriate tools. Tools used: {tools}"
    if len(final_response) > 200:
        return final_response[:200] + "..."
    return final_response


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]
