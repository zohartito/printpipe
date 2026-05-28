# Wave 78 - macOS Developer ID Signing Plumbing

## Goal

Move original item 121 closer to completion by wiring real macOS Developer ID signing and notarization commands into PrintPipe packaging, while keeping the credential boundary honest.

## What Changed

- Added `sign_macos_path()` for `codesign --force --deep --options runtime --timestamp --sign ...` plus verification.
- Added `notarize_macos_artifact()` for `xcrun notarytool submit --wait --output-format json` plus `xcrun stapler staple`.
- Added `--developer-id-identity` to `printpipe build-macos-app`.
- Added `--developer-id-identity` and `--notary-profile` to `printpipe build-macos-dmg`.
- Added the same Developer ID/notary options to `printpipe build-release`.
- Release manifests now distinguish a genuinely notarized macOS DMG from the unsigned boundary.

## Boundary

This wave does not install Apple Developer certificates, create a notary keychain profile, or notarize a real artifact on Zohar's machine. The readiness gate remains action-required until those credentials exist and a real signed/notarized build is produced.
