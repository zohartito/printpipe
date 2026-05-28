# Wave 165 - Media Meshgen Adapter Smoke Command

Date: 2026-05-28

## Question

After scaffolding a generic media meshgen adapter, how can we prove the adapter
actually writes a mesh before running the full repair/orient/bundle/slice path?

## Change

- Added `printpipe media-meshgen-smoke <input>`.
- The command accepts image, GIF, or video inputs.
- It accepts `--command` for one-off adapter testing.
- Without `--command`, it uses the configured default provider order:
  1. `PRINTPIPE_MEDIA_MESHGEN_COMMAND`
  2. `PRINTPIPE_HUNYUAN3D_COMMAND`
  3. generic missing-provider failure
- It prepares references, invokes the adapter, and writes:
  - `20_meshgen/smoke.json`
  - `20_meshgen/summary.json`
  - `20_meshgen/attempts.jsonl`
  - the generated mesh when the adapter succeeds

## Why

The readiness gate now tells users how to configure media meshgen, and the
template command creates a protocol-compliant script. The missing rung was a
cheap proof command that tests the adapter alone before burning a full PrintPipe
run.

## Verification

Focused verification:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py -q
```

Result:

```text
3 passed
```

Related media/provider verification:

```bash
.venv/bin/pytest \
  tests/test_cli_media_meshgen_smoke.py \
  tests/test_cli_media_meshgen_template.py \
  tests/test_cli_run.py \
  tests/test_pipeline_existing_mesh.py \
  tests/test_env_doctor.py \
  tests/test_beta_readiness.py \
  -q
```

Result:

```text
47 passed
```

## Boundary

This does not install or choose a real model. It proves that a configured
adapter can receive PrintPipe media references and return a mesh-shaped artifact.
