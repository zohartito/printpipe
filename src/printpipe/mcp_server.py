"""Dependency-free MCP server exposing PrintPipe's Bambu slicer settings to any AI agent.

This is the programmatic "API to the slicer": Bambu Studio has no live GUI API, but it
slices headlessly from a flat settings keyspace (``Metadata/project_settings.config``).
PrintPipe owns that keyspace, so this server lets an agent:

  * get_slice_settings   - read the FULL keyspace (process / filament / printer) + values.
  * slice_with_settings  - change ANY of those settings and slice an STL with them applied.

Transport: MCP stdio (newline-delimited JSON-RPC 2.0 on stdin/stdout; logs go to stderr).
No third-party packages required, so it runs on this Python 3.14 venv without the `mcp` SDK.

Run directly:           .venv/bin/python -m printpipe.mcp_server
Register with Claude:   claude mcp add printpipe-slicer -- /abs/path/.venv/bin/python -m printpipe.mcp_server
"""

from __future__ import annotations

import json
import sys
import traceback
import zipfile
from pathlib import Path
from typing import Any

from printpipe.contracts import StageStatus
from printpipe.fabrication.runs import build_fabrication_report
from printpipe.fabrication.serialize import to_dict as fabrication_report_to_dict
from printpipe.pipeline import (
    PipelineError,
    resolve_slice_settings,
    run_existing_mesh_pipeline,
)
from printpipe.slice_intents import list_intents, resolve_intents

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "printpipe-slicer", "version": "0.1.0"}

TOOLS = [
    {
        "name": "get_slice_settings",
        "description": (
            "View the full Bambu slicer setting keyspace for a material — every "
            "process, filament, and printer setting and its current value (quality, "
            "layer height, line width, wall loops, infill, speeds, supports, etc.). "
            "Use this to discover which keys exist before changing any with "
            "slice_with_settings."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "material": {
                    "type": "string",
                    "description": "Filament/material label, e.g. 'Bambu PLA Basic'.",
                    "default": "Generic PLA",
                },
                "group": {
                    "type": "string",
                    "enum": ["process", "filament", "printer", "all"],
                    "description": "Which setting group to return (default 'all').",
                    "default": "all",
                },
            },
        },
    },
    {
        "name": "list_slice_intents",
        "description": (
            "List the named natural-language slicing intents (e.g. 'stronger', "
            "'draft', 'needs_supports') and the exact Bambu process overrides each "
            "one applies. Use this to map a user's plain-English request to one or "
            "more intent names, then call resolve_slice_intents."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_slice_intents",
        "description": (
            "Translate one or more intent names into a merged, validated map of "
            "Bambu process overrides for a material — with before->after changes, "
            "conflicts (when two intents fight over the same key), and any unknown "
            "intent names. Returns an 'overrides' dict ready to pass straight to "
            "slice_with_settings. Does NOT slice."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Intent names from list_slice_intents, applied in order "
                        "(later intents win key conflicts)."
                    ),
                },
                "material": {
                    "type": "string",
                    "description": "Filament/material label, e.g. 'Bambu PLA Basic'.",
                    "default": "Generic PLA",
                },
            },
            "required": ["intents"],
        },
    },
    {
        "name": "slice_with_settings",
        "description": (
            "Slice an STL into a Bambu-ready .3mf, overriding ANY settings the agent "
            "chooses across all three groups: process (overrides), filament "
            "(filament_overrides — incl. nozzle/bed temps), and printer "
            "(printer_overrides). Values may be a string or a list of strings; scalars "
            "are wrapped to Bambu's list format automatically. Returns the run folder, "
            "the bundle path, the gcode path, and the settings as actually written into "
            "the bundle (read back for confirmation)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "stl_path": {
                    "type": "string",
                    "description": "Absolute path to an existing ASCII STL mesh to slice.",
                },
                "material": {
                    "type": "string",
                    "description": "Filament/material label, e.g. 'Bambu PLA Basic'.",
                    "default": "Generic PLA",
                },
                "overrides": {
                    "type": "object",
                    "description": (
                        "Map of PROCESS setting key -> value (string or list of strings). "
                        "Each value overrides that key in project_settings.config."
                    ),
                    "additionalProperties": True,
                    "default": {},
                },
                "filament_overrides": {
                    "type": "object",
                    "description": (
                        "Map of FILAMENT setting key -> value (e.g. nozzle_temperature, "
                        "hot_plate_temp and the other *_plate_temp bed temperatures, "
                        "filament_flow_ratio). Overrides the resolved filament profile."
                    ),
                    "additionalProperties": True,
                    "default": {},
                },
                "printer_overrides": {
                    "type": "object",
                    "description": (
                        "Map of PRINTER setting key -> value (e.g. machine_max_acceleration_x, "
                        "machine_max_speed_y). Overrides the resolved printer profile."
                    ),
                    "additionalProperties": True,
                    "default": {},
                },
                "run_slice": {
                    "type": "boolean",
                    "description": "Run the Bambu CLI slice gate (default true). False = bundle only.",
                    "default": True,
                },
                "runs_dir": {
                    "type": "string",
                    "description": "Directory where the run folder is created (default 'runs').",
                    "default": "runs",
                },
            },
            "required": ["stl_path"],
        },
    },
    {
        "name": "get_fabrication_report",
        "description": (
            "Return the fabrication-verification report for an existing run folder: "
            "per-part validity (manifold/solid), printability checks (bed fit, "
            "material/profile, support risk, slice success), dimension provenance, and "
            "the overall ready_to_print verdict. Read-only — it reads the run's "
            "already-written JSON and runs no pipeline or geometry. Pass the run_root "
            "directory produced by a prior slice/run."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_root": {
                    "type": "string",
                    "description": "Absolute path to an existing run folder (the run_root directory).",
                },
            },
            "required": ["run_root"],
        },
    },
]


def _coerce(value: Any) -> str:
    """Coerce a single override value to a Bambu config token.

    JSON booleans become "1"/"0" (Bambu's on/off encoding) rather than the Python
    reprs "True"/"False", which Bambu would not understand.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _normalize_overrides(overrides: dict[str, Any]) -> dict[str, list[str]]:
    """Coerce override values into Bambu's list-of-strings format."""
    normalized: dict[str, list[str]] = {}
    for key, value in overrides.items():
        items = value if isinstance(value, list) else [value]
        normalized[key] = [_coerce(item) for item in items]
    return normalized


def _bundle_path_from_result(result: Any) -> Path | None:
    """The project bundle the pipeline wrote — read from the run's bundle dir.

    Only the project ``.3mf`` lives in ``bundle_dir``; the sliced ``*.gcode.3mf`` lives
    separately in the slice dir, so this can never pick up the wrong archive.
    """
    bundle_dir = Path(result.layout.bundle_dir)
    bundles = [p for p in sorted(bundle_dir.glob("*.3mf")) if not p.name.endswith(".gcode.3mf")]
    return bundles[-1] if bundles else None


def _slice_gcode_path(result: Any) -> Path | None:
    """The sliced toolpath, matching both ``*.gcode`` and ``*.gcode.3mf`` (as slicer.py does)."""
    slice_dir = Path(result.layout.slice_dir)
    outputs = sorted(slice_dir.glob("*.gcode")) + sorted(slice_dir.glob("*.gcode.3mf"))
    return outputs[-1] if outputs else None


def _slice_succeeded(result: Any) -> bool:
    """Truth from the slice StageReceipt, not from a filesystem guess."""
    for stage in result.stages:
        if stage.stage == "slice":
            return stage.status == StageStatus.SUCCEEDED
    return False


def _summarize_run(result: Any, overrides: dict[str, list[str]], run_slice: bool) -> dict[str, Any]:
    """Build the tool response from a PipelineResult (used on success and on slice failure)."""
    bundle = _bundle_path_from_result(result)
    applied: dict[str, Any] = {}
    if bundle is not None:
        with zipfile.ZipFile(bundle) as archive:
            config = json.loads(archive.read("Metadata/project_settings.config"))
        applied = {key: config.get(key) for key in overrides}
    gcode = _slice_gcode_path(result) if run_slice else None
    # Requested overrides whose written value differs from the request — e.g. the
    # reserved profile-id keys (printable_height, nozzle_diameter, *_settings_id)
    # that build_project_settings_config re-stamps from the profile after merging.
    # Surfaced so the agent is never falsely told a dropped override was applied.
    not_applied = {
        key: {"requested": overrides[key], "in_bundle": applied.get(key)}
        for key in overrides
        if bundle is not None and applied.get(key) != overrides[key]
    }
    return {
        "run_root": str(result.layout.root),
        "bundle": str(bundle) if bundle is not None else None,
        "gcode": str(gcode) if gcode is not None else None,
        "sliced": _slice_succeeded(result) if run_slice else False,
        "overrides_requested": overrides,
        "overrides_applied_in_bundle": applied,
        "overrides_not_applied": not_applied,
    }


def _tool_get_slice_settings(arguments: dict[str, Any]) -> dict[str, Any]:
    material = arguments.get("material", "Generic PLA")
    group = arguments.get("group", "all")
    resolved = resolve_slice_settings(material)
    if group == "all":
        return resolved
    return {
        "material": resolved["material"],
        "profile_ids": resolved["profile_ids"],
        group: resolved[group],
    }


def _tool_list_slice_intents(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"intents": list_intents()}


def _tool_resolve_slice_intents(arguments: dict[str, Any]) -> dict[str, Any]:
    intents = arguments.get("intents") or []
    if not isinstance(intents, list):
        raise ValueError("intents must be a list of intent names")
    material = arguments.get("material", "Generic PLA")
    return resolve_intents(intents, material=material)


def _tool_get_fabrication_report(arguments: dict[str, Any]) -> dict[str, Any]:
    run_root = Path(arguments["run_root"]).expanduser()
    if not run_root.exists():
        raise ValueError(f"run_root does not exist: {run_root}")
    return fabrication_report_to_dict(build_fabrication_report(run_root))


def _tool_slice_with_settings(arguments: dict[str, Any]) -> dict[str, Any]:
    stl_path = Path(arguments["stl_path"]).expanduser()
    if not stl_path.exists():
        raise ValueError(f"stl_path does not exist: {stl_path}")
    material = arguments.get("material", "Generic PLA")
    runs_dir = Path(arguments.get("runs_dir", "runs")).expanduser()
    run_slice = bool(arguments.get("run_slice", True))
    process_overrides = _normalize_overrides(arguments.get("overrides", {}) or {})
    filament_overrides = _normalize_overrides(arguments.get("filament_overrides", {}) or {})
    printer_overrides = _normalize_overrides(arguments.get("printer_overrides", {}) or {})

    # Flag override keys not part of their resolved keyspace group (likely typos).
    # They are still applied (the keyspace is open by design), but surfaced so the agent knows.
    keyspace = resolve_slice_settings(material)
    unknown_keys = sorted(
        [key for key in process_overrides if key not in keyspace["process"]]
        + [key for key in filament_overrides if key not in keyspace["filament"]]
        + [key for key in printer_overrides if key not in keyspace["printer"]]
    )
    applied_keys = {**process_overrides, **filament_overrides, **printer_overrides}

    try:
        result = run_existing_mesh_pipeline(
            stl_path,
            runs_dir,
            material=material,
            run_slice=run_slice,
            process_overrides=process_overrides or None,
            filament_overrides=filament_overrides or None,
            printer_overrides=printer_overrides or None,
        )
    except PipelineError as exc:
        # The bundle was written before the slice gate failed - still surface it.
        summary = _summarize_run(exc.result, applied_keys, run_slice)
        summary["sliced"] = False
        summary["error"] = str(exc)
        summary["unknown_override_keys"] = unknown_keys
        return summary

    summary = _summarize_run(result, applied_keys, run_slice)
    summary["unknown_override_keys"] = unknown_keys
    return summary


DISPATCH = {
    "get_slice_settings": _tool_get_slice_settings,
    "list_slice_intents": _tool_list_slice_intents,
    "resolve_slice_intents": _tool_resolve_slice_intents,
    "get_fabrication_report": _tool_get_fabrication_report,
    "slice_with_settings": _tool_slice_with_settings,
}


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message; return a response dict, or None for notifications."""
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = DISPATCH.get(name)
        if handler is None:
            return _error(request_id, -32602, f"unknown tool: {name}")
        try:
            payload = handler(arguments)
            text = json.dumps(payload, indent=2, sort_keys=True)
            return _result(request_id, {"content": [{"type": "text", "text": text}]})
        except (PipelineError, ValueError, KeyError) as exc:
            return _result(
                request_id,
                {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True},
            )

    if request_id is None:
        return None
    return _error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            response = handle_request(message)
        except Exception:  # noqa: BLE001 - never let one bad call kill the server
            traceback.print_exc(file=sys.stderr)
            response = _error(message.get("id"), -32603, "internal error")
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
