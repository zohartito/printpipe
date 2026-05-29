# Wave 187 - ComfyUI Readiness Drift Guard

Question: after a ComfyUI workflow is saved into `.printpipe/config.json`, can the workflow be deleted or edited into a broken state while readiness still counts the provider as live?

Finding: yes, before this wave. Write-time validation stopped new bad config, but readiness only checked that a media command existed. A previously valid config could drift and still look like a live provider until smoke/run time.

What changed:

- Added a shared config workspace resolver for paths relative to `.printpipe/config.json`.
- Generic media command provider health checks now read saved media params.
- If `comfyui_workflow` is present, readiness re-runs the static ComfyUI workflow validator.
- Unready saved workflows make the provider health status `failed`.
- Media readiness uses the failed provider message instead of reporting a live provider.

Truth boundary:

- This is still static validation.
- It does not contact ComfyUI.
- It does not verify model weights, credentials, runtime dependency health, queue execution, or generated mesh quality.
- A successful `media-meshgen-smoke` receipt is still required to close the media gate.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_meshgen.py::test_media_meshgen_readiness_rejects_stale_comfyui_workflow_config \
  tests/test_meshgen.py::test_media_meshgen_readiness_treats_builtin_heightfield_as_plumbing_only \
  tests/test_config.py::test_media_meshgen_configure_writes_project_config_params \
  tests/test_config.py::test_media_meshgen_configure_rejects_unready_comfyui_params \
  -q
```
