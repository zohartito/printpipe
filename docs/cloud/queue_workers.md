# Queue and Worker Architecture Sketch

## Status

This is a future cloud architecture sketch. Queues and workers are not implemented now; the current PrintPipe path remains the local run-folder pipeline.

The goal of this design is to preserve the existing hard gates while making long-running work observable, resumable, and safe to isolate across machine types.

## Future Shape

```text
Client / API
  -> run record + idempotency key
  -> orchestration queue
  -> stage-specific queues
      -> meshgen GPU workers
      -> repair CPU workers
      -> slicing host-isolated workers
      -> report generation workers
  -> artifact store + manifest
  -> progress and cancellation events
```

The orchestrator would own stage ordering. Workers would own one bounded unit of work, publish artifacts, and emit progress, but would not decide the whole run outcome.

## Stage Queues

- `meshgen`: submits normalized input references to a GPU-capable worker pool and returns generated mesh candidates plus provider metadata.
- `repair`: validates and repairs mesh topology on CPU workers, then writes repaired meshes and validation receipts.
- `slicing`: builds the Bambu-native project bundle and runs the slicer in a host-isolated worker so slicer crashes, local profile reads, or platform assumptions do not affect GPU workers.
- `report generation`: renders JSON, Markdown, and HTML receipts from the immutable manifest and stage outputs.

Each stage should read only declared inputs from the prior artifact manifest and write only to its own stage prefix. Cross-stage communication should happen through artifact handoff, not through shared mutable directories.

## Job Model

Each job would include:

- `run_id`: stable run folder or cloud run identifier.
- `stage`: `meshgen`, `repair`, `slicing`, or `report_generation`.
- `attempt`: monotonic retry count.
- `idempotency_key`: derived from request identity, normalized inputs, target printer/material settings, and stage name.
- `input_manifest`: immutable references to the artifacts required by this stage.
- `cancellation_token`: the run-level cancellation marker the worker checks between expensive operations.

Workers should be able to re-run the same job without duplicating promoted outputs. Temporary files can be regenerated, but published artifacts should be addressed by content hash or by a stage output key that is promoted atomically.

## Idempotency

Idempotency should be enforced at both the run and stage level:

- A repeated client submission with the same idempotency key should return the existing run.
- A repeated stage job should either observe that its output manifest is already committed or replace only its own uncommitted scratch space.
- Artifact promotion should be atomic: write to scratch, validate, then publish the manifest update.
- Downstream jobs should consume only committed manifests, never scratch paths.

This keeps retries and worker restarts from producing competing reports, duplicate bundles, or inconsistent slice receipts.

## Retries

Retries should distinguish transient failures from deterministic gate failures:

- Transient failures: network timeouts, provider rate limits, worker preemption, temporary disk pressure, or slicer process crashes.
- Deterministic failures: invalid input, non-repairable topology, bed-fit failure, unsupported profile setting, or repeatable slice rejection.

Transient failures can use bounded retries with exponential backoff and jitter. Deterministic failures should stop the run and write a failure receipt rather than burn queue capacity. Jobs that exhaust retry budget should move to a dead-letter queue with enough context to replay locally.

## Progress

Progress should be stored as append-only events and summarized onto the run record:

- `queued`
- `claimed`
- `started`
- `progress`
- `artifact_committed`
- `blocked`
- `failed`
- `completed`
- `cancelled`

Long stages should emit coarse progress milestones, such as provider request submitted, mesh candidate received, repair validation complete, slicer started, slice estimate parsed, and report generation complete. The UI/API should tolerate sparse progress because some providers and slicer calls may not expose granular percentages.

## Cancellation

Cancellation should be cooperative:

- The run record stores a desired cancelled state.
- Queued jobs should be skipped before claim.
- Claimed jobs should check the cancellation token before starting each expensive operation and before promoting artifacts.
- If a stage cannot be interrupted safely, it may finish scratch work but must not enqueue downstream jobs or mark the run successful after cancellation.

Cancellation should leave already committed artifacts intact for diagnosis, with the final receipt making clear that the run ended by user request.

## Artifact Handoff

Artifact handoff should be manifest-driven:

- Stage outputs are immutable after commit.
- Each manifest entry records path or object key, content hash, media type, producing stage, and validation status.
- The next stage receives only the manifest entries it needs.
- Reports are generated from committed artifacts and stage receipts, not from worker-local state.

For local development this maps cleanly onto run folders. For a future cloud path it can map onto object storage while keeping the same conceptual contract.

## GPU Worker Isolation

GPU worker isolation should be strict because mesh generation is the most expensive and provider-dependent stage:

- GPU workers should handle only meshgen jobs.
- CPU repair, slicing, and report generation should run on separate pools.
- GPU workers should use ephemeral scratch space and avoid mounting slicer profiles or report output directories.
- Provider credentials should be scoped to meshgen and kept out of slicing/report workers.
- Resource limits should prevent a single meshgen job from monopolizing all GPU capacity.

Slicing should be isolated separately from GPU work because it depends on Bambu CLI behavior, local profile discovery, and platform-specific process execution. Keeping those concerns out of the GPU pool makes failures easier to understand and capacity easier to plan.

## Open Questions

- Whether the first cloud queue should preserve the exact local run-folder layout in object storage or introduce a cloud-native manifest shape first.
- Which stage owns user-visible policy decisions when a repair succeeds but leaves warnings.
- How much slicer stdout/stderr should be retained in successful runs.
- Whether cancellation should expose partial artifacts by default or require an explicit debug mode.
