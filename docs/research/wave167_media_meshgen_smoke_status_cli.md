# Wave 167 - Media Meshgen Smoke Status CLI

Date: 2026-05-28

## Question

How should a user or agent quickly inspect whether media meshgen smoke evidence
exists without reading full readiness JSON?

## Finding

Wave 166 made beta readiness depend on successful smoke receipts, but the receipt
status was only directly visible through `readiness.json` or by knowing the run
folder layout. That made the proof boundary correct but slightly buried.

## Change

- Added `printpipe media-meshgen-smoke-status`.
- The command scans the selected runs directory for
  `*/20_meshgen/smoke.json` receipts.
- `--json` returns the same machine-readable status payload used by readiness.
- `--strict` returns exit code `2` when no successful smoke receipt exists.
- Human output includes the latest successful smoke run, provider, output path,
  counts, message, and next action.

## Verification

Red test:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py -q
```

Result before implementation:

```text
3 failed, 5 passed
```

Green test:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_smoke.py -q
```

Result after implementation:

```text
8 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
584 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This command does not prove a real provider exists by itself. It only exposes
the smoke receipt evidence that readiness already requires.
