# Wave 84 - Release Distribution Gates

## Question

Can `printpipe release-status` say the release is blocked by final distribution
requirements even when `verify-release` says the release folder is internally
consistent?

## Change

Wave 84 adds two release-artifact gates:

- `macos_distribution`
- `windows_distribution`

The macOS gate is `ready` only when the release manifest contains a
`macos_dmg` artifact with:

- `signed=true`
- `notarized=true`

The Windows gate is `ready` only when the release manifest contains a
`windows_installer` artifact with:

- `signed=true`

`release-status` can read artifact metadata from an injected verification
payload during tests or from `release_manifest.json` during real CLI use.

## Boundary

These are reporting gates. They do not sign, notarize, install tooling, or
modify the release folder. The current local release bundle can verify cleanly
while these distribution gates remain action-required.
