# Wave 1 Integration Summary

Status: complete

Wave 1 converted the product brainstorm into buildable constraints before Wave 2 implementation starts. The key outcome is that PrintPipe should not jump straight into feature code until it has shared contracts for runs, artifacts, providers, mesh stats, Bambu profiles, and receipts.

## Outputs

- `wave1_requirements.md`: defines v1 goal, non-goals, one-shot meaning, user flow, acceptance criteria, failure criteria, and receipt proof requirements.
- `wave1_repo_architecture.md`: recommends package boundaries and warns that Wave 2 needs shared contracts before agents implement modules in parallel.
- `wave1_slipper_extraction.md`: identifies reusable slipper proof-of-concept code and the slipper-specific assumptions to remove.
- `wave1_bambu_schema.md`: captures Bambu-native 3MF, profile inheritance, enum validation, GUI/CLI transform, and macOS profile path requirements.
- `wave1_meshgen_providers.md`: defines mesh generation as a provider interface, not the product boundary.
- `wave1_validation_strategy.md`: defines gates, fixtures, and regression policy.

## Decisions

1. Keep v1 local-first.
2. Keep Bambu-only at launch.
3. Treat meshgen as a swappable provider.
4. Treat slice verification as the success boundary.
5. Build shared contracts before Wave 2 modules.
6. Port mesh repair first, then Bambu profile/3MF logic, then orientation/bed fit and slice parsing.

## Roadmap Updates

- Phase 0 remains complete.
- Phase 1 remains complete.
- Phase 2 items 16-18 are complete because Wave 1 inventoried the slipper scripts, identified reusable parts, and listed slipper-specific assumptions to remove.
- Phase 2 items 19-23 remain pending because code has not yet been ported.

## Wave 2 Gate

Before the six Wave 2 implementation agents start, the orchestrator should add shared contracts for:

- run IDs and run folder paths
- artifact names
- stage result payloads
- mesh topology stats
- provider request/result objects
- Bambu profile identifiers
- receipt JSON shape

This reduces merge conflicts and prevents each module from inventing its own data model.

Status: partially satisfied by `src/printpipe/contracts.py` and `src/printpipe/runs/paths.py`. Wave 2 agents should use those shared contracts instead of inventing new run IDs, artifact kinds, mesh stat payloads, or stage statuses.
