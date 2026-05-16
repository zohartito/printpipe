from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
FAILURE_TEMPLATE = TEMPLATE_DIR / "printpipe_failure.yml"
FEEDBACK_TEMPLATE = TEMPLATE_DIR / "beta_feedback.yml"


def _read_template(path: Path) -> str:
    assert path.exists(), f"missing GitHub issue template: {path}"
    return path.read_text(encoding="utf-8")


def _top_level_keys(content: str) -> set[str]:
    return {
        match.group("key")
        for match in re.finditer(r"^(?P<key>[a-zA-Z][\w-]*):", content, re.MULTILINE)
    }


def _body_field_ids(content: str) -> list[str]:
    ids: list[str] = []
    in_body = False

    for line in content.splitlines():
        if line == "body:":
            in_body = True
            continue
        if not in_body:
            continue

        match = re.match(r"^    id: (?P<id>[a-z0-9-]+)$", line)
        if match:
            ids.append(match.group("id"))

    return ids


def _required_ids(content: str) -> set[str]:
    required: set[str] = set()
    current_id: str | None = None

    for line in content.splitlines():
        id_match = re.match(r"^    id: (?P<id>[a-z0-9-]+)$", line)
        if id_match:
            current_id = id_match.group("id")
            continue
        if current_id and line == "      required: true":
            required.add(current_id)

    return required


def test_printpipe_failure_issue_template_captures_failed_run_context() -> None:
    content = _read_template(FAILURE_TEMPLATE)
    normalized = content.lower()

    assert {"name", "description", "title", "labels", "body"} <= _top_level_keys(
        content
    )
    assert _body_field_ids(content) == [
        "run-id",
        "command",
        "input-type",
        "printer",
        "material",
        "failed-stage",
        "artifacts-logs",
        "bambu-studio-warnings",
        "physical-print-status",
    ]
    assert set(_body_field_ids(content)) <= _required_ids(content)

    for expected in (
        "printpipe failed run",
        "run id",
        "command",
        "input type",
        "printer",
        "material",
        "failed stage",
        "artifacts",
        "logs",
        "bambu studio warnings",
        "physical print status",
        "mesh generation",
        "mesh repair",
        "slicing",
        "3mf bundle",
    ):
        assert expected in normalized


def test_beta_feedback_issue_template_captures_workflow_and_environment() -> None:
    content = _read_template(FEEDBACK_TEMPLATE)
    normalized = content.lower()

    assert {"name", "description", "title", "labels", "body"} <= _top_level_keys(
        content
    )
    assert _body_field_ids(content) == [
        "workflow-friction",
        "object-type",
        "os",
        "bambu-studio-version",
        "printer-material",
        "screenshots-artifacts",
    ]
    assert set(_body_field_ids(content)) <= _required_ids(content)

    for expected in (
        "beta feedback",
        "workflow friction",
        "object type",
        "os",
        "bambu studio version",
        "printer/material",
        "screenshots",
        "artifacts",
        "macos",
        "windows",
        "linux",
    ):
        assert expected in normalized
