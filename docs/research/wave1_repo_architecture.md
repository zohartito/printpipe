# Wave 1 Repo Architecture Review

Agent: Wave 1 Agent B  
Scope: review the initial PrintPipe scaffold and propose implementation boundaries for later waves.  
Read: `README.md`, `docs/ARCHITECTURE.md`, `docs/APP_ROADMAP.md`, `src/printpipe/cli.py`, and `/Users/zohartito/Desktop/slipper_3d/RETROSPECTIVE.md`. I also skimmed the current repo tree, `docs/AGENT_WAVES.md`, and key slipper scripts to ground the boundary proposal.

## Summary

The current scaffold is a good foundation: a small `src`-layout Python package, one public CLI entrypoint, pytest, and docs that correctly define the product as a verified local reference-to-print pipeline rather than a mesh generator. The architecture doc already names the right major modules.

The biggest thing to settle before Wave 2 is not algorithms. It is contracts. Several Wave 2 agents will need to agree on artifact names, run-folder shape, stage result dataclasses, and Bambu profile/bundle ownership. Without those contracts, agents will independently invent path conventions, profile loaders, mesh stats payloads, and dependency declarations, creating merge conflicts and integration drift.

## Recommended Package Tree

Recommended near-term tree:

```text
src/printpipe/
  __init__.py
  cli.py
  contracts.py
  errors.py
  pipeline/
    __init__.py
    orchestrator.py
    gates.py
  runs/
    __init__.py
    paths.py
    manifest.py
  inputs/
    __init__.py
    media.py
    frames.py
    mesh_import.py
  meshgen/
    __init__.py
    base.py
    existing_mesh.py
    registry.py
    providers/
      __init__.py
      hunyuan.py
  mesh/
    __init__.py
    io.py
    validate.py
    repair.py
    stats.py
  geometry/
    __init__.py
    orientation.py
    bedfit.py
    transforms.py
    previews.py
  bambu/
    __init__.py
    discovery.py
    profiles/
      __init__.py
      loader.py
      inheritance.py
      enums.py
      overrides.py
      delta.py
    threemf/
      __init__.py
      core.py
      metadata.py
      bundle.py
      validate.py
    slicer.py
  reports/
    __init__.py
    receipt.py
    render_html.py
    render_markdown.py
    render_json.py
  resources/
    bambu/
      README.md
```

Recommended test tree:

```text
tests/
  fixtures/
    inputs/
    meshes/
    bambu_profiles/
    gcode/
  test_cli.py
  test_runs.py
  test_inputs.py
  test_mesh.py
  test_geometry.py
  test_bambu_profiles.py
  test_bambu_threemf.py
  test_reports.py
```

This tree intentionally separates `bambu.profiles` from `bambu.threemf`. The slipper project's `build_3mf.py` had to solve profile inheritance, Bambu-native signature metadata, project settings, object transforms, and zip packaging in one file. PrintPipe should split those seams before that code is ported.

## Module Responsibilities

`contracts.py`

- Owns small stdlib-only dataclasses and enums used between stages: `RunId`, `ArtifactRef`, `InputBundle`, `MeshArtifact`, `MeshValidation`, `PrinterSpec`, `FilamentIntent`, `ProfileBundle`, `BundleResult`, `SliceReport`, and `StageResult`.
- Imports only stdlib modules. This gives parallel agents one shared vocabulary without pulling in `trimesh`, `Pillow`, `rembg`, or Bambu-specific code.

`errors.py`

- Owns typed exceptions such as `InputError`, `ProviderError`, `MeshValidationError`, `BedFitError`, `ProfileValidationError`, `BundleValidationError`, and `SliceGateError`.
- Keeps CLI and reports from parsing arbitrary exception strings.

`cli.py`

- Stays thin: parse arguments, call `pipeline` or `runs`, print concise user-facing status, return exit codes.
- Should not import heavy optional dependencies at module import time. `printpipe --version` should keep working even if mesh/media extras are not installed.

`pipeline`

- Orchestrates stages and hard gates. It should import modules below it, but stage modules should not import `pipeline`.
- `gates.py` should centralize the architecture hard gates: topology validation after generation and repair, bed fit before bundling, enum validation before bundling, 3MF structure validation before slicing, and slice success before marking a run successful.

`runs`

- Owns immutable run-folder creation, artifact paths, manifest writes, and run status transitions.
- It should not know how to repair meshes, parse frames, or build Bambu bundles. It only provides a stable place for those artifacts to land.

`inputs`

- Accepts still images, GIFs, video, and existing mesh files.
- Emits an `InputBundle` containing original input references, extracted/cleaned frame artifacts, contact sheets, or imported mesh artifact references.
- Should not call mesh generation or Bambu code. Existing mesh import belongs here only as input normalization; topology validation still belongs in `mesh`.

`meshgen`

- Defines a provider interface and provider registry.
- Providers return generated mesh artifacts plus timing/cost/failure metadata.
- The existing-mesh provider should be first-class so the full pipeline can be tested without network or GPU dependencies.

`mesh`

- Owns mesh I/O, topology counts, repair, validation, and export.
- The slipper `pipeline/repair_mesh.py` maps naturally here. It should become reusable library functions plus a thin command wrapper only if needed.

`geometry`

- Owns object understanding: PCA axes, likely flat base, candidate orientations, support-risk scoring, scaling, bed fit, object-to-bed transforms, and preview images.
- It receives printer bed dimensions as data. It should not read Bambu profile files directly.

`bambu.profiles`

- Owns Bambu profile discovery, profile source loading, inheritance flattening, enum/source validation, material/process override rules, and settings delta generation.
- This should absorb the profile-resolution parts of the slipper `build_3mf.py`.

`bambu.threemf`

- Owns 3MF Core XML, Bambu metadata configs, package layout, Bambu-native signature fields, and static bundle validation.
- It should consume a prepared mesh artifact and a validated `ProfileBundle`; it should not decide material settings or repair meshes.

`bambu.slicer`

- Owns Bambu Studio / Bambu CLI discovery, subprocess execution, log capture, warning/error classification, gcode extraction, and slice stat parsing.
- The slipper `parse_gcode_stats.py` maps here, but slice invocation and parse/report logic should be separate functions.

`reports`

- Builds receipts from manifest and stage outputs.
- JSON receipt should be canonical. Markdown and HTML should render from the same data instead of re-deriving stage facts.

`resources`

- Holds small packaged metadata, schemas, or source snapshots only when needed. Large generated artifacts should stay out of the package.
- Bambu profile snapshots need clear provenance because installed Bambu Studio versions will drift.

## Dependency Boundaries

Preferred dependency direction:

```text
contracts/errors
  <- runs
  <- inputs / meshgen / mesh / geometry / bambu / reports
  <- pipeline
  <- cli
```

Rules:

- `contracts.py` and `errors.py` must stay stdlib-only.
- `runs` can import `contracts` and `errors`, but no media, mesh, Bambu, or report modules.
- `inputs` can use media dependencies and `contracts`; it should not import `meshgen`, `mesh`, `geometry`, or `bambu`.
- `meshgen` can depend on provider SDKs behind provider modules only. `meshgen.base` should stay light enough for tests.
- `mesh` and `geometry` can depend on `numpy`/`trimesh`; `geometry` may consume `PrinterSpec` data but should not import Bambu profile loaders.
- `bambu.profiles` should not import `bambu.threemf`; both can import `contracts`.
- `bambu.threemf` should not validate slicer enums by itself. It should require an already validated profile bundle.
- `bambu.slicer` should not mutate `.3mf` contents. It only slices and parses outcomes.
- `reports` can read run manifests and artifacts, but it should not call provider, repair, bundling, or slicing functions.
- `pipeline` is the only normal place where all stages come together.

Optional heavy dependencies should be isolated behind extras. A reasonable later split is:

```text
media: Pillow, imageio, rembg
mesh: numpy, trimesh, pymeshlab
providers: gradio_client, requests or provider SDKs
reports: jinja2, matplotlib
bambu: no heavy dependency if possible; subprocess/xml/zip/json can stay stdlib
```

## Run Artifact Boundary

Before Wave 2, define a run-folder contract so agents do not invent competing paths. Recommended shape:

```text
runs/<timestamp>-<input-stem>-<short-id>/
  manifest.json
  input/
    original/
    frames/
    selected/
    contact_sheet.png
  mesh/
    generated/
    repaired/
    oriented/
    validation/
  geometry/
    orientation_candidates.json
    bed_fit.json
    bed_fit.png
  bambu/
    profiles/
    settings_delta.json
    package.3mf
    bundle_validation.json
  slice/
    logs/
    gcode/
    slice_report.json
  reports/
    receipt.json
    receipt.md
    receipt.html
```

`manifest.json` should record stage status, artifact refs, source paths, settings intent, and errors. It should not duplicate large report payloads. Receipts can summarize it.

## Where The Current Scaffold Is Okay

- The `src` layout, hatchling config, and console script entrypoint are appropriate.
- The empty dependency list is fine for the foundation. It keeps the CLI import path clean while module boundaries are still being settled.
- `cli.py` is appropriately small. `init-run` is a useful smoke command, and its current behavior can remain while `runs` grows underneath it.
- `README.md` and `docs/ARCHITECTURE.md` correctly state the product boundary: verified Bambu-ready output, not just mesh generation.
- `docs/APP_ROADMAP.md` is sequenced well. The slipper retrospective validates the roadmap emphasis on repair, Bambu enum validation, native 3MF packaging, slice gate, and receipts.
- `tests/test_cli.py` tests public behavior instead of implementation details. Keep that style.

## What Should Change Before Wave 2

1. Define the shared contracts first.

Create or at least specify `contracts.py` before multiple agents write stage modules. The most important objects are artifact refs, mesh validation stats, profile bundle metadata, slice reports, and stage results.

2. Freeze the run-folder convention.

Wave 2 includes run folders, input processing, meshgen, repair, Bambu settings, and bundling. All of those need the same artifact paths. The run-folder contract should land before or as the first Wave 2 integration step.

3. Assign single ownership for shared files.

Only one agent should edit `cli.py`, `pyproject.toml`, `src/printpipe/__init__.py`, `docs/APP_ROADMAP.md`, and `docs/AGENT_WAVES.md` during Wave 2. Module agents should add package-local tests instead.

4. Split Bambu responsibilities before porting slipper code.

Do not port `build_3mf.py` as one module. Extract profile inheritance and enum validation into `bambu.profiles`, then extract packaging into `bambu.threemf`. The enum mismatch from the slipper project is exactly the kind of failure this boundary prevents.

5. Keep generated artifacts out of git.

Before agents run real pipelines, add ignore rules for `runs/`, large `output/` folders, caches, `.venv/`, and generated gcode/3MF/STL/GLB artifacts unless intentionally placed under `tests/fixtures`.

6. Decide dependency strategy centrally.

Do not let each module agent add dependencies to `pyproject.toml`. Agents should report required packages; an integrator should add pinned or ranged dependencies once per wave.

7. Add tiny fixtures, not full slipper outputs.

Use small generated meshes and short fixture gcode where possible. The full slipper project is valuable as a reference and later regression, but it should not become the default test payload.

## Merge Conflict Risks For Parallel Agents

High-risk files:

- `src/printpipe/cli.py`: every feature wants a command. Mitigation: keep Wave 2 CLI changes to one owner; other agents expose library functions.
- `pyproject.toml`: every module wants dependencies. Mitigation: collect dependency requests and apply them once.
- `src/printpipe/contracts.py`: shared schemas can churn. Mitigation: seed minimal contracts before Wave 2 and require additive changes only.
- `src/printpipe/__init__.py`: avoid convenience exports during early waves.
- `docs/APP_ROADMAP.md` and `docs/AGENT_WAVES.md`: let only the orchestrator update status and wave assignments.
- `tests/test_cli.py`: avoid turning it into the shared integration test pile. Add package-specific test files.

High-risk domains:

- Bambu profile handling and 3MF bundling overlap heavily. Profile loading, enum validation, settings delta, and package metadata need separate owners and explicit interfaces.
- Run artifact paths will be used by every stage. If not frozen early, agents will create incompatible assumptions.
- Mesh repair and geometry both touch `trimesh` objects and exports. Repair should output a validated mesh artifact; geometry should consume that artifact without repeating repair logic.
- Input mesh import and mesh validation can blur. Import accepts files; validation decides whether they are printable.
- Slice stats can be parsed by both `bambu.slicer` and `reports` unless the parser owns canonical `slice_report.json` and reports only render it.

Process risks:

- Multiple agents running heavy external tools can create noisy generated output and user-facing prompts. Keep Wave 2 mostly library-level and fixture-level.
- Bambu Studio version assumptions can drift. Any hardcoded signature/version/profile behavior should be isolated in `bambu` and recorded in receipts.
- Cloud mesh providers are unreliable. Provider failures should be structured stage results, not exceptions that erase the run context.

## Practical Wave 2 Ownership Map

- Run folder agent: `runs/*`, `contracts.py` additions for run/artifact refs, `tests/test_runs.py`.
- Input processing agent: `inputs/*`, small input fixtures, `tests/test_inputs.py`.
- Meshgen interface agent: `meshgen/base.py`, `meshgen/existing_mesh.py`, `meshgen/registry.py`, provider stubs, `tests/test_meshgen.py`.
- Mesh repair agent: `mesh/*`, small mesh fixtures, `tests/test_mesh.py`.
- Bambu settings agent: `bambu/profiles/*`, Bambu profile fixtures, `tests/test_bambu_profiles.py`.
- 3MF bundler agent: `bambu/threemf/*`, static bundle validation, `tests/test_bambu_threemf.py`.

The orchestrator or a designated integration agent should own `pipeline/*`, `cli.py`, and `pyproject.toml` changes after module agents land their isolated pieces.
