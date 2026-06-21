"""Tests for the init v1.0 onboarding command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from roxy.cli.init_cmd import init_cmd


def test_init_yes_with_provider_bootstraps_runtime(monkeypatch, tmp_path: Path):
    roxy_home = tmp_path / "roxy-home"
    monkeypatch.setenv("ROXY_HOME", str(roxy_home))

    result = CliRunner().invoke(
        init_cmd,
        [
            "--yes",
            "--provider", "deepseek",
            "--api-key", "sk-test123",
            "--name", "Tester",
        ],
    )

    assert result.exit_code == 0
    assert (roxy_home / "config.yaml").exists()
    assert (roxy_home / "sessions").is_dir()
    assert (roxy_home / "knowledge" / "roxy.db").exists()

    config = yaml.safe_load((roxy_home / "config.yaml").read_text(encoding="utf-8"))
    assert config["user"]["name"] == "Tester"
    assert config["models"]["providers"]["deepseek"]["api_key"] == "sk-test123"
    assert "deepseek" in config["models"]["default"]


def test_init_quick_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ROXY_HOME", str(tmp_path / "roxy-home"))

    result = CliRunner().invoke(
        init_cmd,
        ["--quick", "--yes", "--provider", "openai", "--api-key", "sk-test"],
    )

    assert result.exit_code == 0


def test_init_defaults_to_deepseek_in_yes_mode(monkeypatch, tmp_path: Path):
    rh = tmp_path / "roxy-home"
    monkeypatch.setenv("ROXY_HOME", str(rh))

    result = CliRunner().invoke(init_cmd, ["--yes"])

    assert result.exit_code == 0
    config = yaml.safe_load((rh / "config.yaml").read_text(encoding="utf-8"))
    assert "deepseek" in config["models"]["default"]


def test_init_force_reconfigures(monkeypatch, tmp_path: Path):
    roxy_home = tmp_path / "roxy-home"
    monkeypatch.setenv("ROXY_HOME", str(roxy_home))

    # First init
    CliRunner().invoke(init_cmd, [
        "--yes", "--provider", "openai", "--api-key", "sk-first", "--name", "First",
    ])

    # Second init with force
    result = CliRunner().invoke(init_cmd, [
        "--force", "--yes", "--provider", "deepseek", "--api-key", "sk-second", "--name", "Second",
    ])
    assert result.exit_code == 0

    config = yaml.safe_load((roxy_home / "config.yaml").read_text(encoding="utf-8"))
    assert config["user"]["name"] == "Second"
    assert config["models"]["providers"]["deepseek"]["api_key"] == "sk-second"


def test_init_env_var_key_detected(monkeypatch, tmp_path: Path):
    rh = tmp_path / "roxy-home"
    monkeypatch.setenv("ROXY_HOME", str(rh))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-detected")

    result = CliRunner().invoke(init_cmd, [
        "--yes", "--provider", "deepseek",
    ])

    assert result.exit_code == 0
    config = yaml.safe_load((rh / "config.yaml").read_text(encoding="utf-8"))
    assert config["models"]["providers"]["deepseek"]["api_key"] == "sk-env-detected"
