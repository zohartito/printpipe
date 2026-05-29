# Wave 183 - ComfyUI Workflow Inspector

Question: once a ComfyUI API workflow exists, can PrintPipe help find the patch paths needed by the ComfyUI adapter preset?

Finding: yes. ComfyUI API exports are plain JSON node graphs keyed by node id. The adapter only needs stable dotted paths into that JSON for image upload, prompt text, and seeds. A static inspector can infer useful candidates before any server, credential, or model is available.

What changed:

- Added `printpipe media-meshgen-comfyui-inspect <workflow.json>`.
- Added `src/printpipe/meshgen/comfyui_workflow.py`.
- The inspector reports:
  - workflow path
  - status
  - node count
  - `SaveGLB` node ids
  - image patch candidates
  - prompt patch candidates
  - seed patch candidates
  - suggested `media_meshgen_params`
  - a concrete `media-meshgen-configure --params-json ...` command
- It marks workflows without `SaveGLB` as `action_required`.

Truth boundary:

- This does not run ComfyUI.
- This does not validate provider API credentials.
- This does not prove generated mesh quality.
- This does not close the media meshgen gate.
- It only reduces the chance that the ComfyUI adapter is configured with the wrong patch paths.

Smoke example:

```bash
printpipe media-meshgen-comfyui-inspect workflows/image_to_glb.json --json
```

Focused verification:

```bash
.venv/bin/pytest tests/test_comfyui_workflow.py -q
```
