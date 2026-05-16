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
    available_modules = {"trimesh"}
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
    assert report["summary"]["dependency_status_counts"]["ok"] == 2


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
        "summary": {"dependency_status_counts": {"ok": 1}},
    }

    text = render_environment_report(report)

    assert "PrintPipe Doctor" in text
    assert "Platform: windows (win32)" in text
    assert "ok: Python - No action needed." in text
    assert "Bambu Studio: 0 installed candidate(s) / 2 checked" in text
