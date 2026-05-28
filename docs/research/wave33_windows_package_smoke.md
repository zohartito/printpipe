# Wave 33 Windows Package Smoke Evidence

Status: F11 complete as a clean Windows package smoke path. This is still not a
signed Windows installer, so original roadmap item 122 remains partial.

## How It Was Run

The Windows machine `desktop-zt` was reachable over SSH. GitHub authentication
was not configured there, so the current committed source was exported from the
Mac checkout with `git archive`, copied to the Windows temp directory, and run
with `PYTHONPATH=src` through the same `printpipe` CLI code path.

The executed command inside the temporary Windows source export was equivalent
to:

```powershell
python run_smoke.py
```

Where `run_smoke.py` called:

```python
from printpipe.cli import main

raise SystemExit(
    main([
        "package-smoke",
        "--platform",
        "windows",
        "--runs-dir",
        "runs/package-smoke/windows",
        "--json",
    ])
)
```

## Result

```json
{
  "platform": "windows",
  "status": "ok",
  "run_root": "C:\\Users\\zohar_4ta16fp\\AppData\\Local\\Temp\\printpipe-head\\runs\\package-smoke\\windows\\20260528-051032-package-smoke-tiny-tetrahedron",
  "runs_dir": "C:\\Users\\zohar_4ta16fp\\AppData\\Local\\Temp\\printpipe-head\\runs\\package-smoke\\windows"
}
```

Checks:

- `windows_runtime`: ok, `win32`
- `version`: ok, `0.1.0`
- `input_fixture`: ok, generated ASCII STL
- `pipeline_run`: ok
- `reports`: ok, `run_report.json`, `run_report.md`, and `run_report.html`
  were present
- `bundle`: ok, generated
  `existing_stl_package_smoke_tiny_tetrahedron.3mf`
- `slice_gate`: `manual_required`

## Boundary

This proves the Windows smoke path can execute the local PrintPipe pipeline and
produce report plus bundle artifacts on a real Windows host. It does not prove a
signed installer, Start Menu integration, file associations, or live Bambu CLI
slicing on Windows.
