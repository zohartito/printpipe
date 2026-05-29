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

Regression caught after the first implementation: the unit helper could read
the default `.printpipe/config.json`, but `printpipe doctor` converted
`env=None` to `os.environ` before calling media readiness. That made the
readiness layer treat the real CLI environment like an injected test env and
skip the default project config.

Added regressions:

```bash
.venv/bin/pytest tests/test_config.py::test_configured_media_meshgen_command_reads_default_project_config tests/test_config.py::test_environment_report_reads_default_project_config_for_real_environment -q
```

Result before the doctor fix:

```text
test_environment_report_reads_default_project_config_for_real_environment failed:
expected overall_status == "ready", got "action_required"
```

Result after the fix:

```text
2 passed
```

Manual project-config dogfood:

```bash
.venv/bin/printpipe media-meshgen-configure --command ".venv/bin/printpipe media-meshgen-heightfield"
.venv/bin/printpipe doctor --json
.venv/bin/printpipe media-meshgen-smoke /tmp/printpipe-heightfield-smoke-v2.png --runs-dir runs/media-meshgen-smoke-configured
.venv/bin/printpipe run /tmp/printpipe-heightfield-smoke-v2.png --runs-dir runs/dogfood --material "Generic PLA" --printer "Bambu Lab P2S" --use-case "configured media heightfield smoke"
.venv/bin/printpipe final-next --runs-dir runs --release-dir dist/release --json
```

Observed:

```text
doctor meshgen overall_status: ready
doctor live_media_provider_count: 1
configured smoke run: runs/media-meshgen-smoke-configured/20260529-011815-printpipe-heightfield-smoke-v2
configured full media run: runs/dogfood/20260529-011816-printpipe-heightfield-smoke-v2
final-next next action: physical_validation / PLA coupon
```

Full verification:

```bash
.venv/bin/pytest -q
python -m compileall -q src
git diff --check
```

Result:

```text
605 passed, 1 skipped
compileall exit 0
diff check exit 0
```

## Boundary

This makes local command configuration real and repeatable. It does not prove
that the command is a semantic image-to-object model, and it does not create
physical print evidence.
