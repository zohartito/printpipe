# Wave 153 - macOS Notarization Verification Honesty

## Question

Can a hand-edited release manifest claim a macOS DMG is Developer ID signed and
notarized without `verify-release` checking local signing/notarization evidence?

## Finding

The Opus audit flagged an S4 false-evidence path: a manifest could set a
`macos_dmg` artifact to `signed=true`, `notarized=true`, and
`signing_kind=developer_id_application` while keeping matching size and SHA-256
metadata. Before this wave, `verify-release` accepted that as `ok`; the release
status layer then treated the macOS distribution gate as ready from the manifest
claim alone.

## Change

- `verify-release` now validates any `notarized=true` macOS DMG claim.
- On macOS, the verifier runs `codesign --verify --deep --strict <dmg>` before
  `xcrun stapler validate <dmg>`.
- If the platform or required tools cannot verify the claim, the verifier fails
  with `artifact_notarization_verify:macos_dmg`.
- The release-status distribution gates now require the underlying release
  verifier to be `ok` before marking macOS notarization or Windows installer
  signing ready.

## Verification

```bash
.venv/bin/pytest \
  tests/test_packaging_release.py::test_verify_release_bundle_rejects_unverifiable_notarized_macos_dmg \
  tests/test_release_status.py::test_release_status_report_rejects_unverified_macos_notarization -q
```

Result: `2 passed`.

## Boundary

This is evidence hardening only. It does not install Apple Developer
certificates, configure a notarytool profile, or notarize a DMG. The macOS
distribution gate still requires real Developer ID signing and stapler-verifiable
notarization evidence.
