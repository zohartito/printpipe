# Wave 151 - Release Distribution Plan UI Parity

## Question

Does the dedicated release distribution panel show the signing/tool prerequisites and setup commands needed to execute the release plan?

## Finding

`release-plan` already carries important execution metadata:

- required signing/tool inputs
- release handoff command
- release handoff Markdown path
- build/check command
- follow-up command
- Windows standalone ZIP setup prerequisite when the ZIP is missing

The home-page `Release distribution plan` panel showed the high-level actions, but hid required inputs and setup prerequisites. Final-readiness could show those fields, so the dedicated release panel lagged behind the endgame checklist.

## Change

- Render `Required inputs` on release action cards.
- Render `Setup prerequisite` commands, including the Windows standalone ZIP build command.
- Label release handoff, build/check, and follow-up check commands.

## Verification

```bash
.venv/bin/pytest tests/test_web_server.py::test_home_response_renders_release_distribution_plan -q
```

Result: `1 passed`.

## Boundary

This is execution UI only. It does not create Developer ID certificates, notarize macOS artifacts, install Windows signing tools, or produce a signed Windows installer.
