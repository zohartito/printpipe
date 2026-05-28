# Wave 81 - Combined Release Status Command

## Question

What should an agent or release script run when it needs one answer to:

- Is the release folder intact?
- Are the beta/readiness gates clear?
- What is the next thing blocking a strict handoff?

## Change

Wave 81 adds `printpipe release-status`:

```bash
printpipe release-status --release-dir dist/release --runs-dir runs --strict
printpipe release-status --release-dir dist/release --runs-dir runs --json
```

The command combines:

- `verify_release_bundle()` for the release-folder integrity gate
- `build_beta_readiness_report()` for physical, dependency, Bambu, filesystem,
  and signing gates

The JSON payload includes:

- `overall_status`
- `action_required_count`
- `release_dir`
- `runs_dir`
- ordered `gates`
- deduplicated `next_actions`
- nested `release_verification`
- nested `readiness`

## Boundary

This command is read-only. It does not build a release folder, sign or notarize
packages, install Windows signing tools, install Bambu Studio on Windows, or
record physical print evidence.
