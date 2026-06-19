"""Tests for the init bootstrap command."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from roxy.cli.init_cmd import init_cmd


def test_init_yes_bootstraps_runtime(monkeypatch, tmp_path: Path):
    roxy_home = tmp_path / "roxy-home"
    monkeypatch.setenv("ROXY_HOME", str(roxy_home))

    result = CliRunner().invoke(
        init_cmd,
        [
            "--yes",
            "--name",
            "Tester",
            "--domain",
            "bioinformatics",
            "--topic",
            "single-cell",
            "--feed",
            "HN=https://hnrss.org/frontpage",
            "--skip-provider",
        ],
    )

    assert result.exit_code == 0
    assert (roxy_home / "config.yaml").exists()
    assert (roxy_home / "sessions").is_dir()
    assert (roxy_home / "knowledge" / "roxy.db").exists()

    config = yaml.safe_load((roxy_home / "config.yaml").read_text(encoding="utf-8"))
    assert config["user"]["name"] == "Tester"
    assert config["user"]["research_domain"] == "bioinformatics"
    assert config["user"]["topics"] == ["single-cell"]
    assert config["research"]["feeds"][0]["name"] == "HN"


def test_init_rejects_invalid_feed_spec(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ROXY_HOME", str(tmp_path / "roxy-home"))

    result = CliRunner().invoke(init_cmd, ["--yes", "--feed", "not-a-feed"])

    assert result.exit_code != 0
    assert "--feed must be in NAME=URL format" in result.output
