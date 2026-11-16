# Wave 79 - Windows Native Installer Plumbing

## Goal

Move original item 122 closer to completion by adding real Windows native installer build/sign command plumbing without claiming the missing Windows tools or certificate exist.

## What Changed

- Added `build_windows_installer_package()`.
- The builder takes a prebuilt `PrintPipe-Windows-standalone.zip`.
- It writes an Inno Setup `.iss` script and invokes `iscc`.
- It can Authenticode-sign the resulting installer with `signtool sign /n ...`.
- Added `printpipe build-windows-installer`.
- Added `build-release --windows-installer-exe` so a prebuilt installer can be included in the checksummed release bundle. Wave 152 later corrected this path so copied installers are not treated as signed unless Authenticode verification actually passes.

## Boundary

This wave does not install Inno Setup, WiX, NSIS, Windows SDK `signtool`, or a code-signing certificate. On `windows-pc`, Windows installer readiness remains action-required until those tools and identities are present and a real signed installer is built.
