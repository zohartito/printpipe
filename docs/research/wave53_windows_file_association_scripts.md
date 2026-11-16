# Wave 53 - Windows File Association Scripts

## Question

Can the portable Windows ZIP optionally register PrintPipe for mesh inputs while
staying reversible and avoiding existing user handlers by default?

## Change

The portable ZIP now includes:

- `PrintPipe/install-file-associations.ps1`
- `PrintPipe/uninstall-file-associations.ps1`

The installer defaults to `.stl`, `.obj`, `.3mf`, `.glb`, and `.gltf`. It writes
under `HKCU:\Software\Classes`, creates `PrintPipe.<extension>` ProgIDs, and
sets the open command to run:

`printpipe.cmd run "%1" --runs-dir "%USERPROFILE%\PrintPipe\runs"`

## Safety

The installer skips an extension if it already has a non-PrintPipe handler,
unless the operator passes `-Force`. The uninstaller only removes extension
ownership when the extension currently points at the matching PrintPipe ProgID.

## Live Smoke

The scripts were run on `windows-pc` with a throwaway `.printpipetest`
extension and `PrintPipeSmoke` ProgID prefix. Install created the HKCU
association:

- `ASSOC_VALUE=PrintPipeSmoke.printpipetest`
- `COMMAND_VALUE="...\PrintPipe\printpipe.cmd" run "%1" --runs-dir "%USERPROFILE%\PrintPipe\runs"`
- `ASSOC_EXISTS_AFTER_UNINSTALL=false`

Real `.stl`/`.3mf` associations were not touched during smoke verification.
