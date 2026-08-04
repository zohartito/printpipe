from __future__ import annotations

import re
from pathlib import Path


def test_github_actions_are_absent_or_immutably_pinned() -> None:
    """Prevent a future credentialed workflow from reintroducing mutable action tags."""

    workflow_dir = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    for workflow in workflow_dir.glob("*.y*ml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "uses:" not in line:
                continue
            reference = line.split("uses:", 1)[1].strip()
            assert re.search(r"@[0-9a-f]{40}(?:\s|$)", reference), (
                f"{workflow}: GitHub Actions must use a full immutable commit SHA"
            )


def test_security_hardening_doc_records_p3_execution_boundaries() -> None:
    doc = Path(__file__).resolve().parents[1] / "docs" / "SECURITY_HARDENING.md"
    text = doc.read_text(encoding="utf-8")

    assert "PRINTPIPE_TRUST_PROJECT_MEDIA_COMMAND" in text
    assert "run-regressions" in text
    assert "full commit SHA" in text


def test_current_docs_label_retired_regression_manifest_autodiscovery_as_historical() -> None:
    root = Path(__file__).resolve().parents[1]
    roadmap = (root / "docs" / "APP_ROADMAP.md").read_text(encoding="utf-8")
    waves = (root / "docs" / "AGENT_WAVES.md").read_text(encoding="utf-8")

    assert "Historical (superseded by PP-P3-05)" in roadmap
    assert "explicitly supplies `--regression-manifest`" in roadmap
    assert "historical; superseded by PP-P3-05" in waves
    assert "manifest-free" in roadmap
    assert "accepted but ignored" in waves
    assert "option is accepted only for\ncompatibility and ignored" in (
        root / "docs" / "SECURITY_HARDENING.md"
    ).read_text(encoding="utf-8")
