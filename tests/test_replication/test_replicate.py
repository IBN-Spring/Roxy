"""Tests for v0.9.1 replication safety hardening."""

import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml


class TestExportValidate:
    def test_export_then_validate(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        assert bundle.exists()
        result = rep.validate_bundle(bundle)
        assert result["valid"], f"Export failed validation: {result['errors']}"

    def test_config_template_has_no_real_keys(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        with zipfile.ZipFile(bundle, "r") as zf:
            config = yaml.safe_load(zf.read("config.template.yaml").decode("utf-8"))
            providers = config.get("models", {}).get("providers", {})
            for name, cfg in providers.items():
                assert cfg.get("api_key") == "", f"{name} api_key should be empty"
                assert "sk-" not in str(cfg), f"{name} config contains real key pattern"

    def test_export_contains_manifest(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        with zipfile.ZipFile(bundle, "r") as zf:
            assert "manifest.json" in zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))
            assert "roxy_version" in manifest
            assert "contents" in manifest

    def test_export_contains_source(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        with zipfile.ZipFile(bundle, "r") as zf:
            assert "roxy-src.zip" in zf.namelist()
            assert "config.template.yaml" in zf.namelist()


class TestValidateSecurity:
    def test_hash_tamper_fails(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        # Tamper: rewrite manifest with wrong hash
        with zipfile.ZipFile(bundle, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
        manifest["contents"]["source"]["sha256"] = "deadbeef" * 4
        # Re-pack (read-modify-write)
        import io
        new_data = io.BytesIO()
        with zipfile.ZipFile(bundle, "r") as zf_in:
            with zipfile.ZipFile(new_data, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for name in zf_in.namelist():
                    if name == "manifest.json":
                        zf_out.writestr(name, json.dumps(manifest))
                    else:
                        zf_out.writestr(name, zf_in.read(name))
        new_data.seek(0)
        bundle.write_bytes(new_data.read())
        result = rep.validate_bundle(bundle)
        assert not result["valid"]
        assert any("Hash mismatch" in e for e in result["errors"])

    def test_undeclared_file_fails(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        # Inject undeclared file
        import io
        new_data = io.BytesIO()
        with zipfile.ZipFile(bundle, "r") as zf_in:
            with zipfile.ZipFile(new_data, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for name in zf_in.namelist():
                    zf_out.writestr(name, zf_in.read(name))
                zf_out.writestr("evil.sh", b"rm -rf /")
        new_data.seek(0)
        bundle.write_bytes(new_data.read())
        result = rep.validate_bundle(bundle)
        assert not result["valid"]
        assert any("Undeclared" in e for e in result["errors"])

    def test_zip_slip_absolute_path_fails(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator, _is_safe_path
        assert not _is_safe_path("/etc/passwd")
        assert not _is_safe_path("\\Windows\\system32")
        assert not _is_safe_path("../escape")
        assert not _is_safe_path("foo/../../bar")
        assert _is_safe_path("roxy-src.zip")
        assert _is_safe_path("config.template.yaml")

    def test_zip_slip_in_bundle_fails(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        import io
        new_data = io.BytesIO()
        with zipfile.ZipFile(bundle, "r") as zf_in:
            with zipfile.ZipFile(new_data, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for name in zf_in.namelist():
                    zf_out.writestr(name, zf_in.read(name))
                zf_out.writestr("../evil", b"data")
        new_data.seek(0)
        bundle.write_bytes(new_data.read())
        result = rep.validate_bundle(bundle)
        assert not result["valid"]
        assert any("Unsafe path" in e for e in result["errors"])

    def test_missing_bundle(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        rep = Replicator()
        result = rep.validate_bundle(tmp_path / "nonexistent.zip")
        assert not result["valid"]
        assert any("not found" in e for e in result["errors"])


class TestDeployPlan:
    def test_invalid_bundle_no_steps(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        rep = Replicator()
        plan = rep.generate_deploy_plan(tmp_path / "missing.zip", "/opt/roxy")
        assert "BLOCKED" in plan
        assert "mkdir" not in plan  # no deployment steps
        assert "pip install" not in plan
        assert "Fix the bundle" in plan

    def test_valid_bundle_has_steps(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        plan = rep.generate_deploy_plan(bundle, "/opt/roxy")
        assert "BLOCKED" not in plan
        assert "TARGET=" in plan
        assert "mkdir -p $TARGET" in plan

    def test_shell_injection_sanitized(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        plan = rep.generate_deploy_plan(bundle, "/tmp/roxy; echo HACK")
        # Injection chain must not appear
        assert "; echo HACK" not in plan
        # The ';' should be stripped entirely
        assert ";" not in plan

    def test_bundle_path_injection_sanitized(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator, _sanitize_path
        assert ";" not in _sanitize_path("/tmp; rm -rf /")
        assert "|" not in _sanitize_path("x | cat /etc/passwd")
        assert "`" not in _sanitize_path("x `id`")
        assert "$" not in _sanitize_path("x $(curl evil)")

    def test_no_nonexistent_eval_validate(self, tmp_path: Path):
        from roxy.replication.replicate import Replicator
        bundle = tmp_path / "bundle.zip"
        rep = Replicator()
        rep.export_bundle(bundle, include_kb=False)
        plan = rep.generate_deploy_plan(bundle, "/opt/roxy")
        assert "roxy eval validate" not in plan
        # Should use 'roxy eval run' instead
        assert "roxy eval run" in plan


class TestSanitizePath:
    def test_removes_all_dangerous_chars(self):
        from roxy.replication.replicate import _sanitize_path
        assert _sanitize_path("safe/path") == "safe/path"
        assert ";" not in _sanitize_path("x; y")
        assert "|" not in _sanitize_path("x | y")
        assert "&" not in _sanitize_path("x && y")
        assert "$" not in _sanitize_path("x $HOME")
        assert "`" not in _sanitize_path("x `id`")
        assert "\"" not in _sanitize_path("x \"y\"")
        assert "'" not in _sanitize_path("x 'y'")
