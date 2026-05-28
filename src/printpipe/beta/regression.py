"""Regression manifest helpers for beta dogfood runs."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Mapping, Sequence as SequenceABC
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = 1
CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class ExpectedOutcome(str, Enum):
    FAILURE = "failure"
    SUCCESS = "success"


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    source_run_id: str
    fixture_path: Path
    command: tuple[str, ...]
    expected: ExpectedOutcome = ExpectedOutcome.FAILURE
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixture_path", Path(self.fixture_path))
        object.__setattr__(self, "command", _normalize_command(self.command))
        object.__setattr__(self, "expected", _normalize_expected(self.expected))

    @property
    def rendered_command(self) -> str:
        return render_command(self.command)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source_run_id": self.source_run_id,
            "fixture_path": self.fixture_path.as_posix(),
            "command": list(self.command),
            "expected": self.expected.value,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RegressionManifest:
    cases: tuple[RegressionCase, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "cases", tuple(_case_from_value(case) for case in self.cases))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cases": [case.to_dict() for case in self.cases],
        }


def render_command(command: Sequence[str | Path]) -> str:
    return shlex.join(_normalize_command(command))


def validate_regression_manifest(manifest: Any) -> tuple[str, ...]:
    payload = _manifest_payload(manifest)
    if not isinstance(payload, Mapping):
        return ("manifest must be a JSON object",)

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append("cases must be a list")
        return tuple(errors)

    seen_case_ids: dict[str, int] = {}
    for index, case in enumerate(cases):
        errors.extend(_validate_case_payload(case, index=index, seen_case_ids=seen_case_ids))

    return tuple(errors)


def write_regression_manifest(manifest: RegressionManifest, path: str | Path) -> Path:
    payload = manifest.to_dict()
    errors = validate_regression_manifest(payload)
    if errors:
        raise ValueError("; ".join(errors))

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_regression_manifest(path: str | Path) -> RegressionManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_regression_manifest(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return _manifest_from_payload(payload)


def run_regression_manifest(
    path: str | Path,
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """Run every regression case and return a JSON-friendly status report."""

    manifest_path = Path(path).expanduser().resolve()
    manifest = load_regression_manifest(manifest_path)
    case_results = [
        _run_regression_case(
            case,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        for case in manifest.cases
    ]
    failed_count = sum(1 for result in case_results if result["status"] != "passed")
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_path": str(manifest_path),
        "overall_status": "passed" if failed_count == 0 else "failed",
        "case_count": len(case_results),
        "passed_count": len(case_results) - failed_count,
        "failed_count": failed_count,
        "cases": case_results,
    }


def build_failure_regression_status(
    runs_dir: str | Path,
    *,
    regression_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Report whether captured beta failures have matching regression cases."""

    runs_root = Path(runs_dir).expanduser().resolve()
    failures = _load_failure_report_summaries(runs_root)
    failure_ids = [failure["run_id"] for failure in failures]
    if not failures:
        return {
            "schema_version": SCHEMA_VERSION,
            "runs_dir": str(runs_root),
            "regression_manifest_path": (
                str(Path(regression_manifest_path).expanduser().resolve())
                if regression_manifest_path is not None
                else ""
            ),
            "overall_status": "no_failures",
            "failure_report_count": 0,
            "regression_case_count": 0,
            "covered_failure_count": 0,
            "missing_regression_source_run_ids": [],
            "failure_reports": [],
        }

    manifest_path = (
        Path(regression_manifest_path).expanduser().resolve()
        if regression_manifest_path is not None
        else None
    )
    if manifest_path is None or not manifest_path.exists():
        return _failure_regression_payload(
            runs_root=runs_root,
            manifest_path=manifest_path,
            failures=failures,
            case_count=0,
            covered_ids=[],
            overall_status="missing_manifest",
        )

    try:
        manifest = load_regression_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = _failure_regression_payload(
            runs_root=runs_root,
            manifest_path=manifest_path,
            failures=failures,
            case_count=0,
            covered_ids=[],
            overall_status="invalid_manifest",
        )
        payload["error"] = str(exc)
        return payload

    case_source_ids = {
        case.source_run_id
        for case in manifest.cases
    }
    covered_ids = [run_id for run_id in failure_ids if run_id in case_source_ids]
    missing_ids = [run_id for run_id in failure_ids if run_id not in case_source_ids]
    return _failure_regression_payload(
        runs_root=runs_root,
        manifest_path=manifest_path,
        failures=failures,
        case_count=len(manifest.cases),
        covered_ids=covered_ids,
        overall_status="passed" if not missing_ids else "missing_regressions",
    )


def case_from_run(
    run_root: str | Path,
    *,
    command: Sequence[str | Path],
    case_id: str | None = None,
    expected: ExpectedOutcome | str = ExpectedOutcome.FAILURE,
    fixture_path: str | Path | None = None,
    notes: str = "",
) -> RegressionCase:
    root = Path(run_root).expanduser().resolve()
    run_manifest_path = root / "manifest.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(run_manifest, Mapping):
        raise ValueError(f"run manifest must be a JSON object: {run_manifest_path}")

    source_run_id = _non_empty_text(run_manifest.get("run_id")) or root.name
    resolved_fixture_path = Path(fixture_path) if fixture_path is not None else _fixture_path_from_run(root, run_manifest)

    return RegressionCase(
        case_id=case_id or f"regression-{_slug(source_run_id)}",
        source_run_id=source_run_id,
        fixture_path=resolved_fixture_path,
        command=_normalize_command(command),
        expected=expected,
        notes=notes,
    )


def _failure_regression_payload(
    *,
    runs_root: Path,
    manifest_path: Path | None,
    failures: Sequence[dict[str, Any]],
    case_count: int,
    covered_ids: Sequence[str],
    overall_status: str,
) -> dict[str, Any]:
    covered = set(covered_ids)
    failure_ids = [failure["run_id"] for failure in failures]
    missing = [run_id for run_id in failure_ids if run_id not in covered]
    return {
        "schema_version": SCHEMA_VERSION,
        "runs_dir": str(runs_root),
        "regression_manifest_path": str(manifest_path) if manifest_path else "",
        "overall_status": overall_status,
        "failure_report_count": len(failures),
        "regression_case_count": case_count,
        "covered_failure_count": len(covered_ids),
        "missing_regression_source_run_ids": missing,
        "failure_reports": list(failures),
    }


def _load_failure_report_summaries(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    reports: list[dict[str, Any]] = []
    for report_path in sorted(runs_dir.glob("**/90_beta/failure_report.json")):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_root = report_path.parents[1]
        reports.append(
            {
                "run_id": str(payload.get("run_id") or run_root.name),
                "run_root": str(run_root),
                "json_path": str(report_path),
                "failed_stage": str(payload.get("failed_stage") or ""),
                "symptom_count": len(_list(payload.get("symptoms"))),
                "reproduction_command": str(payload.get("reproduction_command") or ""),
            }
        )
    return reports


def _manifest_payload(manifest: Any) -> Any:
    if isinstance(manifest, RegressionManifest):
        return manifest.to_dict()
    return manifest


def _manifest_from_payload(payload: Mapping[str, Any]) -> RegressionManifest:
    return RegressionManifest(
        schema_version=payload["schema_version"],
        cases=tuple(_case_from_payload(case) for case in payload["cases"]),
    )


def _run_regression_case(
    case: RegressionCase,
    *,
    cwd: str | Path | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = list(case.command)
    try:
        completed = subprocess.run(
            command,
            cwd=Path(cwd).expanduser() if cwd is not None else None,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        actual = "success" if completed.returncode == 0 else "failure"
        message = _case_message(expected=case.expected, actual=actual)
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = _optional_completed_text(exc.stdout)
        stderr = _optional_completed_text(exc.stderr)
        actual = "timeout"
        message = f"command timed out after {timeout_seconds:g} seconds"
    except OSError as exc:
        exit_code = None
        stdout = ""
        stderr = str(exc)
        actual = "error"
        message = f"command could not start: {exc}"

    status = "passed" if actual == case.expected.value else "failed"
    return {
        "case_id": case.case_id,
        "source_run_id": case.source_run_id,
        "fixture_path": case.fixture_path.as_posix(),
        "command": list(case.command),
        "rendered_command": case.rendered_command,
        "expected": case.expected.value,
        "actual": actual,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "message": message,
        "notes": case.notes,
    }


def _case_message(*, expected: ExpectedOutcome, actual: str) -> str:
    if actual == expected.value:
        return "matched expected outcome"
    if expected == ExpectedOutcome.FAILURE and actual == "success":
        return "expected failure but command succeeded"
    if expected == ExpectedOutcome.SUCCESS and actual == "failure":
        return "expected success but command failed"
    return f"expected {expected.value} but got {actual}"


def _optional_completed_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _case_from_value(value: Any) -> RegressionCase:
    if isinstance(value, RegressionCase):
        return value
    if isinstance(value, Mapping):
        return _case_from_payload(value)
    raise TypeError(f"regression cases must be RegressionCase instances: {value!r}")


def _case_from_payload(payload: Mapping[str, Any]) -> RegressionCase:
    return RegressionCase(
        case_id=payload["case_id"],
        source_run_id=payload["source_run_id"],
        fixture_path=Path(payload["fixture_path"]),
        command=tuple(payload["command"]),
        expected=payload["expected"],
        notes=payload["notes"],
    )


def _validate_case_payload(case: Any, *, index: int, seen_case_ids: dict[str, int]) -> tuple[str, ...]:
    prefix = f"cases[{index}]"
    if not isinstance(case, Mapping):
        return (f"{prefix} must be a JSON object",)

    errors: list[str] = []
    required_fields = ("case_id", "source_run_id", "fixture_path", "command", "expected", "notes")
    for field in required_fields:
        if field not in case:
            errors.append(f"{prefix}.{field} is required")

    case_id = case.get("case_id")
    if not _is_non_empty_string(case_id):
        errors.append(f"{prefix}.case_id must be a non-empty string")
    elif not CASE_ID_PATTERN.fullmatch(case_id):
        errors.append(f"{prefix}.case_id must use lowercase letters, digits, '.', '_' or '-'")
    elif case_id in seen_case_ids:
        errors.append(f"{prefix}.case_id duplicates cases[{seen_case_ids[case_id]}].case_id: {case_id}")
    else:
        seen_case_ids[case_id] = index

    source_run_id = case.get("source_run_id")
    if not _is_non_empty_string(source_run_id):
        errors.append(f"{prefix}.source_run_id must be a non-empty string")

    fixture_path = case.get("fixture_path")
    if not _is_non_empty_string(fixture_path):
        errors.append(f"{prefix}.fixture_path must be a non-empty string")
    elif "\x00" in fixture_path:
        errors.append(f"{prefix}.fixture_path must not contain null bytes")

    command = case.get("command")
    if not isinstance(command, list) or not command:
        errors.append(f"{prefix}.command must be a non-empty list of strings")
    elif not all(_is_non_empty_string(part) for part in command):
        errors.append(f"{prefix}.command must be a non-empty list of strings")

    expected = case.get("expected")
    if expected not in {outcome.value for outcome in ExpectedOutcome}:
        errors.append(f"{prefix}.expected must be 'failure' or 'success'")

    notes = case.get("notes")
    if not isinstance(notes, str):
        errors.append(f"{prefix}.notes must be a string")

    return tuple(errors)


def _normalize_command(command: Sequence[str | Path]) -> tuple[str, ...]:
    if isinstance(command, (str, Path)):
        return (str(command),)
    if not isinstance(command, SequenceABC):
        raise TypeError(f"command must be a sequence of strings or paths: {command!r}")
    return tuple(str(part) for part in command)


def _normalize_expected(expected: ExpectedOutcome | str) -> ExpectedOutcome:
    if isinstance(expected, ExpectedOutcome):
        return expected
    return ExpectedOutcome(str(expected))


def _fixture_path_from_run(root: Path, run_manifest: Mapping[str, Any]) -> Path:
    input_payload = run_manifest.get("input")
    if not isinstance(input_payload, Mapping):
        raise ValueError("run manifest does not include an input object; pass fixture_path")

    stored_path = _non_empty_text(input_payload.get("stored_path"))
    if stored_path is not None:
        return root / stored_path

    source_path = _non_empty_text(input_payload.get("source_path"))
    if source_path is not None:
        return Path(source_path)

    raise ValueError("run manifest does not include input.stored_path or input.source_path; pass fixture_path")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def _non_empty_text(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


__all__ = [
    "ExpectedOutcome",
    "RegressionCase",
    "RegressionManifest",
    "build_failure_regression_status",
    "case_from_run",
    "load_regression_manifest",
    "render_command",
    "run_regression_manifest",
    "validate_regression_manifest",
    "write_regression_manifest",
]
