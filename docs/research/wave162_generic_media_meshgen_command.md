# Wave 162 - Generic Media Meshgen Command

Date: 2026-05-28

## Question

Can PrintPipe support a generic media-to-mesh command adapter instead of requiring every live image/GIF/video path to masquerade as Hunyuan3D?

## Change

- Added `MediaCommandMeshProvider`.
- Activation env var: `PRINTPIPE_MEDIA_MESHGEN_COMMAND`.
- The command protocol matches the existing Hunyuan local command protocol:
  - `--input-kind`
  - `--source`
  - `--reference-image`
  - `--output`
  - `--output-format`
  - `--target-use`
  - `--quality`
  - optional `--prompt`
  - optional `--seed`
  - optional `--params-json`
- The command may write directly to `--output`, print JSON with `output_path`, or print a mesh path.

## Why

The readiness gate had one local activation route: `PRINTPIPE_HUNYUAN3D_COMMAND`.
That was honest, but too narrow for Zohar's product direction. He may want to try
Hunyuan, a local wrapper, a hosted GPU script, Chimney, Meshy/Rodin wrappers, or a
future provider without changing PrintPipe internals each time.

## Verification

Focused verification:

```bash
.venv/bin/pytest \
  tests/test_meshgen.py::test_registry_exposes_existing_hunyuan3d_and_placeholder_providers \
  tests/test_meshgen.py::test_media_command_provider_runs_generic_command_and_writes_receipts \
  tests/test_env_doctor.py::test_environment_report_counts_generic_media_command_provider \
  tests/test_pipeline_existing_mesh.py::test_media_pipeline_uses_generic_media_command_from_environment \
  -q
```

Result:

```text
4 passed
```

Compatibility verification:

```bash
.venv/bin/pytest \
  tests/test_meshgen.py \
  tests/test_env_doctor.py \
  tests/test_pipeline_existing_mesh.py \
  tests/test_cli_run.py::test_run_media_input_writes_failed_meshgen_report_and_returns_nonzero \
  tests/test_cli_run.py::test_run_media_input_with_configured_hunyuan_command_writes_bundle \
  -q
```

Result:

```text
27 passed
```

## Boundary

This is an adapter hook, not a configured live provider. Readiness should still
report `media_meshgen=action_required` on this machine until the env var points
at a working command.
