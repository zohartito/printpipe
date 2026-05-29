# Wave 185 - Browser ComfyUI Intake Guard

Question: should the browser ComfyUI workflow upload persist adapter/config state when the static inspector says the workflow is not ready?

Finding: no. A workflow missing `SaveGLB` or useful image/prompt patch targets cannot drive the ComfyUI adapter to a mesh output. Persisting that as configured provider state creates a false sense of readiness and pushes the failure to a later smoke run.

What changed:

- `POST /media-meshgen/comfyui-workflow` now saves the uploaded JSON, runs the static inspector, and checks the inspector status before writing adapter/config files.
- Unready workflows return HTTP `400`.
- The response includes the inspector warning text, such as missing `SaveGLB`.
- The uploaded workflow remains under `workflows/` for diagnosis.
- `scripts/media_meshgen_adapter.py` and `.printpipe/config.json` are not written for unready workflows.

Truth boundary:

- This does not run ComfyUI.
- This does not validate model weights or credentials.
- This does not prove mesh quality.
- This only prevents a known bad workflow from becoming local configured-provider state.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_web_server.py::test_post_media_meshgen_comfyui_workflow_upload_configures_params \
  tests/test_web_server.py::test_post_media_meshgen_comfyui_workflow_requires_upload \
  tests/test_web_server.py::test_post_media_meshgen_comfyui_workflow_rejects_unready_workflow \
  -q
```
