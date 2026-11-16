# printpipe — local-first reference-to-print pipeline: image/GIF/video/prompt/mesh → repaired, oriented, bed-fit mesh → Bambu printer+filament profiles → Bambu-native `.3mf` → slice report → run receipt.

## Run & test
- Dev setup: `python -m venv .venv && source .venv/bin/activate && python -m pip install -e ".[dev,mesh-repair]"`.
- The mesh-repair extra includes the 3MF XML loader; missing loaders produce repair receipts and a failed non-STL run report.
- Automatic run IDs retry collisions with an atomic numeric suffix; explicit IDs still reject existing folders.
- CLI entry point: `printpipe --version` (`printpipe.cli:main`).
- Native macOS packaging checks explicitly skip missing tools; a dedicated macOS CI job verifies them with codesign/hdiutil.
- Intent tests select committed profile fixtures; CI installs dev and mesh-repair extras.
- Tests: `pytest` (testpaths = `tests`, ~105 test files). No lint config committed.
- End-to-end run: `printpipe run input.stl --runs-dir runs --material "PLA" --slice` (also `--prompt`, `--printer`, `--use-case`).
- `physical-slice` returns exit 2 and top-level failed status if its slice receipt fails.
- Health gates: `printpipe doctor`, `printpipe readiness`, `printpipe final-plan`, `printpipe final-next`.
- After configuring, review the command and set `PRINTPIPE_CONFIG_PATH` (or opt into project trust) before smoke/run.
- Media meshgen smoke: `printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke`.
- MCP path roots come from startup `PRINTPIPE_MCP_INPUT_ROOT`/`PRINTPIPE_MCP_OUTPUT_ROOT`; the supplied registration confines inputs/outputs and rejects symlinks below these roots.
- MCP slicer server (stdio): `.venv/bin/python -m printpipe.mcp_server`.

## Structure
- `src/printpipe/` — package; `cli.py`, `pipeline/`, `contracts.py` (stage status), `config.py`, subpackages `bambu/` (`slicer.py` CLI slice gate, `profiles/`, `threemf/`), `mesh/`, `meshgen/`, `geometry/`, `materials/`, `inputs/`, `fabrication/`, `reports/`, `runs/`, `beta/`, `calibration/`, `packaging/`, `web/` (read-only status app).
- `mcp_server.py` — dependency-free stdio JSON-RPC MCP server (`get_slice_settings`, `slice_with_settings`) exposing the Bambu slicer keyspace.
- `.mcp.json` — registers that server as `printpipe-slicer` so the harness drives slicing as MCP tools (portable `python3 tools/mcp_launcher.py`, preferring this checkout's `.venv`, otherwise the active interpreter).
- `docs/APP_ROADMAP.md` + `docs/AGENT_WAVES.md` — 142-item execution map; `runs/` — per-run receipts (artifacts, logs, settings delta, slice outcome).

## Conventions & danger zones
- Open shells may retain boundary edges, but unresolved non-manifold edges fail repair.
- Run reports record the serialized Generic PLA baseline-to-final settings delta, with material/user override reasons.
- `--printer` labels reports/checklists only; bundles use P2S 0.4 mm profiles regardless of the label.
- The P2S XYZ envelope is enforced before bundling; oversized geometry requires an explicit source/edit scale change.
- The Bambu CLI slice gate (`bambu/slicer.py`, `--slice`) requires an external Bambu Studio executable via `PRINTPIPE_BAMBU_STUDIO_CLI` (or `BAMBU_STUDIO_CLI`/`_EXECUTABLE`); without it, slicing skips/fails honestly rather than faking a receipt. Never fabricate slice or meshgen receipts.
- Runs fail *honestly* at `meshgen` / `prompt_reference_generation` when no provider is configured. The media readiness gate checks successful smoke receipts and output existence only; it does not validate geometry or current-provider provenance.
- `.printpipe/config.json` (provider command + workflow params) is deliberately git-ignored — do not commit it or any provider secrets (`OPENAI_API_KEY`, `HF_TOKEN`, etc. stay in env).
- Prompt-image HTTP failure receipts keep only numeric status/error type, excluding provider bodies that may echo credentials.
- OpenAI prompt-image runs enforce a pre-call cost cap (`PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD`) and fail before the API call if the estimate is missing or over cap.
- Packaged web assets use archive-aware resources; package smoke checks JS/CSS routes.
- Viewer conversion rejects paths outside the run and symlinks, and publishes its GLB cache atomically.
- Loopback HTTP requires the bound port with Host 127.0.0.1/localhost and rejects foreign/null Origin headers.
- The web app is read-only by design (all POST routes reject before body processing, including edits, evidence, handoffs and folder opening). Keep configuration on the CLI. License is AGPL-3.0-or-later. Python ≥3.11.

- Windows association helpers save prior default values/types; uninstall only restores/removes the default and PrintPipe ProgID, preserving extension subkeys.

## Loops (loop map #29)
- **EVENT watch-folder:** `tools/watch_3mf_queue.py` — a new `.3mf` in the inbox
  is validated (`validate_bundle`), then sliced via `run_bambu_cli_slice_stage`
  (behind the same Bambu CLI gate the pipeline uses — env
  `PRINTPIPE_BAMBU_STUDIO_CLI`/fallbacks or a discovered install; no CLI =
  `skipped_gate_closed`, never a fake receipt), then appended to a queue report
  (schema `printpipe.watch_queue.v1`). Idempotent via a content-hash state file;
  `--max-files` caps a run. Reuses the library only — no pipeline code changed.
  - Dry-run: `python3 tools/watch_3mf_queue.py --dry-run`
  - Generate the launchd plist from this checkout and an explicitly configured slicer:
    `python tools/generate_watch_plist.py --bambu-cli /absolute/path/to/BambuStudio`
    Then, when ready to enable watching, load the generated file:
    `launchctl bootstrap gui/$(id -u) "$(pwd)/runs/inbox-watch/com.printpipe.watch.plist"`.
    Generation does not load launchd or invoke the slicer. Inbox/state/report live under `runs/` (gitignored).
    State, report and log go in `runs/inbox-watch/`, never the inbox: any write
    there re-fires `WatchPaths` (until 2026-10-22 it re-ran itself every ~10 s).
  - Learnings append to `.claude/LEARNINGS.md`.

## Agent rules (all harnesses)
- Determinism boundary: anything that must be EXACT (money, geometry, safety limits, scoring, pricing) lives in code; the model only orchestrates and judges.
- Keep this file current: when you change how this repo is run, tested, or structured, update AGENTS.md in the same commit. Keep it under ~150 lines.
