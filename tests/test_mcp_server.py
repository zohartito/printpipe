"""Tests for the dependency-free MCP slicer-settings server."""

from __future__ import annotations

import json
import types
import zipfile

from printpipe import mcp_server
from printpipe.contracts import StageStatus


def test_initialize_reports_protocol_and_server_info():
    response = mcp_server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert response["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["name"] == "printpipe-slicer"
    assert "tools" in response["result"]["capabilities"]


def test_initialized_notification_returns_no_response():
    assert mcp_server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_exposes_all_tools():
    response = mcp_server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {
        "get_slice_settings",
        "list_slice_intents",
        "resolve_slice_intents",
        "slice_with_settings",
        "get_fabrication_report",
    }


def test_normalize_overrides_wraps_scalars_and_preserves_lists():
    normalized = mcp_server._normalize_overrides(
        {"wall_loops": 4, "enable_support": "1", "outer_wall_speed": ["200", "500"]}
    )
    assert normalized == {
        "wall_loops": ["4"],
        "enable_support": ["1"],
        "outer_wall_speed": ["200", "500"],
    }


def test_get_slice_settings_tool_returns_keyspace():
    response = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_slice_settings",
                "arguments": {"material": "Bambu PLA Basic", "group": "process"},
            },
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["material"] == "Bambu PLA Basic"
    assert "enable_support" in payload["process"]
    assert len(payload["process"]) > 100


def test_unknown_tool_returns_error():
    response = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32602


def test_coerce_bool_to_bambu_token():
    assert mcp_server._coerce(True) == "1"
    assert mcp_server._coerce(False) == "0"
    assert mcp_server._normalize_overrides({"enable_support": True}) == {"enable_support": ["1"]}


def _fake_result(tmp_path, *, gcode_name="plate_1.gcode.3mf", slice_ok=True):
    bundle_dir = tmp_path / "60_bundle"
    bundle_dir.mkdir()
    slice_dir = tmp_path / "70_slice"
    slice_dir.mkdir()
    bundle = bundle_dir / "existing_stl_x.3mf"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr(
            "Metadata/project_settings.config",
            json.dumps({"wall_loops": ["4"], "enable_support": ["1"]}),
        )
    (slice_dir / gcode_name).write_text("; gcode")
    layout = types.SimpleNamespace(root=str(tmp_path), bundle_dir=bundle_dir, slice_dir=slice_dir)
    status = StageStatus.SUCCEEDED if slice_ok else StageStatus.FAILED
    stages = (types.SimpleNamespace(stage="slice", status=status),)
    return types.SimpleNamespace(layout=layout, stages=stages)


def test_summarize_run_detects_gcode_3mf_and_reads_bundle(tmp_path):
    result = _fake_result(tmp_path, gcode_name="plate_1.gcode.3mf")
    summary = mcp_server._summarize_run(result, {"wall_loops": ["4"]}, run_slice=True)
    assert summary["bundle"].endswith("existing_stl_x.3mf")
    assert summary["gcode"].endswith("plate_1.gcode.3mf")  # the .gcode.3mf form is detected
    assert summary["sliced"] is True
    assert summary["overrides_applied_in_bundle"] == {"wall_loops": ["4"]}


def test_summarize_run_bundle_excludes_stray_gcode_3mf(tmp_path):
    result = _fake_result(tmp_path)
    (result.layout.bundle_dir / "plate_1.gcode.3mf").write_text("x")  # stray in bundle dir
    summary = mcp_server._summarize_run(result, {}, run_slice=True)
    assert summary["bundle"].endswith("existing_stl_x.3mf")


def test_summarize_run_sliced_false_when_receipt_failed(tmp_path):
    result = _fake_result(tmp_path, slice_ok=False)
    summary = mcp_server._summarize_run(result, {}, run_slice=True)
    assert summary["sliced"] is False


def test_slice_with_settings_routes_all_three_override_groups(monkeypatch, tmp_path):
    stl = tmp_path / "x.stl"
    stl.write_text("solid x\nendsolid x\n")
    captured: dict = {}

    def fake_pipeline(input_path, runs_dir, **kwargs):
        captured.update(kwargs)
        return _fake_result(tmp_path)

    monkeypatch.setattr(mcp_server, "run_existing_mesh_pipeline", fake_pipeline)
    mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "slice_with_settings",
                "arguments": {
                    "stl_path": str(stl),
                    "overrides": {"wall_loops": 4},
                    "filament_overrides": {"nozzle_temperature": "230"},
                    "printer_overrides": {"machine_max_acceleration_x": "10000"},
                    "run_slice": False,
                },
            },
        }
    )
    assert captured["process_overrides"] == {"wall_loops": ["4"]}
    assert captured["filament_overrides"] == {"nozzle_temperature": ["230"]}
    assert captured["printer_overrides"] == {"machine_max_acceleration_x": ["10000"]}


def test_slice_with_settings_rejects_missing_stl():
    response = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "slice_with_settings",
                "arguments": {"stl_path": "/tmp/definitely-not-here.stl"},
            },
        }
    )
    assert response["result"]["isError"] is True


def test_get_fabrication_report_returns_serialized_report(monkeypatch, tmp_path):
    from printpipe.fabrication.report import (
        Check,
        ExportResult,
        FabricationReport,
        PartResult,
        Status,
        Target,
    )

    fake = FabricationReport(
        units="mm",
        tolerance_mm=0.01,
        wall_thickness_mm=0.0,
        target=Target.PRINT,
        dimensions=[],
        parts=[PartResult("run_abc", 0, None, solid=True, valid=True)],
        valid_solids="1 / 1",
        printability=[Check("bed_fit", Status.PASS, "Fits the plate.")],
        orientation=None,
        packing=None,
        exports=ExportResult(),
        agent_summary="All available validation checks passed.",
    )
    monkeypatch.setattr(mcp_server, "build_fabrication_report", lambda run_root: fake)

    response = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_fabrication_report",
                "arguments": {"run_root": str(tmp_path)},
            },
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["units"] == "mm"
    assert payload["target"] == "print"
    assert payload["ready_to_print"] is True
    assert payload["parts"][0]["id"] == "run_abc"
    assert payload["printability"][0]["status"] == "pass"


def test_get_fabrication_report_rejects_missing_run_root():
    response = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "get_fabrication_report",
                "arguments": {"run_root": "/tmp/definitely-not-a-run-folder"},
            },
        }
    )
    assert response["result"]["isError"] is True
