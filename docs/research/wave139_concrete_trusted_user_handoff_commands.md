# Wave 139 - Concrete Trusted-User Handoff Commands

Date: 2026-05-28

## Problem

Trusted-user beta handoff rows had real run reports, bundles, and handoff Markdown files, but their commands still contained placeholders:

```bash
runs/<run-id>
<material>
```

That was friction at the exact moment where a human or another agent needs to record evidence accurately.

## Change

When a `90_beta/trusted_user_feedback_handoff_*.md` file exists, `beta-feedback-plan` now parses the handoff context and produces:

- an immediate `printpipe open-folder "<run-root>" --target run` review command
- a concrete `record-beta-feedback` command with the real run root
- the tester slot from the handoff
- the real input type, material, printer, and run report artifact path

If no handoff exists, the plan still uses the starter placeholder command because no target run is known yet.

## Verification

Targeted red/green coverage:

```bash
.venv/bin/pytest tests/test_beta_feedback.py::test_trusted_user_feedback_plan_uses_concrete_handoff_commands -q
```

Focused regression coverage:

```bash
.venv/bin/pytest tests/test_beta_feedback.py tests/test_final_plan.py tests/test_final_readiness_web.py tests/test_web_server.py -q
```

Local smoke:

```bash
.venv/bin/printpipe beta-feedback-plan --runs-dir runs --json
.venv/bin/printpipe final-plan --release-dir dist/release --runs-dir runs --json
```

The current slipper trusted-user rows now point at the real slipper run folder and use `SUNLU TPU 90A` in their record commands.

## Boundary

This is execution guidance only. The trusted-user beta gate still requires three unique completed feedback packets with supporting evidence.
