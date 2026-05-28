"""Beta rule-update evidence packet helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RULE_UPDATE_SCHEMA_VERSION = 1
RULE_UPDATE_TYPES = ("material", "orientation", "repair")
REQUIRED_RULE_UPDATE_TYPES = RULE_UPDATE_TYPES
RULE_UPDATE_STATUSES = ("planned", "implemented", "verified", "reverted")

RULE_UPDATE_REQUIRED_HEADINGS = (
    "Run Context",
    "Rule Update",
    "Source",
    "Changed Files",
    "Verification",
    "Follow-Up",
)


@dataclass(frozen=True)
class RuleUpdate:
    """Structured evidence that a beta finding changed PrintPipe rules."""

    run_id: str
    rule_type: str
    status: str
    summary: str
    source: str
    changed_files: tuple[str, ...]
    tests: tuple[str, ...]
    notes: tuple[str, ...] = ()
    schema_version: int = field(default=RULE_UPDATE_SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "rule_type": self.rule_type,
            "status": self.status,
            "summary": self.summary,
            "source": self.source,
            "changed_files": list(self.changed_files),
            "tests": list(self.tests),
            "notes": list(self.notes),
        }


def build_rule_update(
    *,
    run_id: str,
    rule_type: str,
    status: str,
    summary: str,
    source: str,
    changed_files: Sequence[str],
    tests: Sequence[str],
    notes: Sequence[str] = (),
) -> RuleUpdate:
    """Build a normalized rule-update packet."""

    normalized_summary = summary.strip()
    if not normalized_summary:
        raise ValueError("rule update requires a summary")
    normalized_source = source.strip()
    if not normalized_source:
        raise ValueError("rule update requires a source")
    files = tuple(str(path).strip() for path in changed_files if str(path).strip())
    if not files:
        raise ValueError("rule update requires at least one changed file")
    test_commands = tuple(str(command).strip() for command in tests if str(command).strip())
    if status == "verified" and not test_commands:
        raise ValueError("verified rule updates require at least one test")
    return RuleUpdate(
        run_id=run_id,
        rule_type=_choice(rule_type, RULE_UPDATE_TYPES, "rule_type"),
        status=_choice(status, RULE_UPDATE_STATUSES, "status"),
        summary=normalized_summary,
        source=normalized_source,
        changed_files=files,
        tests=test_commands,
        notes=tuple(str(note) for note in notes),
    )


def render_rule_update_markdown(update: RuleUpdate) -> str:
    """Render a rule-update packet as Markdown."""

    changed_files = _list_lines(update.changed_files)
    tests = _list_lines(update.tests) or "- Not recorded"
    notes = _list_lines(update.notes) or "- None recorded"
    return f"""# PrintPipe Rule Update

## Run Context
- Run ID: {update.run_id}

## Rule Update
- Rule type: {update.rule_type}
- Status: {update.status}
- Summary: {update.summary}

## Source
- {update.source}

## Changed Files
{changed_files}

## Verification
{tests}

## Follow-Up
{notes}
"""


def parse_rule_update_sections(markdown: str) -> dict[str, str]:
    """Parse second-level Markdown headings into section bodies."""

    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for line in markdown.splitlines():
        heading = _second_level_heading(line)
        if heading is not None:
            current_heading = heading
            sections.setdefault(current_heading, [])
            continue
        if current_heading is not None:
            sections[current_heading].append(line)
    return {
        heading: "\n".join(lines).strip("\n")
        for heading, lines in sections.items()
    }


def missing_required_rule_update_headings(markdown: str) -> list[str]:
    """Return required rule-update headings absent from Markdown."""

    sections = parse_rule_update_sections(markdown)
    return [
        heading
        for heading in RULE_UPDATE_REQUIRED_HEADINGS
        if heading not in sections
    ]


def write_rule_update_files(
    *,
    run_root: str | Path,
    update: RuleUpdate,
    directory_name: str = "90_beta",
) -> dict[str, Any]:
    """Write rule-update JSON and Markdown into a run folder."""

    root = Path(run_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    output_dir = root / directory_name
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"rule_update_{update.rule_type}.json"
    markdown_path = output_dir / f"rule_update_{update.rule_type}.md"
    markdown = render_rule_update_markdown(update)
    json_path.write_text(
        json.dumps(update.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return {
        "directory": str(output_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "missing_required_headings": missing_required_rule_update_headings(markdown),
    }


def build_rule_update_status(
    runs_dir: str | Path,
    *,
    required_rule_types: Sequence[str] = REQUIRED_RULE_UPDATE_TYPES,
) -> dict[str, Any]:
    """Summarize material/orientation/repair rule-update packets across runs."""

    root = Path(runs_dir).expanduser().resolve()
    packets = _load_rule_update_packets(root)
    required = tuple(required_rule_types)
    rule_type_status = {
        rule_type: _rule_type_status(rule_type, packets)
        for rule_type in required
    }
    verified = [
        rule_type
        for rule_type, status in rule_type_status.items()
        if status["status"] == "verified"
    ]
    missing = [
        rule_type
        for rule_type, status in rule_type_status.items()
        if status["status"] == "missing"
    ]
    incomplete = [
        rule_type
        for rule_type, status in rule_type_status.items()
        if status["status"] not in {"verified"}
    ]
    if not packets:
        overall = "missing"
    elif not incomplete:
        overall = "passed"
    else:
        overall = "incomplete"
    return {
        "schema_version": RULE_UPDATE_SCHEMA_VERSION,
        "runs_dir": str(root),
        "overall_status": overall,
        "required_rule_types": list(required),
        "verified_rule_types": verified,
        "missing_rule_types": missing,
        "incomplete_rule_types": incomplete,
        "packet_count": len(packets),
        "rule_type_status": rule_type_status,
        "packets": packets,
    }


def render_rule_update_status(status: Mapping[str, Any]) -> str:
    """Render a human-readable rule-update status."""

    lines = [
        "PrintPipe Rule Update Status",
        f"runs dir: {status.get('runs_dir', 'unknown')}",
        f"overall: {status.get('overall_status', 'unknown')}",
        f"packets: {status.get('packet_count', 0)}",
        "Rule types:",
    ]
    rule_type_status = status.get("rule_type_status")
    if isinstance(rule_type_status, Mapping):
        for rule_type in sorted(rule_type_status):
            item = _dict(rule_type_status.get(rule_type))
            lines.append(
                f"- {rule_type}: {item.get('status', 'unknown')} "
                f"({item.get('packet_count', 0)} packet(s))"
            )
    return "\n".join(lines) + "\n"


def _rule_type_status(
    rule_type: str,
    packets: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    matches = [packet for packet in packets if packet["rule_type"] == rule_type]
    verified = [packet for packet in matches if packet["status"] == "verified"]
    implemented = [packet for packet in matches if packet["status"] == "implemented"]
    if verified:
        status = "verified"
    elif implemented:
        status = "implemented"
    elif matches:
        status = str(matches[-1].get("status") or "recorded")
    else:
        status = "missing"
    latest = matches[-1] if matches else {}
    return {
        "rule_type": rule_type,
        "status": status,
        "packet_count": len(matches),
        "verified_count": len(verified),
        "implemented_count": len(implemented),
        "latest_run_id": str(latest.get("run_id") or ""),
        "latest_summary": str(latest.get("summary") or ""),
    }


def _load_rule_update_packets(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    packets: list[dict[str, Any]] = []
    for packet_path in sorted(runs_dir.glob("*/90_beta/rule_update_*.json")):
        try:
            payload = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        packet = _packet_summary(payload, packet_path=packet_path)
        if packet["rule_type"] in RULE_UPDATE_TYPES:
            packets.append(packet)
    return packets


def _packet_summary(
    payload: Mapping[str, Any],
    *,
    packet_path: Path,
) -> dict[str, Any]:
    run_root = packet_path.parents[1]
    markdown_path = packet_path.with_suffix(".md")
    return {
        "run_id": str(payload.get("run_id") or run_root.name),
        "run_root": str(run_root),
        "json_path": str(packet_path),
        "markdown_path": str(markdown_path) if markdown_path.exists() else "",
        "rule_type": str(payload.get("rule_type") or ""),
        "status": str(payload.get("status") or ""),
        "summary": str(payload.get("summary") or ""),
        "source": str(payload.get("source") or ""),
        "changed_file_count": len(_list(payload.get("changed_files"))),
        "test_count": len(_list(payload.get("tests"))),
    }


def _choice(value: str, choices: Sequence[str], field_name: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in choices:
        raise ValueError(
            f"{field_name} must be one of {', '.join(choices)}; got {value!r}"
        )
    return normalized


def _list_lines(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _second_level_heading(line: str) -> str | None:
    if not line.startswith("## "):
        return None
    return line[3:].strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


__all__ = [
    "REQUIRED_RULE_UPDATE_TYPES",
    "RULE_UPDATE_REQUIRED_HEADINGS",
    "RULE_UPDATE_SCHEMA_VERSION",
    "RULE_UPDATE_STATUSES",
    "RULE_UPDATE_TYPES",
    "RuleUpdate",
    "build_rule_update",
    "build_rule_update_status",
    "missing_required_rule_update_headings",
    "parse_rule_update_sections",
    "render_rule_update_markdown",
    "render_rule_update_status",
    "write_rule_update_files",
]
