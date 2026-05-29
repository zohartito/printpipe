from __future__ import annotations

import json
from pathlib import Path

from printpipe.cli import build_parser, main
from printpipe.config import (
    CONFIG_PATH_ENV,
    configured_media_meshgen_command,
    load_project_config,
)
from printpipe.env.doctor import build_environment_report


def test_media_meshgen_configure_parser_accepts_command_and_config_path(tmp_path: Path):
    parser = build_parser()
    config_path = tmp_path / "config.json"

    args = parser.parse_args(
        [
            "media-meshgen-configure",
            "--command",
            "printpipe media-meshgen-heightfield",
            "--config",
            str(config_path),
        ]
    )

    assert args.command == "media-meshgen-configure"
    assert args.media_meshgen_command == "printpipe media-meshgen-heightfield"
    assert args.config_path == config_path


def test_media_meshgen_configure_writes_project_config(
    tmp_path: Path,
    capsys,
):
    config_path = tmp_path / ".printpipe" / "config.json"

    exit_code = main(
        [
            "media-meshgen-configure",
            "--command",
            "printpipe media-meshgen-heightfield",
            "--config",
            str(config_path),
        ]
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert payload["media_meshgen_command"] == "printpipe media-meshgen-heightfield"
    assert f"wrote PrintPipe config: {config_path}" in captured.out


def test_configured_media_meshgen_command_uses_env_before_project_config(
    tmp_path: Path,
):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"media_meshgen_command": "configured-command"}),
        encoding="utf-8",
    )

    command = configured_media_meshgen_command(
        env={
            CONFIG_PATH_ENV: str(config_path),
            "PRINTPIPE_MEDIA_MESHGEN_COMMAND": "env-command",
        }
    )

    assert command == "env-command"


def test_configured_media_meshgen_command_ignores_default_config_when_env_injected(
    tmp_path: Path,
):
    config_path = tmp_path / ".printpipe" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"media_meshgen_command": "configured-command"}),
        encoding="utf-8",
    )

    command = configured_media_meshgen_command(env={}, cwd=tmp_path)

    assert command == ""


def test_configured_media_meshgen_command_reads_default_project_config(
    monkeypatch,
    tmp_path: Path,
):
    config_path = tmp_path / ".printpipe" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"media_meshgen_command": "configured-command"}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    monkeypatch.delenv("PRINTPIPE_MEDIA_MESHGEN_COMMAND", raising=False)

    command = configured_media_meshgen_command()

    assert command == "configured-command"


def test_environment_report_counts_project_config_media_command_provider(
    tmp_path: Path,
):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"media_meshgen_command": "printpipe media-meshgen-heightfield"}),
        encoding="utf-8",
    )

    report = build_environment_report(
        platform_name="linux",
        env={CONFIG_PATH_ENV: str(config_path)},
        workspace_paths=(tmp_path,),
        bambu_studio_roots=(),
        profile_base_paths=(),
    )

    providers = {
        provider["provider_id"]: provider
        for provider in report["meshgen"]["providers"]
    }
    assert report["meshgen"]["overall_status"] == "ready"
    assert report["meshgen"]["live_media_provider_count"] == 1
    assert providers["media_command"]["status"] == "succeeded"
    assert "project config" in providers["media_command"]["message"]


def test_environment_report_reads_default_project_config_for_real_environment(
    monkeypatch,
    tmp_path: Path,
):
    config_path = tmp_path / ".printpipe" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"media_meshgen_command": "printpipe media-meshgen-heightfield"}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    monkeypatch.delenv("PRINTPIPE_MEDIA_MESHGEN_COMMAND", raising=False)

    report = build_environment_report(
        platform_name="linux",
        bambu_studio_roots=(),
        profile_base_paths=(),
    )

    providers = {
        provider["provider_id"]: provider
        for provider in report["meshgen"]["providers"]
    }
    assert report["meshgen"]["overall_status"] == "ready"
    assert report["meshgen"]["live_media_provider_count"] == 1
    assert providers["media_command"]["status"] == "succeeded"
    assert "project config" in providers["media_command"]["message"]


def test_load_project_config_returns_empty_for_missing_config(tmp_path: Path):
    assert load_project_config(config_path=tmp_path / "missing.json") == {}
