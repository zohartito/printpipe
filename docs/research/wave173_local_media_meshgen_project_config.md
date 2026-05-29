# Wave 173 - Local Media Meshgen Project Config

Date: 2026-05-29

## Question

Can PrintPipe turn a smoke-proven one-off media meshgen command into local app
configuration without asking Zohar to manually edit shell profiles?

## Finding

Wave 172 made `final-next` show the exact command that should be exported, but
that still depended on a shell session or launch environment. The local app,
doctor, readiness checks, and normal media runs needed a first-class local config
handoff.

## Change

- Added `printpipe.config`.
- Added local `.printpipe/config.json` loading with `PRINTPIPE_CONFIG_PATH`
  override.
- Added:

```bash
printpipe media-meshgen-configure --command "<adapter command>"
```

- `MediaCommandMeshProvider`, `printpipe doctor`, readiness, and normal media
  runs now use the configured command when the environment variable is absent.
- `.printpipe/` is ignored by git because it is local machine/app state.
- `final-next` now recommends the config command for a smoke-proven generic media
  command.

## Verification

Red test:

```bash
.venv/bin/pytest tests/test_config.py tests/test_final_plan.py -q -k 'media_meshgen_configure or project_config or configures_tested'
```

Result before implementation:

```text
ModuleNotFoundError: No module named 'printpipe.config'
```

Focused green:

```bash
.venv/bin/pytest tests/test_config.py tests/test_final_plan.py -q -k 'media_meshgen_configure or project_config or configures_tested'
```

Result:

```text
6 passed
```

Focused integration:

```bash
.venv/bin/pytest tests/test_config.py tests/test_meshgen.py tests/test_env_doctor.py tests/test_pipeline_existing_mesh.py tests/test_final_plan.py tests/test_cli_media_meshgen_smoke.py -q
```

Result:

```text
64 passed
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
603 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This makes local command configuration real and repeatable. It does not prove
that the command is a semantic image-to-object model, and it does not create
physical print evidence.
