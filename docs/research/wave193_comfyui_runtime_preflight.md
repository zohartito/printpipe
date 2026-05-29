Wave 193 - ComfyUI Runtime Preflight

Question: after a ComfyUI workflow JSON passes static inspection, can PrintPipe distinguish "the workflow file looks right" from "the local ComfyUI API is reachable and has the required 3D node classes" before running a full media smoke?

Finding: not before this wave. PrintPipe could inspect workflow JSON for `SaveGLB`, persist patch paths, and reject stale workflow files, but it had no direct runtime probe for the ComfyUI API.

Change:
- Added `printpipe media-meshgen-comfyui-preflight`.
- The preflight checks `GET /system_stats` and `GET /object_info`.
- It verifies required node classes, defaulting to `SaveGLB`.
- It supports `--json`, `--strict`, `--timeout`, and repeated `--required-node`.
- Added `/media-meshgen/comfyui-preflight.json` to the local app.
- Added a preflight link and terminal command to the media setup panel.

Boundary:
- Runtime preflight is not semantic proof.
- It does not queue a ComfyUI workflow.
- It does not produce a mesh.
- It does not replace `media-meshgen-smoke`.
- The final media gate still requires a successful smoke receipt from a real provider.

Verification:

```bash
.venv/bin/pytest tests/test_comfyui_runtime.py \
  tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms \
  tests/test_web_server.py::test_media_meshgen_comfyui_preflight_json_reports_runtime -q
```
