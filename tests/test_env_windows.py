from __future__ import annotations

import json
import subprocess

from printpipe.env.windows import (
    is_windows_platform,
    python_runtime_summary,
    windows_installer_signing_readiness,
    windows_appdata_candidates,
    windows_environment_report,
    windows_program_files_candidates,
)


def test_is_windows_platform_accepts_injected_platform_names():
    assert is_windows_platform("win32")
    assert is_windows_platform("Windows")
    assert is_windows_platform("WIN64")
    assert not is_windows_platform("darwin")
    assert not is_windows_platform("linux")


def test_windows_appdata_candidates_use_environment_roots_without_duplicates():
    env = {
        "APPDATA": r"C:\Users\zohar\AppData\Roaming",
        "LOCALAPPDATA": r"C:\Users\zohar\AppData\Local",
        "PROGRAMDATA": r"C:\ProgramData",
        "USERPROFILE": r"C:\Users\zohar",
    }

    candidates = windows_appdata_candidates(env)

    assert [(candidate.kind, candidate.path, candidate.source) for candidate in candidates] == [
        ("appdata_roaming", r"C:\Users\zohar\AppData\Roaming", "APPDATA"),
        ("appdata_local", r"C:\Users\zohar\AppData\Local", "LOCALAPPDATA"),
        ("program_data", r"C:\ProgramData", "PROGRAMDATA"),
    ]


def test_windows_appdata_candidates_fall_back_to_userprofile():
    candidates = windows_appdata_candidates({"USERPROFILE": r"C:\Users\zohar"})

    assert [(candidate.kind, candidate.path, candidate.source) for candidate in candidates] == [
        ("appdata_roaming", r"C:\Users\zohar\AppData\Roaming", "USERPROFILE"),
        ("appdata_local", r"C:\Users\zohar\AppData\Local", "USERPROFILE"),
    ]


def test_windows_program_files_candidates_use_case_insensitive_env_lookup_and_dedupe():
    env = {
        "ProgramFiles": r"C:\Program Files",
        "programfiles(x86)": r"C:\Program Files (x86)",
        "PROGRAMW6432": r"C:\Program Files",
    }

    candidates = windows_program_files_candidates(env)

    assert [(candidate.kind, candidate.path, candidate.source) for candidate in candidates] == [
        ("program_files", r"C:\Program Files", "ProgramFiles"),
        ("program_files_x86", r"C:\Program Files (x86)", "programfiles(x86)"),
    ]


def test_python_runtime_summary_accepts_injected_executable_and_version():
    summary = python_runtime_summary(
        executable=r"C:\Python312\python.exe",
        version_info=(3, 12, 4, "final", 0),
        implementation="CPython",
    )

    assert summary == {
        "executable": r"C:\Python312\python.exe",
        "implementation": "CPython",
        "version": "3.12.4",
        "version_info": {
            "major": 3,
            "minor": 12,
            "micro": 4,
            "releaselevel": "final",
            "serial": 0,
        },
    }


def test_windows_environment_report_is_json_friendly_and_uses_injections():
    env = {
        "APPDATA": r"C:\Users\zohar\AppData\Roaming",
        "LOCALAPPDATA": r"C:\Users\zohar\AppData\Local",
        "ProgramFiles": r"C:\Program Files",
    }
    existing_paths = {r"C:\Program Files"}

    report = windows_environment_report(
        env=env,
        platform_name="win32",
        executable=r"C:\Python312\python.exe",
        version_info=(3, 12, 4, "final", 0),
        implementation="CPython",
        path_exists=existing_paths.__contains__,
    )

    json.dumps(report)
    assert report["is_windows"] is True
    assert report["platform"] == "win32"
    assert report["python"]["version"] == "3.12.4"
    assert report["paths"]["appdata"] == [
        {
            "kind": "appdata_roaming",
            "path": r"C:\Users\zohar\AppData\Roaming",
            "source": "APPDATA",
            "exists": False,
        },
        {
            "kind": "appdata_local",
            "path": r"C:\Users\zohar\AppData\Local",
            "source": "LOCALAPPDATA",
            "exists": False,
        },
    ]
    assert report["paths"]["program_files"] == [
        {
            "kind": "program_files",
            "path": r"C:\Program Files",
            "source": "ProgramFiles",
            "exists": True,
        }
    ]


def test_windows_installer_signing_readiness_reports_missing_tools_and_certificates():
    summary = windows_installer_signing_readiness(which=lambda _name: None)
    data = summary.as_dict()

    assert data["status"] == "missing_tools"
    assert data["missing_tools"] == ["signtool", "powershell", "wix/iscc/makensis"]
    assert data["missing_identities"] == ["Code Signing Certificate"]
    assert data["tools"]["signtool"] == {"path": None, "available": False}
    assert data["installer_tool_available"] is False
    assert data["identities"]["code_signing_certificates"] == []


def test_windows_installer_signing_readiness_parses_code_signing_certificates():
    tool_paths = {
        "signtool": r"C:\Program Files (x86)\Windows Kits\10\bin\signtool.exe",
        "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "wix": r"C:\Program Files\WiX Toolset\bin\wix.exe",
    }

    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args == [
            tool_paths["powershell"],
            "-NoProfile",
            "-Command",
            (
                "Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert | "
                "Select-Object -ExpandProperty Subject"
            ),
        ]
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="CN=Zohar Tito Code Signing, O=PrintPipe\n",
            stderr="",
        )

    summary = windows_installer_signing_readiness(
        which=tool_paths.get,
        run_command=fake_run,
    )
    data = summary.as_dict()

    assert data["status"] == "ready"
    assert data["missing_tools"] == []
    assert data["missing_identities"] == []
    assert data["installer_tool_available"] is True
    assert data["identities"]["code_signing_certificates"] == [
        "CN=Zohar Tito Code Signing, O=PrintPipe"
    ]
