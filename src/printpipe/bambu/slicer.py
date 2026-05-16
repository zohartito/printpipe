"""Bambu CLI slice-gate skeleton.

The real Bambu Studio executable is intentionally outside unit-test scope. This
module wraps a command, records raw logs, parses lightweight estimate patterns,
and classifies known hard slicer failures so later orchestration can decide
whether to retry repair, bed fit, profile validation, or support/orientation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus

BAMBU_STUDIO_CLI_ENV = "PRINTPIPE_BAMBU_STUDIO_CLI"
_BAMBU_STUDIO_CLI_ENV_KEYS: tuple[str, ...] = (
    BAMBU_STUDIO_CLI_ENV,
    "BAMBU_STUDIO_CLI",
    "BAMBU_STUDIO_EXECUTABLE",
)
_MACOS_APP_BUNDLES: tuple[str, ...] = (
    "BambuStudio.app",
    "Bambu Studio.app",
)
_WINDOWS_INSTALL_DIRS: tuple[str, ...] = (
    "Bambu Studio",
    "BambuStudio",
)
_WINDOWS_EXECUTABLE_NAMES: tuple[str, ...] = (
    "bambu-studio.exe",
    "BambuStudio.exe",
    "Bambu Studio.exe",
)
_PATH_EXECUTABLE_NAMES: tuple[str, ...] = (
    "bambu-studio",
    "BambuStudio",
)


@dataclass(frozen=True)
class SliceResult:
    return_code: int = 0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    time_seconds: int | None = None
    filament_g: float | None = None
    layer_count: int | None = None
    cost: float | None = None
    gcode_path: Path | None = None
    log_path: Path | None = None
    stderr_log_path: Path | None = None


class SliceGateError(RuntimeError):
    """Raised when a slice result should stop the run."""


class BambuCliNotFoundError(SliceGateError):
    """Raised when PrintPipe cannot find a Bambu Studio CLI executable."""


NONCRITICAL_WARNING_MARKERS: tuple[str, ...] = (
    "ZFiller: both point in subject",
)

_HARD_FAILURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "non-manifold mesh detected; retry mesh repair before slicing",
        re.compile(r"\bnon[-\s]?manifold\b", re.IGNORECASE),
    ),
    (
        "boundary/open mesh detected; retry mesh repair before slicing",
        re.compile(
            r"\b(boundary edge|boundary edges|open contour|open contours|not watertight)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "off-bed placement detected; retry orientation, scale, or bed transform",
        re.compile(
            r"\b(outside (?:the )?(?:print )?bed|off[-\s]?bed|bed boundary|"
            r"exceeds? (?:the )?printable|does not fit (?:on|within)|not on (?:the )?plate)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "enum replacement detected; retry Bambu profile validation",
        re.compile(
            r"\b(enum replacement|invalid enum|unknown enum|will be replaced|"
            r"replaced by|support_style\s+organic)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "floating cantilever detected; retry orientation/support rules",
        re.compile(
            r"\b(floating cantilever|cantilever|floating (?:area|region|regions))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "missing Bambu profile detected; retry 3MF bundling/profile selection",
        re.compile(r"\b(missing profile|profile not found|failed to load profile)\b", re.IGNORECASE),
    ),
)


def bambu_cli_candidate_paths(
    *,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    extra_candidates: Sequence[str | Path] = (),
) -> tuple[Path, ...]:
    """Return likely Bambu Studio CLI executable paths in search order."""

    values = os.environ if env is None else env
    normalized_platform = _normalize_platform(platform or sys.platform)
    candidates: list[Path] = []

    for key in _BAMBU_STUDIO_CLI_ENV_KEYS:
        value = values.get(key, "").strip()
        if value:
            candidates.extend(_cli_paths_from_configured_path(value, normalized_platform))

    candidates.extend(Path(candidate).expanduser() for candidate in extra_candidates)
    candidates.extend(_path_candidates_from_env(values))

    if normalized_platform == "macos":
        candidates.extend(_macos_bambu_cli_candidates(values))
    elif normalized_platform == "windows":
        candidates.extend(_windows_bambu_cli_candidates(values))
    else:
        candidates.extend(_linux_bambu_cli_candidates(values))

    return _dedupe_paths(candidates)


def discover_bambu_cli_executable(
    *,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    extra_candidates: Sequence[str | Path] = (),
    path_exists: Callable[[Path], bool] | None = None,
) -> Path | None:
    """Return the first existing Bambu Studio CLI executable candidate."""

    exists = _path_exists if path_exists is None else path_exists
    for candidate in bambu_cli_candidate_paths(
        env=env,
        platform=platform,
        extra_candidates=extra_candidates,
    ):
        if exists(candidate):
            return candidate
    return None


def build_bambu_slice_command(
    *,
    three_mf_path: str | Path,
    output_dir: str | Path,
    executable: str | Path | None = None,
    plate: int = 0,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
    extra_candidates: Sequence[str | Path] = (),
    path_exists: Callable[[Path], bool] | None = None,
) -> tuple[str, ...]:
    """Build a Bambu Studio CLI command that slices a 3MF into an output folder."""

    if executable is None:
        executable_path = discover_bambu_cli_executable(
            env=env,
            platform=platform,
            extra_candidates=extra_candidates,
            path_exists=path_exists,
        )
        if executable_path is None:
            candidates = bambu_cli_candidate_paths(
                env=env,
                platform=platform,
                extra_candidates=extra_candidates,
            )
            raise BambuCliNotFoundError(_missing_bambu_cli_message(candidates))
    else:
        executable_path = Path(executable).expanduser()

    return (
        str(executable_path),
        "--slice",
        str(plate),
        "--outputdir",
        str(Path(output_dir).expanduser()),
        str(Path(three_mf_path).expanduser()),
    )


def classify_slicer_output(stdout: str, stderr: str, return_code: int) -> SliceResult:
    """Classify raw Bambu CLI output into warnings and hard errors."""

    warnings: list[str] = []
    errors: list[str] = []
    combined = "\n".join(part for part in (stdout, stderr) if part)

    for line in combined.splitlines():
        text = line.strip()
        if not text:
            continue

        hard_failure = _hard_failure_for_line(text)
        if hard_failure is not None:
            errors.append(hard_failure)
            continue

        warning = _warning_from_line(text)
        if warning:
            warnings.append(warning)

    if return_code != 0:
        errors.insert(0, f"slicer exited with return code {return_code}")

    estimate = parse_slice_estimate_from_text(combined)
    return replace(
        estimate,
        return_code=return_code,
        warnings=tuple(_dedupe(warnings)),
        errors=tuple(_dedupe(errors)),
    )


def parse_slice_estimate_from_text(text: str) -> SliceResult:
    """Parse simple Bambu stdout/G-code/Markdown estimate patterns."""

    return SliceResult(
        time_seconds=_parse_time_seconds(text),
        filament_g=_parse_filament_g(text),
        layer_count=_parse_layer_count(text),
        cost=_parse_cost(text),
    )


def run_slice_command(command: Sequence[str | Path], run_layout: object) -> SliceResult:
    """Run a slicer command, save stdout/stderr logs, and return a parsed result."""

    slice_dir = Path(getattr(run_layout, "slice_dir"))
    slice_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = slice_dir / "bambu_slice_stdout.log"
    stderr_log = slice_dir / "bambu_slice_stderr.log"

    completed = subprocess.run(
        [str(part) for part in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    stdout_log.write_text(completed.stdout, encoding="utf-8")
    stderr_log.write_text(completed.stderr, encoding="utf-8")

    result = classify_slicer_output(completed.stdout, completed.stderr, completed.returncode)
    return replace(
        result,
        gcode_path=_find_gcode_path(completed.stdout, completed.stderr, slice_dir),
        log_path=stdout_log,
        stderr_log_path=stderr_log,
    )


def slice_result_to_receipt(result: SliceResult, run_layout: object) -> StageReceipt:
    """Write a stable slice result JSON artifact and return a stage receipt."""

    result_json_path = write_slice_result_json(result, run_layout)
    failed = result.return_code != 0 or bool(result.errors)
    return StageReceipt(
        stage="slice",
        status=StageStatus.FAILED if failed else StageStatus.SUCCEEDED,
        message="Bambu CLI slice failed." if failed else "Bambu CLI slice passed.",
        artifacts=slice_result_artifacts(result, result_json_path=result_json_path),
        metrics=_slice_result_metrics(result),
    )


def write_slice_result_json(result: SliceResult, run_layout: object) -> Path:
    """Write ``slice_result.json`` into the run slice directory."""

    slice_dir = Path(getattr(run_layout, "slice_dir"))
    slice_dir.mkdir(parents=True, exist_ok=True)
    path = slice_dir / "slice_result.json"
    path.write_text(
        json.dumps(_slice_result_payload(result), indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def slice_result_artifacts(
    result: SliceResult,
    *,
    result_json_path: Path,
) -> tuple[Artifact, ...]:
    """Return receipt artifacts for a slice result and its available files."""

    artifacts: list[Artifact] = [
        Artifact(
            kind=ArtifactKind.SLICE_LOG,
            path=result_json_path,
            label="Slice result JSON",
        )
    ]

    if _file_has_content(result.log_path):
        artifacts.append(
            Artifact(
                kind=ArtifactKind.SLICE_LOG,
                path=result.log_path,
                label="Bambu slicer stdout log",
            )
        )
    if _file_has_content(result.stderr_log_path):
        artifacts.append(
            Artifact(
                kind=ArtifactKind.SLICE_LOG,
                path=result.stderr_log_path,
                label="Bambu slicer stderr log",
            )
        )
    if result.gcode_path is not None:
        artifacts.append(
            Artifact(
                kind=ArtifactKind.SLICE_LOG,
                path=result.gcode_path,
                label="G-code output",
            )
        )

    return tuple(artifacts)


def gate_slice(
    result: SliceResult,
    *,
    allowed_warning_markers: Sequence[str] = NONCRITICAL_WARNING_MARKERS,
) -> SliceResult:
    """Raise for hard slice failures; return the result for accepted outcomes."""

    problems: list[str] = []
    if result.return_code != 0:
        problems.append(f"slicer exited with return code {result.return_code}")
    problems.extend(result.errors)

    unallowed_warnings = [
        warning
        for warning in result.warnings
        if not _warning_allowed(warning, allowed_warning_markers)
    ]
    if unallowed_warnings:
        problems.append("unallowlisted slicer warnings: " + "; ".join(unallowed_warnings))

    if problems:
        raise SliceGateError("Slice gate failed: " + "; ".join(_dedupe(problems)))

    return result


def _hard_failure_for_line(line: str) -> str | None:
    for message, pattern in _HARD_FAILURE_PATTERNS:
        if pattern.search(line):
            return f"{message}: {line}"
    return None


def _warning_from_line(line: str) -> str | None:
    warning_message = re.search(
        r"\bwarning_message\b\s*[:=]\s*['\"]?([^'\"]*)",
        line,
        re.IGNORECASE,
    )
    if warning_message:
        value = warning_message.group(1).strip()
        if value:
            return _strip_log_level(value)
        return None

    if re.search(r"\bwarning\b", line, re.IGNORECASE):
        return _strip_log_level(line)
    return None


def _strip_log_level(line: str) -> str:
    return re.sub(r"^\s*(?:warning|warn)\s*[:=-]\s*", "", line, flags=re.IGNORECASE).strip()


def _parse_time_seconds(text: str) -> int | None:
    for line in text.splitlines():
        if re.search(r"total print time|estimated printing time|total estimated time", line, re.IGNORECASE):
            parenthetical_seconds = re.search(
                r"\(([\d,]+)\s*s(?:ec(?:ond)?s?)?\)",
                line,
                re.IGNORECASE,
            )
            if parenthetical_seconds:
                return int(parenthetical_seconds.group(1).replace(",", ""))

    explicit = re.search(
        r"\b(?:total_print_time_seconds|estimated_time_seconds|time_seconds)\b\s*[:=]\s*([\d,]+)",
        text,
        re.IGNORECASE,
    )
    if explicit:
        return int(explicit.group(1).replace(",", ""))

    labels = (
        r"estimated printing time(?:\s*\([^)]+\))?",
        r"total estimated time",
        r"model printing time",
        r"total print time",
    )
    label_pattern = "|".join(labels)
    match = re.search(
        rf"(?:{label_pattern})[^\n\r\d]*(\d+\s*d\s*)?(\d+\s*h\s*)?(\d+\s*m\s*)?(\d+\s*s)",
        text,
        re.IGNORECASE,
    )
    if match:
        return _time_string_to_seconds("".join(part or "" for part in match.groups()))

    any_hms = re.search(
        r"\b(?:(\d+\s*d\s*)?(\d+\s*h\s*)?(\d+\s*m\s*)?(\d+\s*s))\b",
        text,
        re.IGNORECASE,
    )
    if any_hms:
        return _time_string_to_seconds("".join(part or "" for part in any_hms.groups()))

    return None


def _time_string_to_seconds(time_text: str) -> int:
    total = 0
    for value, unit in re.findall(r"(\d+)\s*([dhms])", time_text, re.IGNORECASE):
        amount = int(value)
        unit = unit.lower()
        if unit == "d":
            total += amount * 86400
        elif unit == "h":
            total += amount * 3600
        elif unit == "m":
            total += amount * 60
        elif unit == "s":
            total += amount
    return total


def _parse_filament_g(text: str) -> float | None:
    patterns = (
        r"total filament weight\s*\[g\]\s*[:=]\s*([\d.,]+)",
        r"filament(?:\s*[\u2014-]\s*weight|_used_g| weight).{0,80}?([\d.,]+)\s*g\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return _float_from_text(match.group(1))
    return None


def _parse_layer_count(text: str) -> int | None:
    patterns = (
        r"total layer (?:number|count)\s*[:=]\s*(\d+)",
        r"\blayer_count\b\s*[:=]\s*(\d+)",
        r"\blayer count\b[^\d\n\r]*(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _parse_cost(text: str) -> float | None:
    for line in text.splitlines():
        if re.search(r"filament cost|cost", line, re.IGNORECASE):
            dollar_values = re.findall(r"\$\s*([\d.,]+)", line)
            if dollar_values:
                return _float_from_text(dollar_values[-1])
            values = re.findall(r"[\d.,]+", line)
            if values:
                return _float_from_text(values[-1])
    return None


def _float_from_text(value: str) -> float:
    return float(value.replace(",", ""))


def _slice_result_payload(result: SliceResult) -> dict[str, Any]:
    return {
        "return_code": result.return_code,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "time_seconds": result.time_seconds,
        "filament_g": result.filament_g,
        "layer_count": result.layer_count,
        "cost": result.cost,
        "gcode_path": _path_to_text(result.gcode_path),
        "log_path": _path_to_text(result.log_path),
        "stderr_log_path": _path_to_text(result.stderr_log_path),
    }


def _slice_result_metrics(result: SliceResult) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "return_code": result.return_code,
        "warnings": result.warnings,
        "errors": result.errors,
    }
    for key in ("time_seconds", "filament_g", "layer_count", "cost"):
        value = getattr(result, key)
        if value is not None:
            metrics[key] = value
    return metrics


def _path_to_text(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _normalize_platform(platform: str) -> str:
    platform_text = platform.lower()
    if platform_text in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    if platform_text in {"win32", "cygwin", "msys", "nt", "windows"}:
        return "windows"
    return platform_text


def _cli_paths_from_configured_path(value: str, platform: str) -> tuple[Path, ...]:
    path = Path(value).expanduser()
    if platform == "macos" and path.suffix == ".app":
        return (path / "Contents" / "MacOS" / "BambuStudio",)
    return (path,)


def _path_candidates_from_env(env: Mapping[str, str]) -> tuple[Path, ...]:
    path_text = env.get("PATH", "")
    if not path_text:
        return ()
    paths: list[Path] = []
    for raw_dir in path_text.split(os.pathsep):
        if not raw_dir:
            continue
        directory = Path(raw_dir).expanduser()
        for executable_name in _PATH_EXECUTABLE_NAMES:
            paths.append(directory / executable_name)
    return tuple(paths)


def _macos_bambu_cli_candidates(env: Mapping[str, str]) -> tuple[Path, ...]:
    roots = [Path("/Applications")]
    home = env.get("HOME", "").strip()
    if home:
        roots.append(Path(home).expanduser() / "Applications")

    bundle_candidates = [
        root / bundle_name / "Contents" / "MacOS" / "BambuStudio"
        for root in roots
        for bundle_name in _MACOS_APP_BUNDLES
    ]
    return (
        *bundle_candidates,
        Path("/opt/homebrew/bin/bambu-studio"),
        Path("/usr/local/bin/bambu-studio"),
    )


def _windows_bambu_cli_candidates(env: Mapping[str, str]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        value = env.get(key, "").strip()
        if value:
            roots.append(Path(value))

    local_app_data = env.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        roots.append(Path(local_app_data) / "Programs")

    return tuple(
        root / directory_name / executable_name
        for root in roots
        for directory_name in _WINDOWS_INSTALL_DIRS
        for executable_name in _WINDOWS_EXECUTABLE_NAMES
    )


def _linux_bambu_cli_candidates(env: Mapping[str, str]) -> tuple[Path, ...]:
    candidates: list[Path] = [
        Path("/usr/bin/bambu-studio"),
        Path("/usr/local/bin/bambu-studio"),
        Path("/snap/bin/bambu-studio"),
        Path("/opt/BambuStudio/bambu-studio"),
        Path("/opt/BambuStudio/BambuStudio"),
        Path("/opt/bambu-studio/bambu-studio"),
    ]
    home = env.get("HOME", "").strip()
    if home:
        candidates.append(Path(home).expanduser() / ".local" / "bin" / "bambu-studio")
    return tuple(candidates)


def _path_exists(path: Path) -> bool:
    return path.exists()


def _dedupe_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)


def _missing_bambu_cli_message(candidates: Sequence[Path]) -> str:
    candidate_text = ", ".join(str(path) for path in candidates[:8])
    if len(candidates) > 8:
        candidate_text += f", ... ({len(candidates)} total)"
    elif not candidate_text:
        candidate_text = "none"

    return (
        "Bambu Studio CLI executable was not found. "
        f"Set {BAMBU_STUDIO_CLI_ENV} to the Bambu Studio executable "
        f"or install Bambu Studio. Checked: {candidate_text}"
    )


def _file_has_content(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _find_gcode_path(stdout: str, stderr: str, slice_dir: Path) -> Path | None:
    combined = "\n".join(part for part in (stdout, stderr) if part)
    match = re.search(
        r"(?:g-?code|gcode)[^:\n\r]*:\s*['\"]?([^'\"\n\r]+?\.gcode(?:\.3mf)?)['\"]?\s*$",
        combined,
        re.IGNORECASE | re.MULTILINE,
    )
    if match:
        path = Path(match.group(1).strip())
        return path if path.is_absolute() else slice_dir / path

    candidates = sorted(slice_dir.glob("*.gcode")) + sorted(slice_dir.glob("*.gcode.3mf"))
    return candidates[0] if candidates else None


def _warning_allowed(warning: str, allowed_warning_markers: Sequence[str]) -> bool:
    warning_lower = warning.lower()
    return any(marker.lower() in warning_lower for marker in allowed_warning_markers)


def _dedupe(items: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return tuple(unique)
