"""Inspection helpers for exported ComfyUI API workflows."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any


def inspect_comfyui_workflow(workflow_path: Path) -> dict[str, Any]:
    resolved = workflow_path.expanduser()
    workflow = _load_workflow(resolved)
    nodes = _workflow_nodes(workflow)
    save_glb_nodes = [
        node_id
        for node_id, node in nodes.items()
        if str(node.get("class_type", "")).lower() == "saveglb"
    ]
    image_paths: list[str] = []
    prompt_paths: list[str] = []
    seed_paths: list[str] = []
    for node_id, node in nodes.items():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for input_name, value in inputs.items():
            path = f"{node_id}.inputs.{input_name}"
            lowered = input_name.lower()
            if _is_image_patch_input(lowered, value):
                image_paths.append(path)
            if _is_prompt_patch_input(lowered, value):
                prompt_paths.append(path)
            if _is_seed_patch_input(lowered, value):
                seed_paths.append(path)

    warnings: list[str] = []
    if not save_glb_nodes:
        warnings.append("Workflow does not include a SaveGLB node.")
    if not image_paths and not prompt_paths:
        warnings.append("Workflow has no obvious image or prompt patch inputs.")

    suggested_params: dict[str, Any] = {"comfyui_workflow": str(resolved)}
    if image_paths:
        suggested_params["comfyui_image_paths"] = image_paths
    if prompt_paths:
        suggested_params["comfyui_prompt_paths"] = prompt_paths
    if seed_paths:
        suggested_params["comfyui_seed_paths"] = seed_paths
    if not image_paths and prompt_paths:
        suggested_params["comfyui_allow_no_source_patch"] = True

    status = "ready" if save_glb_nodes and (image_paths or prompt_paths) else "action_required"
    return {
        "schema_version": 1,
        "workflow_path": str(resolved),
        "status": status,
        "node_count": len(nodes),
        "has_save_glb": bool(save_glb_nodes),
        "save_glb_nodes": save_glb_nodes,
        "image_patch_candidates": image_paths,
        "prompt_patch_candidates": prompt_paths,
        "seed_patch_candidates": seed_paths,
        "suggested_params": suggested_params,
        "configure_command": _configure_command(suggested_params),
        "warnings": warnings,
    }


def render_comfyui_workflow_report(report: dict[str, Any]) -> str:
    lines = [
        f"ComfyUI workflow: {report['workflow_path']}",
        f"status: {report['status']}",
        f"nodes: {report['node_count']}",
        f"SaveGLB nodes: {', '.join(report['save_glb_nodes']) or 'missing'}",
        _render_list("image patch candidates", report["image_patch_candidates"]),
        _render_list("prompt patch candidates", report["prompt_patch_candidates"]),
        _render_list("seed patch candidates", report["seed_patch_candidates"]),
    ]
    warnings = report.get("warnings", [])
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "configure command:",
            str(report["configure_command"]),
        ]
    )
    return "\n".join(lines) + "\n"


def _load_workflow(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _workflow_nodes(workflow: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(workflow, dict):
        raise ValueError("ComfyUI workflow must be a JSON object.")
    nodes = workflow.get("prompt") if isinstance(workflow.get("prompt"), dict) else workflow
    if not isinstance(nodes, dict):
        raise ValueError("ComfyUI workflow must contain node objects.")
    result: dict[str, dict[str, Any]] = {}
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "class_type" in node:
            result[str(node_id)] = node
    if not result:
        raise ValueError("ComfyUI workflow did not contain any API nodes.")
    return result


def _is_image_patch_input(input_name: str, value: Any) -> bool:
    if "image" not in input_name:
        return False
    return isinstance(value, str) and not value.startswith(("http://", "https://"))


def _is_prompt_patch_input(input_name: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if "negative" in input_name:
        return False
    return input_name in {"prompt", "text"} or input_name.endswith("_prompt")


def _is_seed_patch_input(input_name: str, value: Any) -> bool:
    return "seed" in input_name and isinstance(value, int)


def _configure_command(params: dict[str, Any]) -> str:
    return (
        "printpipe media-meshgen-configure --command "
        '"python scripts/media_meshgen_adapter.py" --params-json '
        f"{shlex.quote(json.dumps(params, sort_keys=True))}"
    )


def _render_list(label: str, values: list[str]) -> str:
    return f"{label}: {', '.join(values) if values else 'none'}"
