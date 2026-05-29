# Wave 182 - ComfyUI Media Adapter Project Params

Question: after adding the ComfyUI adapter preset, can PrintPipe persist the workflow and patch-path details instead of requiring fragile shell exports every time?

Finding: yes. The generic media command protocol already had a `--params-json` argument, but the ComfyUI preset did not read it and project config only stored the adapter command. This wave turns that unused channel into the adapter setup contract.

What changed:

- `.printpipe/config.json` can store `media_meshgen_params`.
- `printpipe media-meshgen-configure` accepts `--params-json` as inline JSON or a path to a JSON object.
- `media-meshgen-smoke` and normal media runs merge saved project params into the adapter `--params-json` payload.
- The ComfyUI preset reads `--params-json` and uses those values as fallbacks for:
  - `comfyui_url`
  - `comfyui_workflow`
  - `comfyui_image_paths`
  - `comfyui_prompt_paths`
  - `comfyui_seed_paths`
  - `comfyui_timeout_seconds`
  - `comfyui_allow_no_source_patch`
- Environment variables still win over saved params, so temporary overrides remain possible.
- The browser setup form now exposes those ComfyUI params directly.

Truth boundary:

- This is configuration plumbing only.
- It does not create a ComfyUI workflow.
- It does not install model weights.
- It does not provide ComfyUI/Tripo/Meshy credentials.
- It does not close the media meshgen readiness gate without a successful semantic smoke receipt.

Focused verification:

```bash
.venv/bin/pytest tests/test_config.py::test_media_meshgen_configure_parser_accepts_params_json tests/test_config.py::test_media_meshgen_configure_writes_project_config_params tests/test_config.py::test_configured_media_meshgen_params_reads_project_config tests/test_meshgen.py::test_media_command_provider_forwards_provider_params_json tests/test_cli_media_meshgen_template.py::test_comfyui_api_template_reads_inline_params_json tests/test_web_server.py::test_home_response_renders_media_meshgen_setup_forms tests/test_web_server.py::test_post_media_meshgen_configure_writes_comfyui_params_and_redirects tests/test_web_server.py::test_post_media_meshgen_smoke_forwards_saved_adapter_params -q
```
