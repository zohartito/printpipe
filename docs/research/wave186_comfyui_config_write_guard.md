# Wave 186 - ComfyUI Config Write Guard

Question: after guarding browser workflow uploads, can users still bypass the guard by manually saving a bad `comfyui_workflow` through the command form or CLI?

Finding: yes, before this wave. The manual config paths could persist a missing-`SaveGLB` workflow into `.printpipe/config.json`, creating local provider state that looked configured but would fail later during smoke.

What changed:

- Added shared validation for ComfyUI params that include `comfyui_workflow`.
- The validator resolves relative workflow paths against the project/config workspace for inspection.
- `printpipe media-meshgen-configure --params-json ...` validates before writing local config.
- Browser `POST /media-meshgen/configure` validates before writing local config.
- The stored params remain unchanged; relative paths stay relative.

Truth boundary:

- This is static validation only.
- It does not contact a ComfyUI server.
- It does not verify credentials, model weights, runtime dependencies, or mesh quality.
- It does not close the media meshgen gate without a successful smoke receipt.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_config.py::test_media_meshgen_configure_writes_project_config_params \
  tests/test_config.py::test_media_meshgen_configure_rejects_unready_comfyui_params \
  tests/test_web_server.py::test_post_media_meshgen_configure_writes_comfyui_params_and_redirects \
  tests/test_web_server.py::test_post_media_meshgen_configure_rejects_unready_comfyui_params \
  -q
```
