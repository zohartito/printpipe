# Wave 50 - macOS DMG Distribution

## Question

Can PrintPipe produce a real macOS drag-install distribution artifact instead of
only a loose `.app` bundle?

## Change

Added `printpipe build-macos-dmg`, backed by
`printpipe.packaging.macos_dmg.build_macos_dmg_package()`.

The builder:

1. creates a temporary staging folder;
2. builds `PrintPipe.app` into that staging folder;
3. adds an `Applications` symlink;
4. calls `hdiutil create -format UDZO`;
5. returns JSON metadata about the DMG, signing state, and boundary claims.

## Verification

The focused packaging tests create a real `.dmg` when `hdiutil` is available and
validate it with `hdiutil imageinfo`.

## Boundaries

This is still not Developer ID signing, notarization, or Python-runtime
bundling. It is a concrete distribution artifact that can be handed to a tester,
with the current macOS security limitations stated explicitly.
