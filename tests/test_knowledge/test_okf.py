"""Tests for OKF schema, validator, import/export roundtrip."""

import json
from pathlib import Path

from roxy.knowledge.okf_schema import OKF_JSON_SCHEMA, OKF_VERSION, OKF_TYPES
from roxy.knowledge.okf_validator import validate_entry, validate_file, _structural_validate
from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.schema import KnowledgeEntry


def _valid_entry(**overrides) -> dict:
    """Build a minimal valid OKF entry."""
    data = {
        "okf_version": "0.1",
        "id": "abc123def4567890",
        "type": "item",
        "title": "Test Entry",
        "canonical_url": "https://example.com/test",
        "content_md": "Some content.",
        "content_plain": "Some content.",
        "summary": "A test entry.",
        "authors": ["Author Name"],
        "published_at": "2025-01-01T00:00:00",
        "collected_at": "2025-01-02T00:00:00",
        "collected_via": "rss",
        "language": "zh-CN",
        "tags": ["test"],
        "topics": [],
        "source": {
            "type": "rss_feed",
            "feed_url": "https://example.com/feed",
            "channel_name": "Test Feed",
        },
        "relations": {"parent_id": None, "related_ids": [], "follow_up_of": None},
        "insights": [],
        "follow_ups": [],
    }
    data.update(overrides)
    return data


class TestOKFSchema:
    def test_schema_has_version(self):
        assert OKF_JSON_SCHEMA["$id"].endswith("okf-v0.1.json")
        assert OKF_VERSION == "0.1"

    def test_schema_has_types(self):
        assert "item" in OKF_TYPES
        assert "source" in OKF_TYPES
        assert "insight" in OKF_TYPES
        assert "topic" in OKF_TYPES

    def test_schema_defines_required_fields(self):
        required = OKF_JSON_SCHEMA["required"]
        assert "okf_version" in required
        assert "id" in required
        assert "type" in required
        assert "title" in required
        assert "canonical_url" in required


class TestStructuralValidator:
    def test_valid_entry_passes(self):
        errs = _structural_validate(_valid_entry())
        assert errs == []

    def test_missing_required(self):
        errs = _structural_validate({"title": "hi"})
        assert any("okf_version" in e for e in errs)
        assert any("id" in e for e in errs)

    def test_wrong_version(self):
        errs = _structural_validate(_valid_entry(okf_version="0.99"))
        assert any("0.99" in e for e in errs)

    def test_invalid_type(self):
        errs = _structural_validate(_valid_entry(type="invalid_type"))
        assert any("type" in e.lower() for e in errs)

    def test_invalid_url(self):
        errs = _structural_validate(_valid_entry(canonical_url="not-a-url"))
        assert any("canonical_url" in e for e in errs)

    def test_invalid_collected_via(self):
        errs = _structural_validate(_valid_entry(collected_via="telegram"))
        assert any("collected_via" in e for e in errs)

    def test_short_id(self):
        errs = _structural_validate(_valid_entry(id="abc"))
        assert any("short" in e for e in errs)

    def test_authors_not_list(self):
        errs = _structural_validate(_valid_entry(authors="not a list"))
        assert any("authors" in e for e in errs)

    def test_source_not_dict(self):
        errs = _structural_validate(_valid_entry(source="not a dict"))
        assert any("source" in e for e in errs)


class TestValidateFile:
    def test_valid_file(self, tmp_path: Path):
        path = tmp_path / "valid.jsonl"
        path.write_text(
            json.dumps(_valid_entry(id="a" * 16)) + "\n" +
            json.dumps(_valid_entry(id="b" * 16, title="Entry 2")) + "\n",
            encoding="utf-8",
        )
        result = validate_file(path)
        assert result["valid"]
        assert result["total"] == 2

    def test_invalid_file(self, tmp_path: Path):
        path = tmp_path / "invalid.jsonl"
        path.write_text(
            json.dumps({"title": "missing fields"}) + "\n",
            encoding="utf-8",
        )
        result = validate_file(path)
        assert not result["valid"]
        assert len(result["errors"]) >= 1

    def test_bad_json(self, tmp_path: Path):
        path = tmp_path / "bad.jsonl"
        path.write_text("not json at all\n", encoding="utf-8")
        result = validate_file(path)
        assert not result["valid"]

    def test_missing_file(self, tmp_path: Path):
        result = validate_file(tmp_path / "nonexistent.jsonl")
        assert not result["valid"]


class TestOKFRoundtrip:
    def test_export_then_import(self, tmp_path: Path):
        """Export → import roundtrip preserves data."""
        db = tmp_path / "test.db"
        store = KnowledgeStore(db_path=db)
        store.init_db()

        # Insert some entries
        store.insert_entry(KnowledgeEntry(
            title="Alpha", canonical_url="https://a.com/1",
            content_plain="First entry.", collected_via="rss",
            source_feed_url="https://feed.com", source_channel="Feed",
        ))
        store.insert_entry(KnowledgeEntry(
            title="Beta", canonical_url="https://a.com/2",
            content_plain="Second entry.", collected_via="manual",
        ))

        # Export
        export_path = tmp_path / "export.jsonl"
        count = store.export_jsonl(export_path)
        assert count == 2

        # Verify exported OKF
        with open(export_path, "r") as f:
            for line in f:
                data = json.loads(line)
                assert data["okf_version"] == "0.1"
                assert data["id"]
                assert data["title"]

        # Validate exported file
        result = validate_file(export_path)
        assert result["valid"], f"Export failed validation: {result['errors']}"

        # Import into fresh DB
        db2 = tmp_path / "test2.db"
        store2 = KnowledgeStore(db_path=db2)
        store2.init_db()
        counts = store2.import_jsonl(export_path)
        assert counts["imported"] == 2
        assert counts["errors"] == 0

        # Verify imported data
        assert store2.get_stats()["entry_count"] == 2

    def test_import_skips_duplicates(self, tmp_path: Path):
        db = tmp_path / "test.db"
        store = KnowledgeStore(db_path=db)
        store.init_db()

        path = tmp_path / "data.jsonl"
        path.write_text(
            json.dumps(_valid_entry(id="c" * 16, title="One",
                                    canonical_url="https://x.com/1")) + "\n" +
            json.dumps(_valid_entry(id="c" * 16, title="One",
                                    canonical_url="https://x.com/1")) + "\n",
            encoding="utf-8",
        )

        counts = store.import_jsonl(path)
        assert counts["imported"] == 1
        assert counts["skipped"] == 1

    def test_import_without_validation(self, tmp_path: Path):
        db = tmp_path / "test.db"
        store = KnowledgeStore(db_path=db)
        store.init_db()

        path = tmp_path / "loose.jsonl"
        # Missing okf_version — would fail validation
        path.write_text(
            json.dumps({"id": "d" * 16, "type": "item", "title": "Loose",
                        "canonical_url": "https://x.com/loose"}) + "\n",
            encoding="utf-8",
        )

        counts = store.import_jsonl(path, validate=False)
        assert counts["imported"] == 1
