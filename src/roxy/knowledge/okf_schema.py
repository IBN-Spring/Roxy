"""OKF v0.1 JSON Schema — the canonical schema for the Open Knowledge Format.

This schema defines the portable interchange format for Roxy's knowledge base.
Every entry is a single JSON line (JSONL). SQLite is the runtime store; JSONL
is the export/import and migration format.
"""

from __future__ import annotations

# Current OKF version — stamped on every entry
OKF_VERSION = "0.1"

# Allowed values for type field
OKF_TYPES = ("source", "item", "insight", "topic")

# Allowed collected_via values
OKF_COLLECTED_VIA = ("rss", "web", "search", "wechat", "manual", "agent", "import")

# Allowed source.type values
OKF_SOURCE_TYPES = ("rss_feed", "web_page", "search_result", "wechat_mp", "import")

# Allowed follow_up status values
OKF_FOLLOWUP_STATUS = ("open", "investigating", "answered")
OKF_FOLLOWUP_PRIORITY = ("low", "medium", "high")

# ── JSON Schema (draft-07 compatible) ────────────────────────────

OKF_JSON_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema#",
    "$id": "https://github.com/IBN-Spring/Roxy-Agent/okf-v0.1.json",
    "title": "Roxy Open Knowledge Format v0.1",
    "description": "Canonical interchange format for Roxy knowledge base entries.",
    "type": "object",
    "required": ["okf_version", "id", "type", "title", "canonical_url"],
    "properties": {
        "okf_version": {
            "type": "string",
            "description": "OKF schema version. Currently '0.1'.",
            "enum": ["0.1"],
        },
        "id": {
            "type": "string",
            "description": "Stable unique identifier (UUID hex).",
            "minLength": 8,
        },
        "type": {
            "type": "string",
            "description": "Entry type: source, item, insight, or topic.",
            "enum": list(OKF_TYPES),
        },
        "canonical_url": {
            "type": "string",
            "description": "Primary URL for this entry.",
        },
        "title": {
            "type": "string",
            "description": "Human-readable title.",
        },
        "content_md": {
            "type": "string",
            "description": "Full content as Markdown.",
        },
        "content_plain": {
            "type": "string",
            "description": "Plain text excerpt.",
        },
        "summary": {
            "type": "string",
            "description": "AI-generated 1-3 sentence summary.",
        },
        "authors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "published_at": {
            "type": "string",
            "description": "ISO 8601 publication date.",
        },
        "collected_at": {
            "type": "string",
            "description": "ISO 8601 collection timestamp.",
        },
        "collected_via": {
            "type": "string",
            "enum": list(OKF_COLLECTED_VIA),
        },
        "language": {
            "type": "string",
            "description": "BCP 47 language tag.",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "topics": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": list(OKF_SOURCE_TYPES)},
                "feed_url": {"type": "string"},
                "channel_name": {"type": "string"},
            },
        },
        "relations": {
            "type": "object",
            "properties": {
                "parent_id": {"type": ["string", "null"]},
                "related_ids": {"type": "array", "items": {"type": "string"}},
                "follow_up_of": {"type": ["string", "null"]},
            },
        },
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "generated_by": {"type": "string"},
                    "generated_at": {"type": "string"},
                },
            },
        },
        "follow_ups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "status": {"type": "string", "enum": list(OKF_FOLLOWUP_STATUS)},
                    "priority": {"type": "string", "enum": list(OKF_FOLLOWUP_PRIORITY)},
                },
            },
        },
    },
}
