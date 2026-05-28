# Wave 117 - Release Distribution Handoff and Evidence Hardening

## Purpose

The final release gate already had status and action-plan commands, but it did not have the same operational handoff pattern as physical validation and trusted-user beta. Two evidence gates also allowed over-trusting hand-edited packets: a physical packet could point at a nonexistent photo, and a trusted-user packet could claim a completed outcome without any report or attached artifact.

## What changed

- Added `printpipe release-start`.
- Added `start_release_distribution_handoff()` in `printpipe.packaging.release_plan`.
- `release-start --json` returns:
  - `handoff_markdown_path`
  - `release_status_command`
  - `final_plan_command`
  - `action_count`
- Non-JSON `release-start` prints the same release handoff and check commands.
- `release-plan` now includes a `start_command` on release actions.
- `release-plan` surfaces `handoff_markdown_path` when a release handoff exists.
- The home-page release distribution panel renders release start commands and handoff paths.
- Physical validation status now requires printed evidence photo artifacts to exist on disk.
- Trusted-user beta status now requires completed packets to have supporting evidence: either an existing run report or at least one existing attached artifact file.

## Local evidence generated

Ignored local handoff sheet:

- `dist/release_handoffs/release_distribution_handoff.md`

## Verification

- `pytest tests/test_release_status.py::test_release_distribution_start_writes_handoff_without_signed_evidence tests/test_release_status.py::test_release_start_parser_accepts_dirs_json_and_regression_manifest tests/test_release_status.py::test_cli_release_start_prints_handoff_json tests/test_web_server.py::test_home_response_renders_release_distribution_plan -q`
- `printpipe release-start --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json --json`
- `printpipe release-plan --release-dir dist/release --runs-dir runs --regression-manifest regressions/dogfood_failures.json`

## Boundary

The release handoff is not signed distribution evidence. Physical photo existence checks do not prove print quality. Trusted-user supporting evidence checks do not prove satisfaction. The remaining gates still require real physical print evidence, completed trusted-user packets, Developer ID notarization, and a signed Windows installer.
