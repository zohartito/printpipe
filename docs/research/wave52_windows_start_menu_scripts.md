# Wave 52 - Windows Start Menu Scripts

## Question

Can the portable Windows ZIP offer a simple launcher installation path without
pretending to be a signed installer?

## Change

The Windows portable ZIP now includes:

- `PrintPipe/install-start-menu.ps1`
- `PrintPipe/uninstall-start-menu.ps1`

The installer creates a user-scope shortcut:

`%APPDATA%\Microsoft\Windows\Start Menu\Programs\PrintPipe\PrintPipe CLI.lnk`

The shortcut opens `printpipe.cmd` in a persistent Command Prompt. The
uninstaller removes the shortcut and the empty `PrintPipe` Start Menu folder.

## Boundary

This is not an MSI/EXE installer, not signed, and not a file-association
registration flow. It is a reversible convenience script for beta testers using
the portable ZIP.

## Live Windows Smoke

The scripts were run on `windows-pc` from an expanded portable ZIP:

- `install-start-menu.ps1` printed the created shortcut path:
  `C:\Users\sample_user\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\PrintPipe\PrintPipe CLI.lnk`
- A Python path check confirmed the `.lnk` existed after install.
- `uninstall-start-menu.ps1` removed the shortcut.
- A second Python path check reported `SHORTCUT_EXISTS_AFTER_UNINSTALL=false`.
