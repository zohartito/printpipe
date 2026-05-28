# Wave 152 - Windows Installer Signing Honesty

## Question

Can `build-release --windows-installer-exe` or a hand-edited release manifest claim a signed Windows installer without real Authenticode verification?

## Finding

The Opus audit flagged an S4 false-evidence path: copying any `.exe` with
`--windows-installer-exe` synthesized `signed=true` and `signing_kind=authenticode`.
That let a release manifest say the Windows installer was signed without running
`signtool`.

There was a second related path: `verify-release` rejected honest
`signed=false` Windows installer metadata, but accepted `signed=true` metadata
without checking an Authenticode signature.

## Change

- Record copied prebuilt Windows installers as `signed=false` by default.
- Remove synthesized `signing_kind=authenticode` from copied installer metadata.
- Keep the Windows release boundary open unless a Windows installer artifact has
  `signed=true`.
- Let `verify-release` accept honest unsigned installer metadata as a valid
  release record.
- Make `verify-release` fail a `signed=true` Windows installer claim unless
  `signtool verify /pa <installer>` can run and pass.
- Update README, packaging docs, and CLI help to state that copying
  `PrintPipeSetup.exe` is not signing proof.

## Verification

```bash
.venv/bin/pytest \
  tests/test_packaging_release.py::test_build_release_bundle_can_include_prebuilt_windows_installer \
  tests/test_packaging_release.py::test_verify_release_bundle_accepts_honest_unsigned_windows_installer_metadata \
  tests/test_packaging_release.py::test_verify_release_bundle_rejects_unverifiable_signed_windows_installer \
  tests/test_release_status.py::test_release_status_report_blocks_on_unsigned_distribution_artifacts -q
```

Result: `4 passed`.

## Boundary

This is evidence hardening only. It does not install Windows signing tools, create
a code-signing certificate, or produce a signed installer. The Windows
distribution gate still requires real Authenticode signing evidence.
