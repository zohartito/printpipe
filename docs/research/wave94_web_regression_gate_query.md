# Wave 94 - Web Regression Gate Query

Status: complete.

## Why

Wave 92 and Wave 93 made regression manifests available to the CLI readiness
and release-status gates. The local web JSON endpoints still returned only the
default no-manifest reports, so browser automation and other local agents could
not ask the API surface to include beta regression drift.

## What Changed

- `/readiness.json?regression_manifest=<path>` now forwards the path to
  `build_beta_readiness_report()`.
- `/release-status.json?regression_manifest=<path>` now forwards the path to
  `build_release_status_report()`.
- Blank or omitted query values preserve the existing default behavior.

## Boundary

The home page still renders the default no-manifest readiness and release
panels. Callers must explicitly request JSON with a manifest path when they
want regression drift to participate in the local web/API gate.

## Verification

- Red check first: focused web endpoint tests failed because both endpoints
  ignored the query string.
- Green check: focused web endpoint tests passed after implementation.
