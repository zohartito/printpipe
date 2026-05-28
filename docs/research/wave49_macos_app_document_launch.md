# Wave 49 - macOS App Document Launch

## Question

Can the generated macOS app participate in the normal "Open With" flow for
PrintPipe inputs?

## Finding

Before this wave, passing a file path to `Contents/MacOS/printpipe` fell through
to argparse as an unknown command. The app also did not declare document types in
`Info.plist`.

## Change

The app bundle now declares `CFBundleDocumentTypes` for common PrintPipe input
extensions:

- mesh and bundle inputs: `stl`, `obj`, `3mf`, `glb`, `gltf`
- image inputs: `png`, `jpg`, `jpeg`, `gif`, `webp`
- video inputs: `mp4`, `mov`

When launched with exactly one file argument, the launcher:

1. creates `~/PrintPipe/runs` if needed;
2. runs `printpipe run <file>` using the packaged zipapp;
3. starts the same local web UI at `http://127.0.0.1:8765/`.

`PRINTPIPE_APP_DRY_RUN=1` covers this path without creating a run or starting a
blocking web server.

## Boundaries

This is alternate document-type support inside the app bundle. It does not
register PrintPipe as the default handler, and it does not replace signed,
notarized installer work.
