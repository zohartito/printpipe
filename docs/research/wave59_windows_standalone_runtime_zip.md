# Wave 59 - Windows Standalone Runtime ZIP

## Question

Can PrintPipe produce a Windows handoff ZIP that runs without requiring the
tester to install Python first?

## Implementation

- Added `printpipe.packaging.windows_standalone.build_windows_standalone_package()`.
- Added `printpipe build-windows-standalone --output dist/PrintPipe-Windows-standalone.zip`.
- Uses PyInstaller `--onedir --console --name PrintPipe`.
- Writes a standalone entrypoint that preserves normal CLI passthrough.
- With no arguments, the executable launches the local web UI flow at
  `http://127.0.0.1:8765/` and defaults runs to `%USERPROFILE%\PrintPipe\runs`.

## Artifact Shape

The generated ZIP contains:

- `PrintPipe/PrintPipe.exe`
- `PrintPipe/_internal/...` PyInstaller runtime files
- `PrintPipe/README.txt`

Metadata reports:

- `runtime_kind=pyinstaller`
- `bundles_python_runtime=true`
- `bundles_bambu_studio=false`
- `signed=false`
- `notarized=false`

## Live Windows Evidence

Ran on `desktop-zt` from a fresh source export and Windows venv with PyInstaller:

```powershell
printpipe build-windows-standalone `
  --output $env:TEMP\printpipe-windows-standalone-live\dist\PrintPipe-Windows-standalone.zip `
  --pyinstaller $env:TEMP\printpipe-windows-standalone-live\.venv\Scripts\pyinstaller.exe `
  --json
```

Observed result:

- `status=ok`
- `archive_name=PrintPipe-Windows-standalone.zip`
- `executable_path=PrintPipe/PrintPipe.exe`
- `bundles_python_runtime=true`
- `bundles_bambu_studio=false`
- `size_bytes=9669184`

After extracting the ZIP:

- `PrintPipe.exe --version` returned `printpipe 0.1.0`
- `PRINTPIPE_APP_DRY_RUN=1 PrintPipe.exe` printed the local web UI command for
  `http://127.0.0.1:8765/`
- `PrintPipe.exe package-smoke --platform windows --runs-dir ... --json`
  returned `status=ok`
- package smoke generated reports and a Bambu `.3mf`

## Boundary

This is not a signed Windows installer. It does not create Start Menu shortcuts,
register file associations, or bundle Bambu Studio. The package-smoke slice gate
remains `manual_required` on `desktop-zt` because Bambu Studio is not installed
or discoverable on that Windows host.
