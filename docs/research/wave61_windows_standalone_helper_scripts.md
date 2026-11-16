# Wave 61 - Windows Standalone Helper Scripts

## Question

Can the runtime-bundled Windows standalone ZIP offer the same optional local
convenience scripts as the portable ZIP while targeting `PrintPipe.exe` directly?

## Implementation

The standalone ZIP now includes:

- `PrintPipe/install-start-menu.ps1`
- `PrintPipe/uninstall-start-menu.ps1`
- `PrintPipe/install-file-associations.ps1`
- `PrintPipe/uninstall-file-associations.ps1`

The Start Menu installer creates:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\PrintPipe\PrintPipe.lnk
```

The file association installer writes HKCU associations for mesh/media
extensions. Its open command is:

```text
"PrintPipe.exe" "%1"
```

That uses the standalone one-file document launcher instead of the old portable
ZIP's `printpipe.cmd run "%1"` path.

## Live Windows Evidence

Ran on `windows-pc` from a rebuilt standalone ZIP:

- `build-windows-standalone` returned `contains_start_menu_installer=true`,
  `contains_start_menu_uninstaller=true`,
  `contains_file_association_installer=true`, and
  `contains_file_association_uninstaller=true`
- `PrintPipe.exe --version` returned `printpipe 0.1.0`
- `PRINTPIPE_APP_DRY_RUN=1 PrintPipe.exe` printed the local web UI command
- `install-start-menu.ps1` created `PrintPipe.lnk`
- `uninstall-start-menu.ps1` removed `PrintPipe.lnk`
- `install-file-associations.ps1 -Extensions .printpipestandtest -ProgIdPrefix PrintPipeStandaloneSmoke -Force`
  created a throwaway HKCU association
- The throwaway association command was:
  `"C:\Users\sample_user\AppData\Local\Temp\printpipe-windows-standalone-live\extract\PrintPipe\PrintPipe.exe" "%1"`
- `uninstall-file-associations.ps1 -Extensions .printpipestandtest -ProgIdPrefix PrintPipeStandaloneSmoke`
  removed the throwaway association
- `PrintPipe.exe package-smoke --platform windows ... --json` returned
  `status=ok`, generated reports, and wrote a Bambu `.3mf`

## Boundary

These scripts are reversible user-scope conveniences, not a signed installer.
Windows+Bambu live slicing still waits on Bambu Studio being installed or an
explicit executable path on the Windows host.
