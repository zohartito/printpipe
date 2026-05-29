# Wave 184 - Browser ComfyUI Workflow Intake

Question: can the local web app take the static ComfyUI workflow inspector from Wave 183 and make setup possible without hand-writing config JSON?

Finding: yes. The browser can accept an exported ComfyUI API workflow JSON, save it into the project, write the ComfyUI adapter preset, inspect the graph for patch paths, and persist the adapter command plus suggested params into `.printpipe/config.json`.

What changed:

- Added `POST /media-meshgen/comfyui-workflow`.
- Added a ComfyUI workflow upload card to the home-page `Media meshgen setup` panel.
- The route saves uploaded workflow JSON under `workflows/`.
- The route writes `scripts/media_meshgen_adapter.py` from the `comfyui-api` preset.
- The route runs the same static inspector used by `printpipe media-meshgen-comfyui-inspect`.
- The route saves `media_meshgen_command` and `media_meshgen_params` into local project config.

Truth boundary:

- This does not run ComfyUI.
- This does not verify that ComfyUI is installed or reachable.
- This does not install model weights or provider credentials.
- This does not prove semantic image/GIF/video reconstruction.
- This does not close the media meshgen readiness gate.
- A successful `media-meshgen-smoke` receipt from a real workflow/provider is still required.

Browser path:

1. Start the local app with `printpipe serve --port 8877 --runs-dir runs`.
2. Open the home page.
3. Use `Media meshgen setup -> ComfyUI workflow`.
4. Upload an exported ComfyUI API workflow JSON ending in `SaveGLB`.
5. Run a media smoke test with a real reference image/GIF/video.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms \
  tests/test_web_server.py::test_post_media_meshgen_comfyui_workflow_upload_configures_params \
  tests/test_web_server.py::test_post_media_meshgen_comfyui_workflow_requires_upload \
  -q
```
