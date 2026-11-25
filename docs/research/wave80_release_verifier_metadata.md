# Wave 80 - Release Verifier Metadata Hardening

## Question

Can a release folder pass `printpipe verify-release` while carrying artifact
metadata that contradicts what the artifact is supposed to be?

## Finding

Before this wave, `verify-release` validated:

- `release_manifest.json` existence and JSON syntax
- boundary text drift
- artifact path containment
- artifact existence
- artifact size
- artifact SHA-256

That was enough to catch tampered bytes, but not enough to catch a manifest that
included hash-correct native artifacts with impossible or misleading metadata.
Examples:

- a `windows_installer` artifact with `signed=false`
- a `windows_installer` artifact pointing at a `.zip`
- a `macos_dmg` artifact claiming `notarized=true` while `signed=false`

## Change

Wave 80 adds type-specific metadata checks inside `verify-release`:

- `zipapp`: path ends in `.pyz` and does not claim a bundled Python runtime
- `macos_dmg`: path ends in `.dmg`; notarized DMGs must also be signed
- `macos_standalone_zip`: path ends in `.zip`, bundles Python, does not bundle
  Bambu Studio
- `windows_portable`: path ends in `.zip` and does not claim a bundled Python
  runtime
- `windows_standalone_zip`: path ends in `.zip`, bundles Python, does not
  bundle Bambu Studio
- `windows_installer`: path ends in `.exe`, is signed, bundles Python, does not
  bundle Bambu Studio

## Boundary

This is verifier hardening only. It does not produce real signing credentials,
notarize a macOS package, install Windows signing tools, build a signed Windows
installer on `windows-pc`, or record physical print evidence.
