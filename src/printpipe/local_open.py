"""Local folder-opening helpers for CLI and local web affordances."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


OpenTarget = str
PathOpener = Callable[[Path], object]


@dataclass(frozen=True)
class OpenFolderResult:
    target: OpenTarget
    path: Path
    opened: bool


def open_run_folder(
    run_root: str | Path,
    *,
    target: OpenTarget = "run",
    dry_run: bool = False,
    path_opener: PathOpener | None = None,
) -> OpenFolderResult:
    """Open a safe folder inside a run, or return it without opening."""

    folder = resolve_run_folder_target(run_root, target=target)
    if dry_run:
        return OpenFolderResult(target=target, path=folder, opened=False)
    opener = path_opener or _platform_opener
    opener(folder)
    return OpenFolderResult(target=target, path=folder, opened=True)


def resolve_run_folder_target(run_root: str | Path, *, target: OpenTarget = "run") -> Path:
    """Resolve one of the supported local run folder targets."""

    root = Path(run_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    targets = {
        "run": root,
        "report": root / "80_reports",
        "reports": root / "80_reports",
        "bundle": root / "60_bundle",
        "bundles": root / "60_bundle",
    }
    try:
        folder = targets[target]
    except KeyError as exc:
        allowed = ", ".join(sorted(targets))
        raise ValueError(f"unknown open-folder target '{target}' (choose from {allowed})") from exc
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    return folder


def _platform_opener(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    if sys.platform.startswith("win"):
        subprocess.run(["explorer", str(path)], check=False)
        return
    subprocess.run(["xdg-open", str(path)], check=False)


__all__ = ["OpenFolderResult", "open_run_folder", "resolve_run_folder_target"]
