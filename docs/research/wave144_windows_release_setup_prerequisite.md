# Wave 144 - Windows Release Setup Prerequisite Command

## Question

Does the release-distribution plan give a complete sequence for the Windows installer gate, or does it point at a prerequisite artifact that may not exist?

## Finding

The plan assumed `dist/release/PrintPipe-Windows-standalone.zip` existed before running:

```bash
printpipe build-windows-installer --standalone-zip dist/release/PrintPipe-Windows-standalone.zip ...
```

In the current local release folder, the manifest has `PrintPipe-Windows-portable.zip` but not `PrintPipe-Windows-standalone.zip`. That made the Windows action truthful about the missing signed installer, but incomplete as an operator handoff.

## Change

`release-plan` now adds a setup prerequisite when the standalone ZIP is missing:

```bash
printpipe build-windows-standalone --output dist/release/PrintPipe-Windows-standalone.zip --json
```

The setup command is surfaced through:

- terminal release-plan rendering
- release handoff Markdown
- final-readiness web rows
- final-readiness next-action callouts

## Verification

Targeted red/green checks:

```bash
.venv/bin/pytest tests/test_release_status.py::test_release_distribution_plan_turns_distribution_gates_into_commands tests/test_release_status.py::test_release_distribution_start_writes_handoff_without_signed_evidence tests/test_final_readiness_web.py::test_build_final_readiness_view_keeps_release_commands_and_required_inputs tests/test_final_readiness_web.py::test_render_final_readiness_panel_next_action_shows_release_commands tests/test_final_readiness_web.py::test_render_final_readiness_panel_shows_release_commands_and_required_inputs -q
```

Result after implementation:

```text
5 passed
```

Live spot-check:

```bash
.venv/bin/printpipe release-plan --release-dir dist/release --runs-dir runs --json
```

The Windows distribution action now includes `setup_command` before its installer build command.

## Boundary

This does not create signed Windows distribution evidence. It only makes the next command sequence complete. The Windows gate still requires a Windows signing/installer toolchain, a code-signing certificate, a signed `PrintPipeSetup.exe`, and a release manifest that verifies it.
