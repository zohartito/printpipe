# Wave 171 - Built-In Heightfield Smoke Adapter

Date: 2026-05-28

## Question

Can PrintPipe prove the media meshgen command protocol with a real local mesh
without requiring Hunyuan, ComfyUI, Chimney, or a hosted GPU provider?

## Finding

The pipeline already had the right generic adapter contract and smoke harness,
but the only suggested next action was to scaffold a placeholder adapter that
intentionally fails until a real provider is filled in. That is honest, but it
left no dependency-free way to prove the media command protocol end-to-end.

Zohar's machine has ComfyUI/Hunyuan files under `/Users/zohartito/comfyui-mac`,
but that is not the same as a configured, running, smoke-proven PrintPipe
provider. The next useful step is a local plumbing adapter that writes a real
mesh while clearly refusing to call itself semantic reconstruction.

## Change

- Added `printpipe media-meshgen-heightfield`.
- The command accepts the same adapter arguments used by
  `PRINTPIPE_MEDIA_MESHGEN_COMMAND`.
- It reads 8-bit PNG references using a dependency-free parser.
- It writes a closed ASCII STL relief heightfield with top, bottom, and side
  triangles.
- `media-meshgen-smoke` can now run:

```bash
printpipe media-meshgen-smoke reference.png \
  --command "printpipe media-meshgen-heightfield" \
  --runs-dir runs/media-meshgen-smoke
```

## Verification

Red test:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_heightfield.py -q
```

Result before implementation:

```text
3 failed
```

Focused green:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_heightfield.py -q
```

Result:

```text
3 passed
```

Focused meshgen/CLI verification:

```bash
.venv/bin/pytest tests/test_cli_media_meshgen_heightfield.py tests/test_cli_media_meshgen_smoke.py tests/test_cli_media_meshgen_template.py tests/test_meshgen.py tests/test_pipeline_existing_mesh.py -q
```

Result:

```text
35 passed
```

Manual smoke:

```bash
.venv/bin/printpipe media-meshgen-smoke /tmp/printpipe-heightfield-smoke.png \
  --command ".venv/bin/printpipe media-meshgen-heightfield" \
  --runs-dir runs/media-meshgen-smoke
.venv/bin/printpipe media-meshgen-smoke-status --runs-dir runs --strict
```

Result:

```text
media meshgen smoke: succeeded
overall: passed
successful: 1
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
595 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Scanner Fix

The documented smoke path uses `runs/media-meshgen-smoke/<run-id>`, while the
status scanner only checked direct `runs/<run-id>` children. This wave changed
the scanner to find nested `**/20_meshgen/smoke.json` receipts so the documented
command sequence is actually visible to `media-meshgen-smoke-status`,
readiness, and the browser smoke panel.

## Boundary

This is a protocol/plumbing smoke path. It produces a real STL from PNG pixel
heights, but it is not AI image-to-object generation and should not be presented
as a replacement for Hunyuan, ComfyUI, Chimney, Meshy, Rodin, or a hosted
semantic mesh provider.
