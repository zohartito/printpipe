# printpipe — local-first reference-to-print pipeline: image/GIF/video/prompt/mesh → repaired, oriented, bed-fit mesh → Bambu printer+filament profiles → Bambu-native `.3mf` → slice report → run receipt.

## Run & test
- Dev setup: `python -m venv .venv && source .venv/bin/activate && python -m pip install -e ".[dev,mesh-repair]"`.
- CLI entry point: `printpipe --version` (`printpipe.cli:main`).
- Tests: `pytest` (testpaths = `tests`, ~105 test files). No lint config committed.
- End-to-end run: `printpipe run input.stl --runs-dir runs --material "PLA" --slice` (also `--prompt`, `--printer`, `--use-case`).
- Health gates: `printpipe doctor`, `printpipe readiness`, `printpipe final-plan`, `printpipe final-next`.
- Media meshgen smoke: `printpipe media-meshgen-smoke reference.png --runs-dir runs/media-meshgen-smoke`.
- MCP slicer server (stdio): `.venv/bin/python -m printpipe.mcp_server`.

## Structure
- `src/printpipe/` — package; `cli.py`, `pipeline/`, `contracts.py` (stage status), `config.py`, subpackages `bambu/` (`slicer.py` CLI slice gate, `profiles/`, `threemf/`), `mesh/`, `meshgen/`, `geometry/`, `materials/`, `inputs/`, `fabrication/`, `reports/`, `runs/`, `beta/`, `calibration/`, `packaging/`, `web/` (read-only status app).
- `mcp_server.py` — dependency-free stdio JSON-RPC MCP server (`get_slice_settings`, `slice_with_settings`) exposing the Bambu slicer keyspace.
- `.mcp.json` — registers that server as `printpipe-slicer` so the harness drives slicing as MCP tools (runs the repo's own `.venv` Python).
- `docs/APP_ROADMAP.md` + `docs/AGENT_WAVES.md` — 142-item execution map; `runs/` — per-run receipts (artifacts, logs, settings delta, slice outcome).

## Conventions & danger zones
- The Bambu CLI slice gate (`bambu/slicer.py`, `--slice`) requires an external Bambu Studio executable via `PRINTPIPE_BAMBU_STUDIO_CLI` (or `BAMBU_STUDIO_CLI`/`_EXECUTABLE`); without it, slicing skips/fails honestly rather than faking a receipt. Never fabricate slice or meshgen receipts.
- Runs fail *honestly* at `meshgen` / `prompt_reference_generation` when no provider is configured. A media provider only satisfies the readiness gate after a real `media-meshgen-smoke` receipt exists.
- `.printpipe/config.json` (provider command + workflow params) is deliberately git-ignored — do not commit it or any provider secrets (`OPENAI_API_KEY`, `HF_TOKEN`, etc. stay in env).
- OpenAI prompt-image runs enforce a pre-call cost cap (`PRINTPIPE_PROMPT_IMAGE_MAX_COST_USD`) and fail before the API call if the estimate is missing or over cap.
- The web app is read-only by design (no web run-creation, provider config, uploads, or re-slice). Keep configuration on the CLI. License is Proprietary. Python ≥3.11.

## Agent rules (all harnesses)
- Determinism boundary: anything that must be EXACT (money, geometry, safety limits, scoring, pricing) lives in code; the model only orchestrates and judges.
- Keep this file current: when you change how this repo is run, tested, or structured, update AGENTS.md in the same commit. Keep it under ~150 lines.
