# Wave 172 - Tested Media Command Handoff

Date: 2026-05-29

## Question

After a one-off `media-meshgen-smoke --command ...` succeeds, can PrintPipe
guide the user to configure that tested command instead of sending them back to
the blank adapter template?

## Finding

Wave 171 proved the adapter protocol with a real heightfield STL, but the narrow
`20_meshgen/smoke.json` receipt did not record the command that produced the
mesh. `summary.json` had the expanded subprocess argv, but the readiness and
final-plan surfaces intentionally read `smoke.json`. As a result,
`final-next` still recommended:

```bash
printpipe media-meshgen-template --output scripts/media_meshgen_adapter.py
```

even when a smoke-proven one-off command existed.

## Change

- `media-meshgen-smoke` now writes `command` into `smoke.json` when a command is
  passed directly or resolved from `PRINTPIPE_MEDIA_MESHGEN_COMMAND` /
  `PRINTPIPE_HUNYUAN3D_COMMAND`.
- `media-meshgen-smoke-status` exposes that command on
  `latest_successful_smoke`.
- `final-next` now switches to:

```bash
export PRINTPIPE_MEDIA_MESHGEN_COMMAND='.venv/bin/printpipe media-meshgen-heightfield'
```

when a successful `media_command` smoke exists but the provider is not
configured in the current environment.

## Verification

Red tests:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py tests/test_final_plan.py -q -k 'tested_command or records_adapter_command or configures_tested'
```

Result before implementation:

```text
2 failed
```

Focused verification:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py tests/test_final_plan.py tests/test_final_readiness_web.py tests/test_web_server.py -q
```

Result:

```text
104 passed
```

Manual smoke:

```bash
.venv/bin/printpipe media-meshgen-smoke /tmp/printpipe-heightfield-smoke-v2.png \
  --command ".venv/bin/printpipe media-meshgen-heightfield" \
  --runs-dir runs/media-meshgen-smoke
.venv/bin/printpipe media-meshgen-smoke-status --runs-dir runs --json
.venv/bin/printpipe final-next --runs-dir runs --release-dir dist/release --json
```

Result:

```text
media meshgen smoke: succeeded
latest_successful_smoke.command: .venv/bin/printpipe media-meshgen-heightfield
next_command: export PRINTPIPE_MEDIA_MESHGEN_COMMAND='.venv/bin/printpipe media-meshgen-heightfield'
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
597 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This does not edit shell profiles, launch agents, or app environment. It converts
existing smoke evidence into an exact handoff command while leaving the provider
gate action-required until the command is actually configured and checked.
