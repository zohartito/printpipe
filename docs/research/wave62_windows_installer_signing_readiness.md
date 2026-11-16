# Wave 62 - Windows Installer Signing Readiness Doctor

## Question

Can PrintPipe tell the truth about whether a Windows host is ready to build and
sign a native installer?

## Implementation

Added `windows_installer_signing_readiness()` in `printpipe.env.windows`.

It checks for:

- `signtool`
- `powershell`
- at least one installer tool from `wix/iscc/makensis`
- code-signing certificates in `Cert:\CurrentUser\My`

`printpipe doctor --json` now includes the packet under `system.signing` for
Windows reports. The human doctor renderer labels it as `Windows installer
signing`.

## Live Windows Evidence

Ran on `windows-pc` from a fresh source export:

```powershell
printpipe doctor --json
```

Observed:

- `system.signing.status=missing_tools`
- PowerShell available:
  `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.EXE`
- `signtool` missing
- installer tool group `wix/iscc/makensis` missing
- `Code Signing Certificate` missing
- `bambu_studio.installed_count=0`

## Boundary

The Windows portable and standalone ZIPs remain usable unsigned test artifacts.
A signed Windows installer still requires installing signing/installer tools and
a code-signing certificate on the Windows host. Live Windows+Bambu slicing also
still requires Bambu Studio to be installed or an explicit executable path.
