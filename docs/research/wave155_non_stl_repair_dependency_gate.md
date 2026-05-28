# Wave 155 - Non-STL Repair Dependency Gate

## Question

Can PrintPipe fail non-STL mesh imports at the repair/dependency boundary instead
of letting them reach the ASCII STL orientation path?

## Finding

The existing pipeline could import an OBJ/GLB/3MF, receive a skipped repair
receipt when optional mesh-repair dependencies were unavailable, and then fall
back to the original non-STL file for orientation. That produced the lower-level
message `only ASCII .stl inputs are supported`, which hid the real action:
install the optional repair/conversion stack or provide an ASCII STL.

## Change

- Added a gate between repair and orientation.
- If repair is skipped and the imported mesh is not `.stl`, the pipeline now
  turns that receipt into a failed `mesh_repair` receipt.
- The message tells the user to install `printpipe[mesh-repair]` or convert the
  model to ASCII STL before importing.
- The pipeline report is written with `mesh_repair=failed`, and orientation is
  not attempted.

## Verification

```bash
.venv/bin/pytest \
  tests/test_pipeline_existing_mesh.py::test_non_stl_existing_mesh_fails_at_repair_when_trimesh_unavailable -q
```

Result: `1 passed`.

## Boundary

This is a clearer dependency gate, not a replacement for `trimesh`. Native
OBJ/GLB/3MF repair/conversion still requires the optional mesh-repair
dependencies.
