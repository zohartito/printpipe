# Wave 56 - macOS Signing Readiness Doctor

## Question

Can PrintPipe tell whether this Mac is actually ready for Developer ID signing
and notarization, instead of only saying the app is not signed?

## Change

Added `printpipe.env.macos.macos_signing_readiness()` and surfaced its packet in
`printpipe doctor`.

The readiness packet checks:

- `codesign`
- `productbuild`
- `security`
- `notarytool` through `xcrun --find notarytool` when needed
- `Developer ID Application` identities
- `Developer ID Installer` identities

`printpipe doctor --json` now includes this under `system.signing`, and the
human doctor report renders the status plus missing tools/identities.

## Live Boundary

On Zohar's current Mac, the signing tools are available, but
`security find-identity -v -p codesigning` reports zero valid identities. Final
Developer ID signing/notarization remains blocked until Apple Developer
certificates/credentials are installed.
