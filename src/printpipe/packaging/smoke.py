"""Clean-environment packaging smoke checks."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from printpipe import __version__
from printpipe.env.windows import is_windows_platform
from printpipe.pipeline import PipelineError, run_existing_mesh_pipeline


@dataclass(frozen=True)
class SmokeStep:
    id: str
    label: str
    command: str
    expected: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "command": self.command,
            "expected": self.expected,
        }


@dataclass(frozen=True)
class SmokeCheck:
    id: str
    label: str
    status: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class MacOSPackageSmokePlan:
    runs_dir: Path
    steps: tuple[SmokeStep, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": "macos",
            "runs_dir": str(self.runs_dir),
            "fixture_source": "generated_ascii_stl",
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class WindowsPackageSmokePlan:
    runs_dir: Path
    steps: tuple[SmokeStep, ...]

    def to_dict(self) -> dict[str, Any]:
        command = f"printpipe package-smoke --platform windows --runs-dir {self.runs_dir} --json"
        return {
            "platform": "windows",
            "runs_dir": str(self.runs_dir),
            "fixture_source": "generated_ascii_stl",
            "recommended_command": command,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class MacOSPackageSmokeResult:
    status: str
    runs_dir: Path
    input_fixture: Path
    run_root: Path | None
    checks: tuple[SmokeCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": "macos",
            "status": self.status,
            "runs_dir": str(self.runs_dir),
            "input_fixture": str(self.input_fixture),
            "run_root": str(self.run_root) if self.run_root is not None else "",
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class WindowsPackageSmokeResult:
    status: str
    runs_dir: Path
    input_fixture: Path
    run_root: Path | None
    checks: tuple[SmokeCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": "windows",
            "status": self.status,
            "runs_dir": str(self.runs_dir),
            "input_fixture": str(self.input_fixture),
            "run_root": str(self.run_root) if self.run_root is not None else "",
            "checks": [check.to_dict() for check in self.checks],
        }


def build_macos_package_smoke_plan(
    *,
    runs_dir: Path = Path("runs/package-smoke/macos"),
) -> MacOSPackageSmokePlan:
    """Return the commands a clean macOS package smoke run must cover."""

    fixture = _planned_fixture_path(runs_dir)
    steps = (
        SmokeStep(
            id="version",
            label="CLI version",
            command="printpipe --version",
            expected=f"prints printpipe {__version__}",
        ),
        SmokeStep(
            id="doctor",
            label="Environment doctor",
            command="printpipe doctor --platform macos --json",
            expected="prints JSON without crashing when optional dependencies are missing",
        ),
        SmokeStep(
            id="pipeline",
            label="Existing mesh pipeline",
            command=f"printpipe run {fixture} --runs-dir {runs_dir}",
            expected="creates a run folder with reports and a Bambu 3MF bundle",
        ),
        SmokeStep(
            id="status",
            label="Run status",
            command=f"printpipe status {runs_dir}/<run-id>",
            expected="summarizes manifest, reports, stages, and warnings",
        ),
        SmokeStep(
            id="open_report",
            label="Report handoff",
            command=f"printpipe open-report {runs_dir}/<run-id>",
            expected="prints a local HTML or Markdown report path",
        ),
        SmokeStep(
            id="serve",
            label="Local UI launch",
            command=f"printpipe serve --host 127.0.0.1 --port 8765 --runs-dir {runs_dir}",
            expected="starts the local web UI on loopback for manual inspection",
        ),
    )
    return MacOSPackageSmokePlan(runs_dir=runs_dir, steps=steps)


def build_windows_package_smoke_plan(
    *,
    runs_dir: Path = Path("runs/package-smoke/windows"),
) -> WindowsPackageSmokePlan:
    """Return the commands a clean Windows package smoke run must cover."""

    fixture = _planned_fixture_path(runs_dir)
    steps = (
        SmokeStep(
            id="version",
            label="CLI version",
            command="printpipe --version",
            expected=f"prints printpipe {__version__}",
        ),
        SmokeStep(
            id="doctor",
            label="Environment doctor",
            command="printpipe doctor --platform windows --json",
            expected="prints JSON without crashing when optional dependencies are missing",
        ),
        SmokeStep(
            id="pipeline",
            label="Existing mesh pipeline",
            command=f"printpipe run {fixture} --runs-dir {runs_dir}",
            expected="creates a run folder with reports and a Bambu 3MF bundle",
        ),
        SmokeStep(
            id="status",
            label="Run status",
            command=f"printpipe status {runs_dir}\\<run-id>",
            expected="summarizes manifest, reports, stages, and warnings",
        ),
        SmokeStep(
            id="open_report",
            label="Report handoff",
            command=f"printpipe open-report {runs_dir}\\<run-id>",
            expected="prints a local HTML or Markdown report path",
        ),
        SmokeStep(
            id="serve",
            label="Local UI launch",
            command=f"printpipe serve --host 127.0.0.1 --port 8765 --runs-dir {runs_dir}",
            expected="starts the local web UI on loopback for manual inspection",
        ),
    )
    return WindowsPackageSmokePlan(runs_dir=runs_dir, steps=steps)


def run_macos_package_smoke(
    *,
    runs_dir: Path = Path("runs/package-smoke/macos"),
) -> MacOSPackageSmokeResult:
    """Run the non-interactive macOS package smoke path against a generated STL."""

    runs_dir = runs_dir.expanduser().resolve()
    fixture = _write_tiny_tetrahedron(_fixture_path(runs_dir))
    checks: list[SmokeCheck] = [
        SmokeCheck(
            id="version",
            label="CLI version",
            status="ok",
            details={"version": __version__},
        ),
        SmokeCheck(
            id="input_fixture",
            label="Generated mesh fixture",
            status="ok",
            details={"path": str(fixture)},
        ),
    ]

    try:
        result = run_existing_mesh_pipeline(fixture, runs_dir)
    except PipelineError as exc:
        checks.append(
            SmokeCheck(
                id="pipeline_run",
                label="Existing mesh pipeline",
                status="failed",
                details={"error": str(exc), "run_root": str(exc.result.layout.root)},
            )
        )
        return MacOSPackageSmokeResult(
            status="failed",
            runs_dir=runs_dir,
            input_fixture=fixture,
            run_root=exc.result.layout.root,
            checks=tuple(checks),
        )

    run_root = result.layout.root
    checks.extend(
        (
            SmokeCheck(
                id="pipeline_run",
                label="Existing mesh pipeline",
                status="ok",
                details={"run_root": str(run_root)},
            ),
            _reports_check(result.layout.reports_dir),
            _bundle_check(result.layout.bundle_dir),
            SmokeCheck(
                id="slice_gate",
                label="Slice gate",
                status="manual_required",
                details={
                    "reason": (
                        "The package smoke path verifies bundle/report creation. "
                        "Live Bambu CLI slicing remains F13 because Bambu Studio "
                        "2.6.00.51 segfaults on this macOS 26.5 host."
                    )
                },
            ),
        )
    )

    status = "ok" if all(check.status != "failed" for check in checks) else "failed"
    return MacOSPackageSmokeResult(
        status=status,
        runs_dir=runs_dir,
        input_fixture=fixture,
        run_root=run_root,
        checks=tuple(checks),
    )


def run_windows_package_smoke(
    *,
    runs_dir: Path = Path("runs/package-smoke/windows"),
    platform_name: str | None = None,
) -> WindowsPackageSmokeResult:
    """Run the Windows smoke path only when invoked on Windows."""

    current_platform = sys.platform if platform_name is None else platform_name
    runs_dir = runs_dir.expanduser().resolve()
    fixture = _fixture_path(runs_dir)
    if not is_windows_platform(current_platform):
        return WindowsPackageSmokeResult(
            status="manual_required",
            runs_dir=runs_dir,
            input_fixture=fixture,
            run_root=None,
            checks=(
                SmokeCheck(
                    id="windows_runtime",
                    label="Windows runtime",
                    status="manual_required",
                    details={
                        "platform": current_platform,
                        "reason": (
                            "run this command on Windows: "
                            f"printpipe package-smoke --platform windows --runs-dir {runs_dir} --json"
                        ),
                    },
                ),
            ),
        )

    fixture = _write_tiny_tetrahedron(fixture)
    checks: list[SmokeCheck] = [
        SmokeCheck(
            id="windows_runtime",
            label="Windows runtime",
            status="ok",
            details={"platform": current_platform},
        ),
        SmokeCheck(
            id="version",
            label="CLI version",
            status="ok",
            details={"version": __version__},
        ),
        SmokeCheck(
            id="input_fixture",
            label="Generated mesh fixture",
            status="ok",
            details={"path": str(fixture)},
        ),
    ]

    try:
        result = run_existing_mesh_pipeline(fixture, runs_dir)
    except PipelineError as exc:
        checks.append(
            SmokeCheck(
                id="pipeline_run",
                label="Existing mesh pipeline",
                status="failed",
                details={"error": str(exc), "run_root": str(exc.result.layout.root)},
            )
        )
        return WindowsPackageSmokeResult(
            status="failed",
            runs_dir=runs_dir,
            input_fixture=fixture,
            run_root=exc.result.layout.root,
            checks=tuple(checks),
        )

    run_root = result.layout.root
    checks.extend(
        (
            SmokeCheck(
                id="pipeline_run",
                label="Existing mesh pipeline",
                status="ok",
                details={"run_root": str(run_root)},
            ),
            _reports_check(result.layout.reports_dir),
            _bundle_check(result.layout.bundle_dir),
            SmokeCheck(
                id="slice_gate",
                label="Slice gate",
                status="manual_required",
                details={
                    "reason": (
                        "The Windows package smoke path verifies bundle/report "
                        "creation. Live Bambu CLI slicing should be checked on "
                        "the target Windows+Bambu Studio install."
                    )
                },
            ),
        )
    )
    status = "ok" if all(check.status != "failed" for check in checks) else "failed"
    return WindowsPackageSmokeResult(
        status=status,
        runs_dir=runs_dir,
        input_fixture=fixture,
        run_root=run_root,
        checks=tuple(checks),
    )


def _fixture_path(runs_dir: Path) -> Path:
    return runs_dir.expanduser().resolve().parent / "package_smoke_tiny_tetrahedron.stl"


def _planned_fixture_path(runs_dir: Path) -> Path:
    return runs_dir.parent / "package_smoke_tiny_tetrahedron.stl"


def _write_tiny_tetrahedron(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TINY_TETRAHEDRON_STL, encoding="utf-8")
    return path


def _reports_check(reports_dir: Path) -> SmokeCheck:
    required = (
        reports_dir / "run_report.json",
        reports_dir / "run_report.md",
        reports_dir / "run_report.html",
    )
    missing = [path for path in required if not path.exists()]
    status = "failed" if missing else "ok"
    details: dict[str, Any] = {
        "paths": [str(path) for path in required],
        "missing": [str(path) for path in missing],
    }
    if not missing:
        report = json.loads(required[0].read_text(encoding="utf-8"))
        details["warnings"] = len(report.get("warnings", []))
    return SmokeCheck(
        id="reports",
        label="Reports",
        status=status,
        details=details,
    )


def _bundle_check(bundle_dir: Path) -> SmokeCheck:
    bundles = sorted(bundle_dir.glob("*.3mf"))
    return SmokeCheck(
        id="bundle",
        label="Bambu 3MF bundle",
        status="ok" if bundles else "failed",
        details={"paths": [str(path) for path in bundles]},
    )


_TINY_TETRAHEDRON_STL = """solid package_smoke_tiny_tetrahedron
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 0 10 0
      vertex 10 0 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 0 10
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 0 10
      vertex 0 10 0
    endloop
  endfacet
  facet normal 1 1 1
    outer loop
      vertex 10 0 0
      vertex 0 10 0
      vertex 0 0 10
    endloop
  endfacet
endsolid package_smoke_tiny_tetrahedron
"""


__all__ = [
    "MacOSPackageSmokePlan",
    "MacOSPackageSmokeResult",
    "SmokeCheck",
    "SmokeStep",
    "WindowsPackageSmokePlan",
    "WindowsPackageSmokeResult",
    "build_macos_package_smoke_plan",
    "build_windows_package_smoke_plan",
    "run_macos_package_smoke",
    "run_windows_package_smoke",
]
