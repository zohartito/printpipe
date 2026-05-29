# Wave 166 - Media Meshgen Readiness Requires Smoke Evidence

Date: 2026-05-28

## Question

Should `printpipe readiness` treat `PRINTPIPE_MEDIA_MESHGEN_COMMAND` as ready
before we know the command can actually write a mesh?

## Finding

No. Wave 165 added `media-meshgen-smoke`, but the readiness gate still had a
fake-positive path: a non-empty environment variable could mark media meshgen as
ready even when the command was broken, missing dependencies, or unable to write
the requested output.

## Change

- Added smoke receipt scanning under `runs/*/20_meshgen/smoke.json`.
- A receipt counts as successful only when:
  - `status` is `succeeded`
  - the referenced `output_path` still exists on disk
- `build_beta_readiness_report()` now includes `media_meshgen_smoke_status`.
- The `media_meshgen` gate now requires both:
  - a configured live provider from doctor/environment readiness
  - at least one successful smoke receipt

## Verification

Focused verification:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py tests/test_beta_readiness.py -q
```

Result:

```text
15 passed
```

Readiness/web/release verification:

```bash
.venv/bin/pytest \
  tests/test_beta_readiness.py \
  tests/test_cli_readiness.py \
  tests/test_web_server.py \
  tests/test_release_status.py \
  tests/test_final_plan.py \
  tests/test_final_readiness_web.py \
  tests/test_cli_media_meshgen_smoke.py \
  -q
```

Result:

```text
126 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
581 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This still does not install a live model/provider. It makes the readiness gate
honest: configured-but-untested providers are setup progress, not beta/release
readiness.
