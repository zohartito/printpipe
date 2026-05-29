"""Starter template for PrintPipe media meshgen command adapters."""

from __future__ import annotations

from pathlib import Path


MEDIA_MESHGEN_TEMPLATE_PRESETS = ("generic", "comfyui-api")


MEDIA_MESHGEN_COMMAND_TEMPLATE = """#!/usr/bin/env python3
\"\"\"PrintPipe media meshgen adapter template.

Fill in generate_mesh() with a real image/GIF/video-to-mesh call. PrintPipe calls
this script through PRINTPIPE_MEDIA_MESHGEN_COMMAND and expects it to write the
requested mesh to --output or print JSON with {"output_path": "..."}.
\"\"\"

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PrintPipe media meshgen adapter template."
    )
    parser.add_argument("--input-kind", required=True, choices=("image", "gif", "video"))
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--reference-image", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-format", required=True, choices=("stl", "glb", "obj"))
    parser.add_argument("--target-use", default="print")
    parser.add_argument("--quality", default="balanced")
    parser.add_argument("--prompt")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--params-json", type=Path)
    return parser


def generate_mesh(args: argparse.Namespace) -> None:
    \"\"\"Write args.output here, or replace this function with provider API calls.\"\"\"
    raise NotImplementedError(
        "Replace generate_mesh() with a real image/GIF/video-to-mesh call."
    )


def main() -> int:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        generate_mesh(args)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not args.output.exists():
        print(f"adapter did not write expected mesh: {args.output}", file=sys.stderr)
        return 2

    print(json.dumps({"output_path": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


COMFYUI_API_MEDIA_MESHGEN_COMMAND_TEMPLATE = """#!/usr/bin/env python3
\"\"\"ComfyUI API media meshgen adapter preset for PrintPipe.

This preset is intentionally honest: it is a bridge to a real ComfyUI workflow,
not a bundled model. Export a 3D workflow from ComfyUI with File > Export (API),
include a SaveGLB node, then point PRINTPIPE_COMFYUI_WORKFLOW at that JSON.
PrintPipe calls this script through PRINTPIPE_MEDIA_MESHGEN_COMMAND.
\"\"\"

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"
# ComfyUI API surfaces used by this preset: "/prompt", "/history/", "/view?".


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PrintPipe ComfyUI API media meshgen adapter preset."
    )
    parser.add_argument("--input-kind", required=True, choices=("image", "gif", "video"))
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--reference-image", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-format", required=True, choices=("glb", "stl", "obj"))
    parser.add_argument("--target-use", default="print")
    parser.add_argument("--quality", default="balanced")
    parser.add_argument("--prompt")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--params-json")
    return parser


def _load_params(args: argparse.Namespace) -> dict[str, Any]:
    if not args.params_json:
        return {}
    stripped = args.params_json.strip()
    if stripped.startswith("{"):
        raw = stripped
    else:
        candidate = Path(args.params_json).expanduser()
        raw = candidate.read_text(encoding="utf-8") if candidate.exists() else args.params_json
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("--params-json must be a JSON object or path to one")
    return payload


def _env(name: str, default: str = "", *, params: dict[str, Any] | None = None, key: str | None = None) -> str:
    configured = os.environ.get(name, "").strip()
    if configured:
        return configured
    if params is not None:
        value = params.get(key or name)
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, bool):
            return "1" if value else "0"
        if value is not None:
            return str(value).strip()
    return os.environ.get(name, default).strip()


def _env_paths(name: str, *, params: dict[str, Any], key: str) -> tuple[str, ...]:
    value = params.get(key)
    if isinstance(value, list):
        return tuple(str(part).strip() for part in value if str(part).strip())
    raw = _env(name, params=params, key=key)
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _comfy_url(params: dict[str, Any]) -> str:
    return _env(
        "PRINTPIPE_COMFYUI_URL",
        DEFAULT_COMFYUI_URL,
        params=params,
        key="comfyui_url",
    ).rstrip("/")


def _load_workflow(params: dict[str, Any]) -> dict[str, Any]:
    workflow_path = _env(
        "PRINTPIPE_COMFYUI_WORKFLOW",
        params=params,
        key="comfyui_workflow",
    )
    if not workflow_path:
        raise RuntimeError(
            "PRINTPIPE_COMFYUI_WORKFLOW is required; export a ComfyUI API workflow "
            "with a SaveGLB node, then point this variable at the JSON file."
        )
    path = Path(workflow_path).expanduser()
    if not path.exists():
        raise RuntimeError(f"PRINTPIPE_COMFYUI_WORKFLOW does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _patch_path(document: dict[str, Any], dotted_path: str, value: Any) -> None:
    current: Any = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise RuntimeError(f"workflow patch path does not exist: {dotted_path}")
        current = current[part]
    if not isinstance(current, dict):
        raise RuntimeError(f"workflow patch parent is not an object: {dotted_path}")
    current[parts[-1]] = value


def _upload_reference(comfy_url: str, source_path: Path) -> str:
    if not source_path.exists():
        raise RuntimeError(f"source reference does not exist: {source_path}")
    boundary = f"----PrintPipeComfyUI{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    payload = source_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\\r\\n".encode("utf-8"),
            (
                'Content-Disposition: form-data; name="image"; '
                f'filename="{source_path.name}"\\r\\n'
            ).encode("utf-8"),
            f"Content-Type: {mime_type}\\r\\n\\r\\n".encode("utf-8"),
            payload,
            f"\\r\\n--{boundary}--\\r\\n".encode("utf-8"),
        ]
    )
    request = urllib.request.Request(
        f"{comfy_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request) as response:
        uploaded = json.loads(response.read().decode("utf-8"))
    name = uploaded.get("name") or uploaded.get("filename")
    if not name:
        raise RuntimeError(f"ComfyUI upload response did not include a filename: {uploaded}")
    subfolder = uploaded.get("subfolder") or ""
    if subfolder:
        return f"{subfolder}/{name}"
    return str(name)


def _queue_prompt(comfy_url: str, workflow: dict[str, Any]) -> str:
    prompt_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "prompt": workflow,
        "client_id": str(uuid.uuid4()),
        "prompt_id": prompt_id,
    }
    api_key = _env("PRINTPIPE_COMFYUI_API_KEY")
    if api_key:
        payload["extra_data"] = {"api_key_comfy_org": api_key}
    request = urllib.request.Request(
        f"{comfy_url}/prompt",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request).read()
    return prompt_id


def _history(comfy_url: str, prompt_id: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}") as response:
        payload = json.loads(response.read().decode("utf-8"))
    if prompt_id not in payload:
        raise KeyError(prompt_id)
    return payload[prompt_id]


def _wait_for_history(comfy_url: str, prompt_id: str, params: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = int(
        _env(
            "PRINTPIPE_COMFYUI_TIMEOUT_SECONDS",
            "900",
            params=params,
            key="comfyui_timeout_seconds",
        )
    )
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _history(comfy_url, prompt_id)
        except (KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"ComfyUI prompt did not finish before timeout: {last_error}")


def _first_3d_output(history: dict[str, Any], output_format: str) -> dict[str, str]:
    outputs = history.get("outputs", {})
    for node_output in outputs.values():
        for key in ("3d", "files", "models"):
            for item in node_output.get(key, []) if isinstance(node_output, dict) else []:
                filename = str(item.get("filename", ""))
                if filename.lower().endswith(f".{output_format}"):
                    return {
                        "filename": filename,
                        "subfolder": str(item.get("subfolder", "")),
                        "type": str(item.get("type", "output")),
                    }
    raise RuntimeError(
        "ComfyUI history did not include a matching 3D output. Make sure the "
        "workflow ends in SaveGLB and request --output-format glb."
    )


def _download_view(comfy_url: str, file_info: dict[str, str], output_path: Path) -> None:
    query = urllib.parse.urlencode(
        {
            "filename": file_info["filename"],
            "subfolder": file_info["subfolder"],
            "type": file_info["type"],
        }
    )
    with urllib.request.urlopen(f"{comfy_url}/view?{query}") as response:
        output_path.write_bytes(response.read())


def generate_mesh(args: argparse.Namespace) -> None:
    if args.output_format != "glb":
        raise RuntimeError(
            "The ComfyUI API preset expects a SaveGLB workflow; request "
            "--output-format glb or add a separate conversion step."
        )

    params = _load_params(args)
    workflow = _load_workflow(params)
    if args.prompt:
        for patch_path in _env_paths(
            "PRINTPIPE_COMFYUI_PROMPT_PATHS",
            params=params,
            key="comfyui_prompt_paths",
        ):
            _patch_path(workflow, patch_path, args.prompt)
    if args.seed is not None:
        for patch_path in _env_paths(
            "PRINTPIPE_COMFYUI_SEED_PATHS",
            params=params,
            key="comfyui_seed_paths",
        ):
            _patch_path(workflow, patch_path, args.seed)

    comfy_url = _comfy_url(params)
    image_paths = _env_paths(
        "PRINTPIPE_COMFYUI_IMAGE_PATHS",
        params=params,
        key="comfyui_image_paths",
    )
    if image_paths:
        uploaded_name = _upload_reference(comfy_url, Path(args.source[0]))
        for patch_path in image_paths:
            _patch_path(workflow, patch_path, uploaded_name)
    elif (
        _env(
            "PRINTPIPE_COMFYUI_ALLOW_NO_SOURCE_PATCH",
            params=params,
            key="comfyui_allow_no_source_patch",
        )
        != "1"
    ):
        raise RuntimeError(
            "PRINTPIPE_COMFYUI_IMAGE_PATHS is required so the adapter injects "
            "PrintPipe's reference image/frame into the workflow. Set "
            "PRINTPIPE_COMFYUI_ALLOW_NO_SOURCE_PATCH=1 only for prompt-only workflows."
        )

    prompt_id = _queue_prompt(comfy_url, workflow)
    history = _wait_for_history(comfy_url, prompt_id, params)
    file_info = _first_3d_output(history, args.output_format)
    _download_view(comfy_url, file_info, args.output)


def main() -> int:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        generate_mesh(args)
    except (RuntimeError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not args.output.exists():
        print(f"adapter did not write expected mesh: {args.output}", file=sys.stderr)
        return 2

    print(json.dumps({"output_path": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def available_media_meshgen_template_presets() -> tuple[str, ...]:
    return MEDIA_MESHGEN_TEMPLATE_PRESETS


def _normalize_preset(preset: str) -> str:
    normalized = preset.strip().lower()
    if normalized not in MEDIA_MESHGEN_TEMPLATE_PRESETS:
        allowed = ", ".join(MEDIA_MESHGEN_TEMPLATE_PRESETS)
        raise ValueError(f"unsupported media meshgen template preset: {preset}; expected one of {allowed}")
    return normalized


def render_media_meshgen_command_template(*, preset: str = "generic") -> str:
    normalized = _normalize_preset(preset)
    if normalized == "comfyui-api":
        return COMFYUI_API_MEDIA_MESHGEN_COMMAND_TEMPLATE
    return MEDIA_MESHGEN_COMMAND_TEMPLATE


def write_media_meshgen_command_template(output_path: Path, *, preset: str = "generic") -> Path:
    resolved = output_path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(render_media_meshgen_command_template(preset=preset), encoding="utf-8")
    resolved.chmod(resolved.stat().st_mode | 0o111)
    return resolved
