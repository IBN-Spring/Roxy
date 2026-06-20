"""OKF Validator — validate entries against the OKF JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roxy.knowledge.okf_schema import OKF_JSON_SCHEMA, OKF_VERSION


class OKFValidationError(Exception):
    """Raised when an entry fails OKF validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def validate_entry(entry: dict[str, Any]) -> list[str]:
    """Validate a single OKF entry dict. Returns list of error messages (empty = valid).

    Uses jsonschema if available, otherwise falls back to structural validation.
    """
    # Try jsonschema first
    try:
        import jsonschema
        jsonschema.validate(entry, OKF_JSON_SCHEMA)
        return []
    except ImportError:
        pass
    except jsonschema.ValidationError as exc:
        return [str(exc)]

    # Fallback: structural validation
    return _structural_validate(entry)


def validate_file(path: Path) -> dict[str, Any]:
    """Validate a JSONL file. Returns {valid, total, errors: [{line, errors}]}."""
    if not path.exists():
        return {"valid": False, "total": 0, "errors": [{"line": 0, "errors": ["File not found"]}]}

    results = {"valid": True, "total": 0, "errors": []}
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            results["total"] += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                results["valid"] = False
                results["errors"].append({"line": line_num, "errors": [f"Invalid JSON: {exc}"]})
                continue

            errs = validate_entry(entry)
            if errs:
                results["valid"] = False
                results["errors"].append({"line": line_num, "errors": errs})

    return results


def _structural_validate(entry: dict[str, Any]) -> list[str]:
    """Basic structural validation without jsonschema dependency."""
    errors: list[str] = []

    # Required fields
    for field in ("okf_version", "id", "type", "title", "canonical_url"):
        if field not in entry:
            errors.append(f"Missing required field: '{field}'")

    # Version check
    if entry.get("okf_version") != OKF_VERSION:
        errors.append(
            f"Unsupported okf_version: '{entry.get('okf_version')}'. "
            f"Expected '{OKF_VERSION}'."
        )

    # Type check
    okf_type = entry.get("type", "")
    valid_types = ("source", "item", "insight", "topic")
    if okf_type and okf_type not in valid_types:
        errors.append(f"Invalid type '{okf_type}'. Must be one of: {valid_types}")

    # collected_via check
    via = entry.get("collected_via", "")
    valid_via = ("rss", "web", "search", "wechat", "manual", "agent", "import")
    if via and via not in valid_via:
        errors.append(f"Invalid collected_via '{via}'. Must be one of: {valid_via}")

    # URL format check (basic)
    url = entry.get("canonical_url", "")
    if url and not (url.startswith("http://") or url.startswith("https://")):
        errors.append(f"canonical_url must start with http:// or https://: '{url[:80]}'")

    # ID length
    eid = entry.get("id", "")
    if eid and len(str(eid)) < 8:
        errors.append(f"id too short: '{eid}' (min 8 characters)")

    # authors must be list if present
    authors = entry.get("authors")
    if authors is not None and not isinstance(authors, list):
        errors.append("'authors' must be a list")

    # tags must be list if present
    tags = entry.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("'tags' must be a list")

    # source must be dict if present
    source = entry.get("source")
    if source is not None and not isinstance(source, dict):
        errors.append("'source' must be an object")

    return errors
