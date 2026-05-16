# Wave 8 Integration Summary

Status: complete as a packaging/environment foundation; not a finished installer.

## What Landed

Wave 8 added environment and packaging support for local v1:

- macOS runtime/path report helpers.
- Windows runtime/path report helpers that are safe to test on macOS.
- Bambu Studio install candidate detection for macOS and Windows.
- Bambu Studio user profile folder detection for `BambuStudio/user/<user-id>`.
- Missing dependency/preflight checks for Python, optional mesh repair, optional Bambu CLI, optional Blender, and future print-monitor dependencies.
- `printpipe doctor` and `printpipe doctor --json` as the unified local diagnostic entry point.
- Packaging and troubleshooting docs under `docs/`.

## What Is Still Partial

- There is no signed macOS app package yet.
- There is no Windows installer yet.
- Windows Bambu profile paths still need a real Windows smoke test before automatic preset writes are allowed.
- Optional dependency installation is reported, not automatically performed.

## Verification

```text
.venv/bin/python -m pytest tests/test_env_dependencies.py tests/test_env_doctor.py tests/test_cli_doctor.py tests/test_env_macos.py tests/test_env_windows.py tests/test_env_bambu_studio.py tests/test_env_bambu_profiles.py
36 passed
```

Full-suite verification should be run before committing Wave 8.
