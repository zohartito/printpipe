from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest


def load_macos_module():
    try:
        return importlib.import_module("printpipe.env.macos")
    except ModuleNotFoundError as exc:
        pytest.fail(f"missing macOS environment module: {exc}")


def test_is_macos_uses_platform_system(monkeypatch: pytest.MonkeyPatch):
    macos = load_macos_module()

    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    assert macos.is_macos() is True

    monkeypatch.setattr(macos.platform, "system", lambda: "Linux")
    assert macos.is_macos() is False


def test_architecture_summary_identifies_apple_silicon_and_intel(
    monkeypatch: pytest.MonkeyPatch,
):
    macos = load_macos_module()

    monkeypatch.setattr(macos.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(macos.platform, "processor", lambda: "arm")
    apple_silicon = macos.macos_architecture()

    assert apple_silicon.kind == "apple_silicon"
    assert apple_silicon.is_apple_silicon is True
    assert apple_silicon.is_intel is False
    assert apple_silicon.as_dict() == {
        "machine": "arm64",
        "processor": "arm",
        "kind": "apple_silicon",
        "is_apple_silicon": True,
        "is_intel": False,
    }

    monkeypatch.setattr(macos.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(macos.platform, "processor", lambda: "i386")
    intel = macos.macos_architecture()

    assert intel.kind == "intel"
    assert intel.is_apple_silicon is False
    assert intel.is_intel is True


def test_common_app_support_paths_are_pathlib_values(monkeypatch: pytest.MonkeyPatch):
    macos = load_macos_module()
    fake_home = Path("/Users/runner")

    monkeypatch.setattr(macos.Path, "home", lambda: fake_home)
    paths = macos.common_app_support_paths()

    assert paths.home == fake_home
    assert paths.user_application_support == (
        fake_home / "Library" / "Application Support"
    )
    assert paths.user_caches == fake_home / "Library" / "Caches"
    assert paths.user_logs == fake_home / "Library" / "Logs"
    assert paths.user_preferences == fake_home / "Library" / "Preferences"
    assert paths.local_applications == Path("/Applications")
    assert paths.system_application_support == Path("/Library/Application Support")

    assert paths.as_dict() == {
        "home": "/Users/runner",
        "user_application_support": "/Users/runner/Library/Application Support",
        "user_caches": "/Users/runner/Library/Caches",
        "user_logs": "/Users/runner/Library/Logs",
        "user_preferences": "/Users/runner/Library/Preferences",
        "local_applications": "/Applications",
        "system_application_support": "/Library/Application Support",
    }


def test_application_support_path_trims_app_name_and_rejects_blank():
    macos = load_macos_module()

    assert macos.application_support_path(
        " BambuStudio ",
        home=Path("/Users/runner"),
    ) == Path("/Users/runner/Library/Application Support/BambuStudio")

    with pytest.raises(ValueError, match="app_name"):
        macos.application_support_path("   ", home=Path("/Users/runner"))


def test_python_runtime_summary_is_json_friendly_and_copy_safe():
    macos = load_macos_module()

    summary = macos.python_runtime_summary()
    data = summary.as_dict()

    json.dumps(data)
    assert isinstance(data["executable"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["version_info"], list)
    assert len(data["version_info"]) == 5
    assert isinstance(data["is_virtualenv"], bool)

    data["version_info"].append("mutated")
    assert "mutated" not in summary.as_dict()["version_info"]


def test_macos_signing_readiness_reports_missing_tools_and_identities():
    macos = load_macos_module()

    summary = macos.macos_signing_readiness(which=lambda _name: None)
    data = summary.as_dict()

    assert data["status"] == "missing_tools"
    assert data["missing_tools"] == ["codesign", "productbuild", "security", "notarytool"]
    assert data["missing_identities"] == [
        "Developer ID Application",
        "Developer ID Installer",
    ]
    assert data["tools"]["codesign"] == {"path": None, "available": False}
    assert data["identities"]["developer_id_application"] == []


def test_macos_signing_readiness_parses_developer_id_identities():
    macos = load_macos_module()
    tool_paths = {
        "codesign": "/usr/bin/codesign",
        "productbuild": "/usr/bin/productbuild",
        "security": "/usr/bin/security",
        "xcrun": "/usr/bin/xcrun",
    }

    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["/usr/bin/xcrun", "--find", "notarytool"]:
            return subprocess.CompletedProcess(args, 0, stdout="/usr/bin/notarytool\n", stderr="")
        if args == ["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=(
                    '  1) ABCD "Developer ID Application: Zohar Tito (TEAMID)"\n'
                    '  2) EFGH "Developer ID Installer: Zohar Tito (TEAMID)"\n'
                    "     2 valid identities found\n"
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {args}")

    summary = macos.macos_signing_readiness(
        which=tool_paths.get,
        run_command=fake_run,
    )
    data = summary.as_dict()

    assert data["status"] == "ready"
    assert data["missing_tools"] == []
    assert data["missing_identities"] == []
    assert data["tools"]["notarytool"] == {
        "path": "/usr/bin/notarytool",
        "available": True,
    }
    assert data["identities"]["developer_id_application"] == [
        "Developer ID Application: Zohar Tito (TEAMID)"
    ]
    assert data["identities"]["developer_id_installer"] == [
        "Developer ID Installer: Zohar Tito (TEAMID)"
    ]


def test_macos_environment_report_is_json_friendly_and_copy_safe(
    monkeypatch: pytest.MonkeyPatch,
):
    macos = load_macos_module()
    fake_home = Path("/Users/runner")

    monkeypatch.setattr(macos.Path, "home", lambda: fake_home)
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(macos.platform, "release", lambda: "23.5.0")
    monkeypatch.setattr(macos.platform, "version", lambda: "Darwin Kernel Version")
    monkeypatch.setattr(macos.platform, "mac_ver", lambda: ("14.5", ("", "", ""), "arm64"))
    monkeypatch.setattr(macos.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(macos.platform, "processor", lambda: "arm")

    report = macos.macos_environment_report()

    json.dumps(report)
    assert report["platform"] == {
        "system": "Darwin",
        "is_macos": True,
        "release": "23.5.0",
        "version": "Darwin Kernel Version",
        "mac_ver": "14.5",
        "machine": "arm64",
        "processor": "arm",
        "architecture": {
            "machine": "arm64",
            "processor": "arm",
            "kind": "apple_silicon",
            "is_apple_silicon": True,
            "is_intel": False,
        },
    }
    assert report["paths"]["home"] == "/Users/runner"
    assert report["paths"]["user_application_support"].endswith(
        "/Library/Application Support"
    )
    assert report["python"]["executable"]

    report["paths"]["home"] = "mutated"
    assert macos.macos_environment_report()["paths"]["home"] == "/Users/runner"
