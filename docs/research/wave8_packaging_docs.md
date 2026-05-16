# Wave 8 Packaging Docs Notes

Status: documentation foundation for Wave 8 Agent F.

## Scope

Files added:

- `docs/PACKAGING.md`
- `docs/TROUBLESHOOTING.md`

No code, CLI, roadmap, `AGENT_WAVES`, or top-level Markdown files were changed.

## Sources Read

- `README.md`
- `pyproject.toml`
- `src/printpipe/cli.py`
- `src/printpipe/pipeline/__init__.py`
- `src/printpipe/mesh/repair.py`
- `src/printpipe/bambu/profiles/sources.py`
- `docs/ARCHITECTURE.md`
- `docs/AGENT_WAVES.md`
- `docs/research/wave1_bambu_schema.md`
- `docs/research/wave1_requirements.md`
- `docs/research/wave4_integration_summary.md`
- `docs/research/wave5_existing_stl_pipeline.md`
- `docs/research/wave7_integration_summary.md`

## Decisions Captured

- Packaging is documented as a v1 plan/foundation, not as a completed
  installer.
- macOS and Windows packages should wrap the same `printpipe` entry point and
  should not bundle Bambu Studio.
- `printpipe serve` is included as a first-class local command with host, port,
  and runs-dir examples.
- Missing optional dependencies should not break base CLI diagnosis commands.
- Bambu Studio absence means a run cannot be called slice-verified.
- The updater is explicitly later work and not v1.

## Bambu Path Expectations

macOS profile expectations reuse the prior schema research:

```text
/Applications/BambuStudio.app/Contents/Resources/profiles/BBL/
~/Library/Application Support/BambuStudio/user/
```

User presets prefer a numeric `user/<numeric_user_id>/` directory and fall back
to `user/default/`. Preset subdirectories are `filament/`, `process/`, and
`machine/`.

Windows expectations are intentionally documented as detector candidates until a
Windows smoke test confirms the exact tree:

```text
C:\Program Files\Bambu Studio\
%APPDATA%\BambuStudio\user\
```

The docs avoid promising automatic preset writes on Windows until those paths are
verified.

## Honest Current State

The current app has a dependency-light CLI, run folders, reports, local web
server, profile source helpers, optional mesh repair, Bambu 3MF helpers, and
slicer classification utilities. It does not yet have a finished packaged
installer or a full live UI-submitted pipeline.

The docs therefore use smoke checks and troubleshooting guidance rather than
release notes for a package that does not exist yet.
