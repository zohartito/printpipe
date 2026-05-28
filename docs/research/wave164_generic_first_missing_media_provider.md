# Wave 164 - Generic-First Missing Media Provider Failure

Date: 2026-05-28

## Question

After adding `PRINTPIPE_MEDIA_MESHGEN_COMMAND`, what should users see when
they run an image/GIF/video input with no provider configured?

## Problem

The pipeline still defaulted to `Hunyuan3DProvider()` when neither the generic
nor Hunyuan environment variable was set. That made CLI, web, and report
failures say only:

```text
Hunyuan3D local command is not configured
```

That was stale product behavior because PrintPipe now supports a generic media
adapter hook and a scaffold command.

## Change

- Default media provider selection now prefers:
  1. `PRINTPIPE_MEDIA_MESHGEN_COMMAND`
  2. `PRINTPIPE_HUNYUAN3D_COMMAND`
  3. unconfigured `MediaCommandMeshProvider` for the failure receipt
- Missing-provider warnings now point at:
  - `printpipe media-meshgen-template --output scripts/media_meshgen_adapter.py`
  - `PRINTPIPE_MEDIA_MESHGEN_COMMAND`
  - `PRINTPIPE_HUNYUAN3D_COMMAND`
  - hosted providers
- Doctor/readiness actions use the same setup path.

## Verification

Focused behavior:

```bash
.venv/bin/pytest \
  tests/test_cli_run.py::test_run_media_input_writes_failed_meshgen_report_and_returns_nonzero \
  tests/test_pipeline_existing_mesh.py::test_existing_mesh_pipeline_rejects_media_inputs_with_reported_failure \
  tests/test_web_server.py::test_post_runs_accepts_multipart_upload_creates_skeleton_run_and_redirects \
  tests/test_env_doctor.py::test_environment_report_combines_dependencies_bambu_and_profile_detection \
  tests/test_beta_readiness.py::test_beta_readiness_report_blocks_when_media_meshgen_provider_unavailable \
  -q
```

Result:

```text
5 passed
```

Related suite:

```bash
.venv/bin/pytest \
  tests/test_cli_run.py \
  tests/test_pipeline_existing_mesh.py \
  tests/test_web_server.py \
  tests/test_env_doctor.py \
  tests/test_beta_readiness.py \
  tests/test_meshgen.py \
  -q
```

Result:

```text
109 passed
```

## Boundary

This is still configuration guidance, not a live model installation. Readiness
must remain action-required until a real media meshgen command or hosted
provider is configured.
