# Wave 101 Rule Update Packets

Status: complete for software rule-update evidence. This does not complete
physical validation or trusted-user beta.

## Problem

The beta action plan could say "update material/orientation/repair rules", but
there was no durable packet proving which rule changed, what failure caused it,
which files changed, and which tests verified the fix.

## Implementation

- Added `src/printpipe/beta/rule_updates.py`.
- Added `printpipe record-rule-update <run-root>`.
- Added `printpipe rule-update-status --runs-dir runs`.
- Added rule-update status to `build_beta_action_plan()`.
- Added a `rule_updates` readiness gate.

Each packet writes:

- `90_beta/rule_update_<type>.json`
- `90_beta/rule_update_<type>.md`

Supported rule types:

- `material`
- `orientation`
- `repair`

Supported statuses:

- `planned`
- `implemented`
- `verified`
- `reverted`

## Local Evidence Recorded

The packets below live under ignored local run folders and are not committed as
run artifacts.

| Rule type | Local run folder | Source | Verification |
| --- | --- | --- | --- |
| material | `runs/wave41-material-rule-update` | PETG/engineering material bundles defaulted to Cool Plate until material rules carried `curr_bed_type=Textured PEI Plate`. | `tests/test_materials_petg.py`, `tests/test_existing_stl_pipeline_bundle.py` |
| orientation | `runs/wave100-orientation-rule-update` | Flat bracket preview found a 45 degree bed fit, but the bundle still used the 0 degree mesh. | `tests/test_pipeline_existing_mesh.py::test_existing_mesh_pipeline_applies_bed_fit_rotation_before_bundle` |
| repair | `runs/wave100-repair-rule-update` | Cup/vase open-rim repair failed despite `allow_non_watertight=True`, and hole filling exposed the lazy `networkx` dependency. | `tests/test_mesh_repair.py::test_repair_mesh_file_allows_non_watertight_when_requested`, `tests/test_mesh_repair.py::test_repair_mesh_file_to_receipt_records_missing_networkx_from_hole_fill` |

Local status after recording:

```text
overall_status: passed
packet_count: 3
verified_rule_types: material, orientation, repair
missing_rule_types: []
```

## Verification

```bash
.venv/bin/pytest tests/test_beta_rule_updates.py tests/test_beta_plan.py tests/test_beta_readiness.py
.venv/bin/pytest tests/test_cli_readiness.py tests/test_release_status.py tests/test_web_server.py tests/test_cli.py
```

## Boundary

Rule-update packets are software evidence. They do not prove that a physical
PLA/PETG/TPU print passed, that trusted users accepted the app, or that signed
distribution credentials exist.
