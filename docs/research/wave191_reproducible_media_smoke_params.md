# Wave 191 - Reproducible Media Smoke Params

Question: if a one-off media smoke succeeds with ComfyUI workflow and patch-path params, can final-next promote that tested setup without dropping the params?

Finding: not before this wave. Smoke receipts stored the tested command, but not the adapter params that may have made the command work. Final-plan could suggest configuring the command while silently omitting ComfyUI workflow and patch paths.

What changed:

- Smoke receipts now include allowlisted `adapter_params`.
- The allowlist covers ComfyUI URL, workflow path, image/prompt/seed patch paths, timeout, prompt-only mode, and model version.
- Obvious unallowlisted keys such as `api_key` are not copied.
- `media-meshgen-smoke-status` exposes the stored adapter params.
- Final-plan appends `--params-json ...` when suggesting a `media-meshgen-configure --command ...` handoff from a tested smoke.

Truth boundary:

- This does not create a real provider.
- This does not prove semantic reconstruction by itself.
- It only makes future successful smoke evidence reproducible without losing non-secret adapter setup.

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_cli_media_meshgen_smoke.py::test_media_meshgen_smoke_receipt_preserves_safe_adapter_params \
  tests/test_final_plan.py::test_media_meshgen_action_plan_preserves_tested_safe_params \
  tests/test_final_plan.py::test_media_meshgen_action_plan_configures_tested_smoke_command \
  -q
```
