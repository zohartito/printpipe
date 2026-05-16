from __future__ import annotations

from pathlib import Path

from printpipe.env.bambu_studio import (
    detect_bambu_studio_candidates,
    macos_bambu_studio_candidates,
    windows_bambu_studio_candidates,
)


def test_macos_candidates_include_common_app_bundle_names_with_open_hints(tmp_path: Path):
    applications_root = tmp_path / "Applications"
    installed = applications_root / "Bambu Studio.app"
    installed.mkdir(parents=True)

    candidates = macos_bambu_studio_candidates(roots=[applications_root])

    assert candidates == [
        {
            "path": str(applications_root / "Bambu Studio.app"),
            "platform": "macos",
            "exists": True,
            "launch_hint": ["open", str(applications_root / "Bambu Studio.app")],
            "open_hint": [
                "open",
                "-a",
                str(applications_root / "Bambu Studio.app"),
                "<file.3mf>",
            ],
        },
        {
            "path": str(applications_root / "BambuStudio.app"),
            "platform": "macos",
            "exists": False,
            "launch_hint": ["open", str(applications_root / "BambuStudio.app")],
            "open_hint": [
                "open",
                "-a",
                str(applications_root / "BambuStudio.app"),
                "<file.3mf>",
            ],
        },
    ]


def test_macos_default_roots_can_use_injected_home(tmp_path: Path):
    system_applications = tmp_path / "System Applications"
    home = tmp_path / "home"

    candidates = macos_bambu_studio_candidates(
        roots=[system_applications],
        env={"HOME": str(home)},
        include_user_applications=True,
    )

    paths = [candidate["path"] for candidate in candidates]
    assert str(system_applications / "Bambu Studio.app") in paths
    assert str(home / "Applications" / "Bambu Studio.app") in paths


def test_windows_candidates_include_program_files_paths_with_launch_hints(tmp_path: Path):
    program_files = tmp_path / "Program Files"
    program_files_x86 = tmp_path / "Program Files (x86)"
    installed = program_files / "Bambu Studio" / "bambu-studio.exe"
    installed.parent.mkdir(parents=True)
    installed.write_text("exe placeholder", encoding="utf-8")

    candidates = windows_bambu_studio_candidates(
        env={
            "ProgramFiles": str(program_files),
            "ProgramFiles(x86)": str(program_files_x86),
        }
    )

    assert {
        "path": str(installed),
        "platform": "windows",
        "exists": True,
        "launch_hint": [str(installed)],
        "open_hint": [str(installed), "<file.3mf>"],
    } in candidates
    assert {
        "path": str(program_files_x86 / "Bambu Studio" / "bambu-studio.exe"),
        "platform": "windows",
        "exists": False,
        "launch_hint": [str(program_files_x86 / "Bambu Studio" / "bambu-studio.exe")],
        "open_hint": [
            str(program_files_x86 / "Bambu Studio" / "bambu-studio.exe"),
            "<file.3mf>",
        ],
    } in candidates


def test_detect_candidates_dispatches_by_platform_with_injected_roots(tmp_path: Path):
    mac_root = tmp_path / "Applications"
    win_root = tmp_path / "Program Files"

    mac_candidates = detect_bambu_studio_candidates(platform="darwin", roots=[mac_root])
    win_candidates = detect_bambu_studio_candidates(platform="win32", roots=[win_root])

    assert mac_candidates[0]["platform"] == "macos"
    assert mac_candidates[0]["path"] == str(mac_root / "Bambu Studio.app")
    assert win_candidates[0]["platform"] == "windows"
    assert win_candidates[0]["path"] == str(win_root / "Bambu Studio" / "bambu-studio.exe")
