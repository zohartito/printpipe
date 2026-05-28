from __future__ import annotations

import importlib.machinery
import json
from pathlib import Path

from printpipe.env.doctor import (
    build_environment_report,
    normalize_platform,
    render_environment_report,
)


def test_normalize_platform_maps_common_python_platforms():
    assert normalize_platform("darwin") == "macos"
    assert normalize_platform("macOS") == "macos"
    assert normalize_platform("win32") == "windows"
    assert normalize_platform("linux") == "linux"


def test_environment_report_combines_dependencies_bambu_and_profile_detection(
    monkeypatch,
    tmp_path: Path,
):
    available_modules = {"trimesh", "networkx"}
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda module_name: (
            importlib.machinery.ModuleSpec(module_name, loader=None)
            if module_name in available_modules
            else None
        ),
    )
    studio_root = tmp_path / "Applications"
    (studio_root / "Bambu Studio.app").mkdir(parents=True)
    profile_base = tmp_path / "BambuStudio" / "user"
    (profile_base / "1676299444" / "filament").mkdir(parents=True)

    report = build_environment_report(
        platform_name="darwin",
        env={},
        bambu_studio_roots=[studio_root],
        profile_base_paths=[profile_base],
    )

    json.dumps(report)
    assert report["platform"] == {"raw": "darwin", "normalized": "macos"}
    assert report["bambu_studio"]["installed_count"] == 1
    assert report["bambu_profiles"]["candidate_count"] == 1
    assert report["summary"]["bambu_studio_found"] is True
    assert report["summary"]["bambu_profile_user_count"] == 1
    assert report["summary"]["dependency_status_counts"]["ok"] == 3


def test_environment_report_warns_about_unreadable_workspace_and_artifact_paths(
    monkeypatch,
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    artifact = tmp_path / "external" / "mesh.stl"
    workspace.mkdir()
    artifact.parent.mkdir()
    artifact.write_text("solid fake\nendsolid fake\n", encoding="utf-8")

    def fake_can_read(path: Path) -> bool:
        return path != artifact.resolve()

    monkeypatch.setattr("printpipe.env.doctor._can_read_path", fake_can_read)

    report = build_environment_report(
        platform_name="linux",
        env={},
        workspace_paths=[workspace],
        artifact_paths=[artifact],
    )

    checks = {check["id"]: check for check in report["filesystem"]["checks"]}
    assert checks["workspace:0"]["status"] == "ok"
    assert checks["artifact:0"]["status"] == "warning"
    assert checks["artifact:0"]["readable"] is False
    assert report["summary"]["filesystem_status_counts"]["warning"] == 1


def test_render_environment_report_is_concise_and_human_readable():
    report = {
        "platform": {"raw": "win32", "normalized": "windows"},
        "dependencies": [
            {
                "id": "python",
                "label": "Python",
                "status": "ok",
                "action": "No action needed.",
            },
        ],
        "bambu_studio": {"installed_count": 0, "candidate_count": 2},
        "bambu_profiles": {"candidate_count": 0},
        "filesystem": {
            "checks": [
                {
                    "status": "warning",
                    "label": "Artifact path",
                    "action": "Grant access.",
                }
            ]
        },
        "summary": {
            "dependency_status_counts": {"ok": 1},
            "filesystem_status_counts": {"warning": 1},
        },
        "system": {
            "signing": {
                "status": "missing_tools",
                "missing_tools": ["signtool"],
                "missing_identities": ["Code Signing Certificate"],
            }
        },
    }

    text = render_environment_report(report)

    assert "PrintPipe Doctor" in text
    assert "Platform: windows (win32)" in text
    assert "ok: Python - No action needed." in text
    assert "Bambu Studio: 0 installed candidate(s) / 2 checked" in text
    assert "Filesystem:" in text
    assert "warning: Artifact path - Grant access." in text
    assert "Windows installer signing: missing_tools" in text
    assert "Missing signing tools: signtool" in text
    assert "Missing signing identities: Code Signing Certificate" in text
