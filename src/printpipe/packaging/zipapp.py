"""Build a portable stdlib zipapp artifact for PrintPipe."""

from __future__ import annotations

import shutil
import tempfile
import zipapp
from pathlib import Path
from typing import Any


DEFAULT_ENTRYPOINT = "printpipe.cli:main"
DEFAULT_INTERPRETER = "/usr/bin/env python3"


def build_zipapp_package(
    *,
    project_root: str | Path = Path("."),
    output_path: str | Path = Path("dist/printpipe.pyz"),
    entrypoint: str = DEFAULT_ENTRYPOINT,
    interpreter: str = DEFAULT_INTERPRETER,
) -> dict[str, Any]:
    """Build a cross-platform `python printpipe.pyz` artifact.

    The zipapp is intentionally a lightweight packaging artifact. It bundles the
    PrintPipe source package, not Python itself and not Bambu Studio.
    """

    root = Path(project_root).expanduser().resolve()
    package_source = root / "src" / "printpipe"
    if not package_source.is_dir():
        raise FileNotFoundError(f"printpipe package source not found: {package_source}")

    target = Path(output_path).expanduser()
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="printpipe-zipapp-") as temp_dir:
        staging = Path(temp_dir) / "app"
        shutil.copytree(
            package_source,
            staging / "printpipe",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
        zipapp.create_archive(
            staging,
            target=target,
            interpreter=interpreter,
            main=entrypoint,
            compressed=True,
        )

    return {
        "status": "ok",
        "artifact_path": str(target),
        "artifact_name": target.name,
        "entrypoint": entrypoint,
        "interpreter": interpreter,
        "size_bytes": target.stat().st_size,
        "bundles_python_runtime": False,
        "bundles_bambu_studio": False,
    }


__all__ = ["build_zipapp_package"]
