# Wave 188 - Media Smoke Workspace Config Alignment

Question: does `run_media_meshgen_smoke(..., config_cwd=workspace)` use the same workspace config for both adapter command and adapter params?

Finding: no, before this wave. The helper used `config_cwd` for params, but command resolution still came from the process environment or current checkout. Browser smoke pre-resolved the command as a workaround, but the shared helper itself was inconsistent.

What changed:

- Added a regression that calls `run_media_meshgen_smoke` with only `config_cwd` and no explicit command.
- The helper now resolves the media adapter command from `workspace/.printpipe/config.json`.
- The helper resolves adapter params from the same workspace.
- Explicit `command=` still wins.
- `PRINTPIPE_MEDIA_MESHGEN_COMMAND` still wins over project config.

Truth boundary:

- This does not provide a semantic media meshgen provider.
- This does not create a successful smoke receipt in the real project.
- It makes browser/helper smoke behavior consistent once a real provider config exists.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_cli_media_meshgen_smoke.py::test_run_media_meshgen_smoke_resolves_command_from_config_cwd \
  tests/test_cli_media_meshgen_smoke.py::test_media_meshgen_smoke_records_project_config_command \
  tests/test_web_server.py::test_post_media_meshgen_smoke_runs_configured_adapter_and_redirects \
  tests/test_web_server.py::test_post_media_meshgen_smoke_forwards_saved_adapter_params \
  -q
```
