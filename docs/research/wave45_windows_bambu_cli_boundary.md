# Wave 45 - Windows Bambu CLI Boundary

Date: 2026-05-28

## Goal

After proving the `printpipe.pyz` artifact runs on Windows, check whether the
same host can also run a live Bambu Studio CLI slice.

## Commands

Common install candidates:

```powershell
$candidates = @(
  "$env:ProgramFiles\Bambu Studio\bambu-studio.exe",
  "$env:ProgramFiles\Bambu Studio\BambuStudio.exe",
  "$env:ProgramFiles\BambuStudio\bambu-studio.exe",
  "$env:LOCALAPPDATA\Programs\Bambu Studio\bambu-studio.exe"
)
foreach ($p in $candidates) {
  if (Test-Path $p) { Write-Output $p }
}
```

Broader search:

```powershell
Get-ChildItem -Path $env:ProgramFiles,$env:LOCALAPPDATA -Filter BambuStudio.exe -Recurse -ErrorAction SilentlyContinue |
  Select-Object -First 20 -ExpandProperty FullName
```

## Result

No Bambu Studio executable was found on `desktop-zt`.

## Boundary

Windows zipapp package smoke is verified, but Windows live Bambu CLI slicing
cannot be verified on this host until Bambu Studio is installed or an explicit
executable path is provided.
