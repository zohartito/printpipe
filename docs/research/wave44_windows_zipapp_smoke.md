# Wave 44 - Windows Zipapp Smoke

Date: 2026-05-28

## Goal

Verify the actual `printpipe.pyz` artifact on Windows, not only a source export
or macOS-local package smoke.

## Host

- SSH target: `desktop-zt`
- Python: `3.13.7`
- PowerShell: `5.1.26100.8521`

## Commands

Local build/copy:

```bash
.venv/bin/printpipe build-zipapp --output "$LOCAL_DIR/printpipe.pyz" --json
scp "$LOCAL_DIR/printpipe.pyz" desktop-zt:AppData/Local/Temp/printpipe-zipapp/printpipe.pyz
```

Remote Windows checks:

```cmd
python %TEMP%\printpipe-zipapp\printpipe.pyz --version
python %TEMP%\printpipe-zipapp\printpipe.pyz package-smoke --platform windows --runs-dir %TEMP%\printpipe-zipapp\runs --json
```

## Results

- Version command: `printpipe 0.1.0`
- Package smoke: `status=ok`
- Windows runtime: `win32`
- Generated fixture:
  `C:\Users\zohar_4ta16fp\AppData\Local\Temp\printpipe-zipapp\package_smoke_tiny_tetrahedron.stl`
- Run root:
  `C:\Users\zohar_4ta16fp\AppData\Local\Temp\printpipe-zipapp\runs\20260528-063417-package-smoke-tiny-tetrahedron`
- Reports:
  `80_reports\run_report.json`, `.md`, `.html`
- Bundle:
  `60_bundle\existing_stl_package_smoke_tiny_tetrahedron.3mf`

## Boundary

This proves the portable Python artifact works on Windows. It still does not
prove a signed installer, bundled Python runtime, Start Menu integration, file
associations, or live Windows+Bambu Studio slicing.
