from __future__ import annotations

import json
from pathlib import Path

from printpipe.env.bambu_profiles import (
    build_bambu_profile_detection_report,
    default_bambu_user_base_paths,
    discover_bambu_user_profile_candidates,
)


def test_default_base_paths_include_macos_bambu_studio_user_root(tmp_path: Path):
    home = tmp_path / "zohar-home"

    assert default_bambu_user_base_paths(platform="darwin", home=home, env={}) == (
        home / "Library" / "Application Support" / "BambuStudio" / "user",
    )


def test_default_base_paths_include_windows_roaming_and_local_user_roots(
    tmp_path: Path,
):
    roaming = tmp_path / "AppData" / "Roaming"
    local = tmp_path / "AppData" / "Local"

    assert default_bambu_user_base_paths(
        platform="win32",
        env={
            "APPDATA": str(roaming),
            "LOCALAPPDATA": str(local),
        },
    ) == (
        roaming / "BambuStudio" / "user",
        local / "BambuStudio" / "user",
    )


def test_discover_candidates_detects_user_ids_and_profile_subfolders(
    tmp_path: Path,
):
    base = tmp_path / "BambuStudio" / "user"
    cloud_user = base / "123456789012345678"
    local_user = base / "local"
    (cloud_user / "filament").mkdir(parents=True)
    (cloud_user / "process").mkdir()
    (cloud_user / "machine").mkdir()
    (local_user / "process").mkdir(parents=True)
    (base / ".DS_Store").write_text("not a directory", encoding="utf-8")

    (cloud_user / "filament" / "SUNLU TPU 90A.json").write_text("{}", encoding="utf-8")
    (cloud_user / "filament" / "notes.txt").write_text("skip", encoding="utf-8")
    (cloud_user / "machine" / "Bambu Lab P2S.json").write_text("{}", encoding="utf-8")
    (local_user / "process" / "0.20mm Slipper.json").write_text("{}", encoding="utf-8")

    candidates = discover_bambu_user_profile_candidates(base_paths=[base])

    assert [candidate.user_id for candidate in candidates] == [
        "123456789012345678",
        "local",
    ]
    assert candidates[0].profile_kinds() == ("filament", "process", "printer")
    assert candidates[1].profile_kinds() == ("process",)

    cloud_report = candidates[0].as_report()
    assert cloud_report["path"] == str(cloud_user)
    assert cloud_report["subfolders"]["filament"] == [
        {
            "kind": "filament",
            "folder_name": "filament",
            "path": str(cloud_user / "filament"),
            "json_file_count": 1,
        }
    ]
    assert cloud_report["subfolders"]["printer"] == [
        {
            "kind": "printer",
            "folder_name": "machine",
            "path": str(cloud_user / "machine"),
            "json_file_count": 1,
        }
    ]


def test_build_report_is_json_friendly_and_includes_base_path_status(
    tmp_path: Path,
):
    base = tmp_path / "Library" / "Application Support" / "BambuStudio" / "user"
    missing_base = tmp_path / "missing" / "BambuStudio" / "user"
    user_dir = base / "999999"
    (user_dir / "filament").mkdir(parents=True)

    report = build_bambu_profile_detection_report(base_paths=[base, missing_base])

    json.dumps(report)
    assert report["candidate_count"] == 1
    assert report["base_paths"] == [
        {
            "path": str(base),
            "exists": True,
            "is_dir": True,
            "user_ids": ["999999"],
        },
        {
            "path": str(missing_base),
            "exists": False,
            "is_dir": False,
            "user_ids": [],
        },
    ]
    assert report["candidates"][0]["user_id"] == "999999"
