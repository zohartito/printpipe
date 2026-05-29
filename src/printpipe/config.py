"""Local project configuration for PrintPipe."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


CONFIG_PATH_ENV = "PRINTPIPE_CONFIG_PATH"
MEDIA_MESHGEN_COMMAND_ENV = "PRINTPIPE_MEDIA_MESHGEN_COMMAND"
DEFAULT_CONFIG_PATH = Path(".printpipe") / "config.json"


def resolve_config_path(
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    if config_path is not None:
        return config_path.expanduser()
    environment = os.environ if env is None else env
    configured_path = environment.get(CONFIG_PATH_ENV, "").strip()
    if configured_path:
        return Path(configured_path).expanduser()
    if env is not None:
        return Path("__printpipe_config_not_configured__")
    base = Path.cwd() if cwd is None else cwd
    return base / DEFAULT_CONFIG_PATH


def load_project_config(
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    path = resolve_config_path(env=env, cwd=cwd, config_path=config_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_project_config(
    *,
    updates: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    config_path: Path | None = None,
) -> Path:
    path = resolve_config_path(env=env, cwd=cwd, config_path=config_path)
    payload = load_project_config(env=env, cwd=cwd, config_path=path)
    payload.update(dict(updates))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def configured_media_meshgen_command(
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    config_path: Path | None = None,
) -> str:
    environment = os.environ if env is None else env
    env_command = environment.get(MEDIA_MESHGEN_COMMAND_ENV, "").strip()
    if env_command:
        return env_command
    config = load_project_config(env=environment, cwd=cwd, config_path=config_path)
    command = config.get("media_meshgen_command")
    return command.strip() if isinstance(command, str) else ""
