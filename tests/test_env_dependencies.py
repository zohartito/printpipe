from __future__ import annotations

import importlib.machinery
import os
import sys
from pathlib import Path

from printpipe.env import (
    DependencyReport,
    check_dependency_preflight,
    check_python_version,
)
from printpipe.env.dependencies import check_executable, check_module_available


def test_python_version_reports_ok_for_supported_runtime():
    report = check_python_version((3, 11, 0, "final", 0))

    assert report.to_dict() == {
        "id": "python",
        "label": "Python",
        "status": "ok",
        "action": "No action needed.",
        "details": {
            "minimum": "3.11",
            "current": "3.11.0",
        },
    }


def test_python_version_reports_unsupported_for_old_runtime():
    report = check_python_version((3, 10, 12, "final", 0))

    assert report.status == "unsupported"
    assert report.details == {
        "minimum": "3.11",
        "current": "3.10.12",
    }
    assert "Install Python 3.11 or newer" in report.action


def test_module_check_uses_find_spec_without_importing_package(monkeypatch):
    calls: list[str] = []

    def fake_find_spec(module_name: str):
        calls.append(module_name)
        return importlib.machinery.ModuleSpec(module_name, loader=None)

    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)

    report = check_module_available(
        "trimesh",
        label="trimesh",
        purpose="mesh inspection and repair",
    )

    assert calls == ["trimesh"]
    assert report == DependencyReport(
        id="trimesh",
        label="trimesh",
        status="ok",
        action="No action needed.",
        details={"purpose": "mesh inspection and repair", "module": "trimesh"},
    )


def test_optional_module_missing_reports_action(monkeypatch):
    monkeypatch.setattr("importlib.util.find_spec", lambda module_name: None)

    report = check_module_available(
        "paho.mqtt.client",
        label="paho-mqtt",
        purpose="future printer status monitoring",
        install_hint="Install paho-mqtt to enable future printer status monitoring.",
    )

    assert report.to_dict() == {
        "id": "paho_mqtt",
        "label": "paho-mqtt",
        "status": "optional_missing",
        "action": "Install paho-mqtt to enable future printer status monitoring.",
        "details": {
            "purpose": "future printer status monitoring",
            "module": "paho.mqtt.client",
        },
    }


def test_optional_module_missing_parent_package_reports_action(monkeypatch):
    def raise_missing_parent(module_name: str):
        raise ModuleNotFoundError("No module named 'paho'")

    monkeypatch.setattr("importlib.util.find_spec", raise_missing_parent)

    report = check_module_available(
        "paho.mqtt.client",
        label="paho-mqtt",
        purpose="future printer status monitoring",
        install_hint="Install paho-mqtt to enable future printer status monitoring.",
    )

    assert report.status == "optional_missing"
    assert report.id == "paho_mqtt"


def test_executable_check_reports_ok_for_executable_path(tmp_path: Path):
    executable = tmp_path / "bambu-studio"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)

    report = check_executable(
        id="bambu_studio_cli",
        label="Bambu Studio CLI",
        path=executable,
        purpose="slicing 3MF bundles",
        missing_action="Set PRINTPIPE_BAMBU_STUDIO_CLI to the Bambu Studio executable.",
    )

    assert report.to_dict() == {
        "id": "bambu_studio_cli",
        "label": "Bambu Studio CLI",
        "status": "ok",
        "action": "No action needed.",
        "details": {
            "purpose": "slicing 3MF bundles",
            "path": str(executable),
        },
    }


def test_executable_check_reports_optional_missing_without_path():
    report = check_executable(
        id="blender",
        label="Blender",
        path=None,
        purpose="mesh conversion and repair workflows",
        missing_action="Set PRINTPIPE_BLENDER to the Blender executable.",
    )

    assert report.status == "optional_missing"
    assert report.details == {"purpose": "mesh conversion and repair workflows", "path": None}
    assert report.action == "Set PRINTPIPE_BLENDER to the Blender executable."


def test_executable_check_reports_missing_for_invalid_configured_path(tmp_path: Path):
    missing_path = tmp_path / "does-not-exist"

    report = check_executable(
        id="bambu_studio_cli",
        label="Bambu Studio CLI",
        path=missing_path,
        purpose="slicing 3MF bundles",
        missing_action="Set PRINTPIPE_BAMBU_STUDIO_CLI to the Bambu Studio executable.",
    )

    assert report.status == "missing"
    assert str(missing_path) in report.action
    assert report.details == {
        "purpose": "slicing 3MF bundles",
        "path": str(missing_path),
    }


def test_preflight_returns_json_friendly_launch_report(monkeypatch, tmp_path: Path):
    available_modules = {"trimesh", "networkx"}
    bambu = tmp_path / "bambu-studio"
    bambu.write_text("#!/bin/sh\n", encoding="utf-8")
    bambu.chmod(0o755)

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda module_name: (
            importlib.machinery.ModuleSpec(module_name, loader=None)
            if module_name in available_modules
            else None
        ),
    )

    reports = check_dependency_preflight(
        python_version=(sys.version_info.major, sys.version_info.minor, sys.version_info.micro),
        environ={
            "PRINTPIPE_BAMBU_STUDIO_CLI": str(bambu),
            "PRINTPIPE_BLENDER": "",
        },
    )

    assert [report["id"] for report in reports] == [
        "python",
        "trimesh",
        "networkx",
        "bambu_studio_cli",
        "blender",
        "paho_mqtt",
    ]
    assert all(isinstance(report, dict) for report in reports)
    assert {report["status"] for report in reports} == {"ok", "optional_missing"}
    assert reports[3]["details"]["path"] == str(bambu)


def test_preflight_reads_tool_paths_from_environment(monkeypatch, tmp_path: Path):
    blender = tmp_path / "blender"
    blender.write_text("#!/bin/sh\n", encoding="utf-8")
    blender.chmod(0o755)
    monkeypatch.setenv("PRINTPIPE_BAMBU_STUDIO_CLI", "")
    monkeypatch.setenv("PRINTPIPE_BLENDER", str(blender))
    monkeypatch.setattr("importlib.util.find_spec", lambda module_name: None)

    reports = check_dependency_preflight(environ=os.environ)
    by_id = {report["id"]: report for report in reports}

    assert by_id["bambu_studio_cli"]["status"] == "optional_missing"
    assert by_id["blender"]["status"] == "ok"
    assert by_id["blender"]["details"]["path"] == str(blender)
