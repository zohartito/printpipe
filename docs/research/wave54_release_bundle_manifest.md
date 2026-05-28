# Wave 54 - Release Bundle Manifest

## Question

Can PrintPipe produce one local release folder with the current macOS, Windows,
and portable Python handoff artifacts plus integrity metadata?

## Change

Added `printpipe build-release`, backed by
`printpipe.packaging.release.build_release_bundle()`.

The command builds:

- `printpipe.pyz`
- `PrintPipe.dmg`
- `PrintPipe-Windows-portable.zip`
- `release_manifest.json`

The manifest records each artifact's relative path, size, SHA-256 checksum,
signing/notarization status, and whether it bundles Python or Bambu Studio.

## Boundary

The release bundle is a handoff folder, not a claim that final distribution is
complete. It still records the remaining boundaries: no bundled Python, no
bundled Bambu Studio, no Developer ID notarization, no signed Windows installer,
and physical print validation living in separate run evidence packets.
