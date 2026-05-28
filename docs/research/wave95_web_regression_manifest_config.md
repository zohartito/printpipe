# Wave 95 - Web Regression Manifest Configuration

Status: complete.

## Why

Wave 94 added query-string support for regression manifests on the local JSON
endpoints. That helped browser and agent automation, but the normal local web
app still started with no manifest configured. The home-page readiness and
release panels therefore stayed blind to regression drift unless the caller
manually edited JSON URLs.

## What Changed

- Added `printpipe serve --regression-manifest <manifest>`.
- Threaded the configured manifest through `PrintPipeWebApp`, `create_app()`,
  and `serve()`.
- Home-page readiness and release-status panels now include the configured
  manifest.
- `Readiness JSON` and `Release status JSON` service links include the manifest
  query when configured.
- Explicit endpoint query parameters still override the configured manifest for
  one-off checks.

## Boundary

This wave does not create beta failures, physical print evidence, signed
packages, Apple Developer credentials, or Windows signing certificates. It
keeps the local browser UI aligned with the regression gates that already exist
in the CLI and JSON endpoints.

## Verification

- Red check first: focused serve/web tests failed because the parser, app
  factory, and home panels had no configured manifest support.
- Green check: focused serve/web tests passed after implementation.
