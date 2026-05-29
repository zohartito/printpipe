# Wave 181 - ComfyUI Media Adapter Preset

Question: can PrintPipe move past a generic media-meshgen placeholder toward a real provider handoff without falsely claiming semantic image/GIF/video reconstruction is solved?

Finding: yes. Zohar's machine has a local ComfyUI checkout at `/Users/zohartito/comfyui-mac`, and that checkout contains API examples for `/prompt`, `/history/{prompt_id}`, and `/view`, plus 3D nodes that can produce `File3DGLB` and a `SaveGLB` node. That is enough to generate a concrete adapter scaffold that a real exported ComfyUI workflow can use.

What changed:

- `printpipe media-meshgen-template` now has `--preset generic` and `--preset comfyui-api`.
- The `comfyui-api` template is an executable Python adapter scaffold that:
  - requires `PRINTPIPE_COMFYUI_WORKFLOW`;
  - expects a ComfyUI API-exported workflow ending in `SaveGLB`;
  - can patch prompt, seed, and source-image fields through environment variable path lists;
  - uploads the PrintPipe reference image/frame to ComfyUI when image patch paths are supplied;
  - queues the workflow through `/prompt`, polls `/history`, and downloads the first matching 3D output through `/view`.
- The browser media setup form can write the selected preset.
- The browser media smoke form can request `stl`, `glb`, or `obj`, so a ComfyUI `SaveGLB` workflow can be smoked as GLB instead of being forced into STL.
- `final-next` now points the missing-provider setup action at the ComfyUI preset and GLB smoke command.

Truth boundary:

- This does not install ComfyUI.
- This does not create or validate a Tripo, Meshy, Rodin, Hunyuan, or Chimney workflow.
- This does not supply ComfyUI or provider API credentials.
- This does not close the media meshgen readiness gate.
- It only turns the next provider action from "write some adapter" into "export a real ComfyUI API workflow, point this preset at it, then run smoke evidence."

Focused verification:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_template.py tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms tests/test_web_server.py::test_post_media_meshgen_template_writes_adapter_and_redirects tests/test_web_server.py::test_post_media_meshgen_template_writes_selected_preset_and_redirects tests/test_web_server.py::test_post_media_meshgen_smoke_runs_configured_adapter_and_redirects -q
```

Result: `10 passed`.
