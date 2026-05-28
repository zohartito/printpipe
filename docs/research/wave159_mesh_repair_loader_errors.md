# Wave 159 - Mesh Repair Loader Errors Become Receipts

## Question

Can corrupt or legacy GLB/mesh files throw raw loader exceptions through mesh
repair instead of producing a failed stage receipt?

## Finding

Yes. `repair_mesh_file_to_receipt()` handled missing optional dependencies and
explicit `MeshRepairError`, but loader-level exceptions such as
`NotImplementedError("file is not GLTF2")` escaped as tracebacks.

## Change

- Catch `NotImplementedError`, `ValueError`, and `TypeError` in the receipt
  wrapper.
- Write a failed repair stats JSON file with `error_type`, input path, output
  path, and the loader message.
- Return a failed `mesh_repair` receipt with the stats artifact.

## Verification

```bash
.venv/bin/pytest \
  tests/test_mesh_repair.py::test_repair_mesh_file_to_receipt_records_mesh_loader_errors -q
```

Result: `1 passed`.

## Boundary

This does not repair invalid GLB files. It turns the failure into a normal,
artifact-backed PrintPipe receipt so reports and UI can explain it.
