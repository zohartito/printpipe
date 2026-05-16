# Cloud Cost And Billing Sketch

Generated: 2026-05-16. Scope: future hosted PrintPipe cloud planning.

This document is a planning sketch for cloud cost visibility and later billing.
It does not change the v1 product boundary: PrintPipe v1 remains local-first,
Bambu-focused, and slice-verified before any hosted product promise.

## Billing Not V1

Billing not v1 means no user-facing metering, invoices, paid plans, automatic
paid retries, or hosted-only success path should ship in the first release.
Before pricing, PrintPipe needs evidence about actual cost, estimated cost,
failure rates, support burden, artifact retention, and the user value of a
completed slice-verified run.

The cloud phase can collect internal cost telemetry earlier, but the telemetry
must not imply that a run is billable. The first use of these numbers should be
capacity planning, abuse protection, provider comparison, and beta support
triage.

## Cost Model

Treat the cost model as cost-of-goods-sold per run, not as customer pricing.

```text
run_cost =
  hosted_gpu_meshgen_cost
  + storage_cost
  + slicing_cost
  + bandwidth_cost
  + support_cost
  + failed_run_reserve
```

Each component should be stored separately in run receipts. A raw meshgen
success is not enough to allocate all cost to a successful customer outcome,
because the run can still fail repair, orientation, Bambu bundling, slicing, or
physical review.

### Hosted GPU Meshgen

Hosted GPU meshgen is likely the largest variable cost. Track each provider or
owned worker attempt rather than only the final run:

- `gpu_seconds`: accelerator time used by model loading, inference, remeshing,
  and post-processing.
- `queue_seconds`: time spent waiting for a worker or provider slot.
- cold-start count, model ID, model version, worker type, and region.
- attempt status, retry reason, fallback provider, and whether the retry was
  user-requested or platform-requested.
- provider-native cost units plus normalized actual cost or estimated cost.

No automatic paid retry should happen without a run budget and a receipt line
explaining why the retry was attempted. Provider failures and platform retries
should be separated from user-requested quality retries.

### Storage

Storage includes original references, cleaned frames, generated meshes,
repaired/oriented meshes, Bambu bundles, reports, logs, screenshots, and
regression artifacts. Track:

- `storage_gb_days` by artifact class.
- retained artifact count, largest artifact class, and compression status.
- retention policy chosen for the run: temporary, beta-debug, user-retained, or
  regression-retained.
- deletion status for local artifacts and remote provider artifacts.

Long-lived failed-run artifacts can be valuable for regressions, but they should
be deliberately retained with a reason, not accidentally priced into every run.

### Slicing

Slicing is a separate compute lane from meshgen. It may run on CPU-heavy workers
with Bambu Studio installed and will have different scaling, licensing, and
platform support risks than GPU inference.

Track:

- `slice_seconds`: wall time and CPU time for Bambu CLI or equivalent slicer.
- slicer version, printer profile, filament profile, process profile, and
  bundle hash.
- result status: success, warning-blocked, failed, timed out, or skipped.
- parsed estimates: print time, mass, layer count, and material cost estimate.

Slicing cost should stay visible even when meshgen is free or local, because a
hosted slice gate is part of the future cloud reliability promise.

### Bandwidth

Bandwidth covers user uploads, provider downloads, report viewing, artifact
downloads, and any cross-region movement between workers and storage.

Track:

- `egress_bytes` by artifact class: mesh, bundle, report, preview, log, and
  user download.
- ingress bytes for references, videos, and existing meshes.
- provider download bytes and cross-region transfer bytes.
- signed URL creation and expiry outcomes, without storing secrets.

Bandwidth is also a privacy signal. Receipts should record what crossed the
cloud boundary without storing private URLs, bearer tokens, cookies, or EXIF/GPS
metadata.

### Support

Support cost is part of the product cost, not an afterthought. Cloud workflows
turn unclear failures into tickets, refunds, reruns, and manual review.

Track:

- `support_minutes` spent on beta triage, user onboarding, refund review, and
  regression reduction.
- issue category: provider, repair, orientation, profile, 3MF, slice, packaging,
  billing, privacy, or unclear.
- whether the run produced enough receipts for self-service debugging.
- whether support resulted in a regression fixture or product change.

Pricing should not be set until support minutes per successful run and support
minutes per failed run are measured across real beta users.

### Failed Runs

Failed runs are expected and useful during beta. They are product evidence, not
customer debt.

Classify every failed run with a `failure_category`, first failing gate, retry
count, provider status, and user-visible message. Suggested billing stance for
future planning:

- Do not charge users for platform failures such as provider outage, internal
  worker crash, storage loss, slicer infrastructure failure, or a broken
  PrintPipe adapter.
- Do not charge for retries triggered only by platform policy.
- Consider charging only after a clear future policy exists for user-requested
  quality retries, unsupported inputs, very large uploads, or intentionally
  retained cloud artifacts.
- Keep failed-run cost in internal COGS so pricing can include a realistic
  failure reserve.

## Collect Metrics Before Pricing

Collect metrics before pricing any hosted tier. The minimum useful dataset is
attempt-level and run-level, because provider attempts, platform retries, and
final user outcomes have different costs.

| Metric | Level | Why it matters before pricing |
|---|---|---|
| `gpu_seconds` | meshgen attempt | Separates expensive inference from cheap imports and catches cold-start waste. |
| `queue_seconds` | meshgen attempt | Shows whether latency comes from capacity shortage or model runtime. |
| `storage_gb_days` | run artifact | Converts retention choices into visible cost. |
| `slice_seconds` | slice attempt | Measures hosted slice-gate cost separately from mesh generation. |
| `egress_bytes` | artifact transfer | Captures download-heavy reports and repeated bundle access. |
| `support_minutes` | ticket/run | Prevents pricing from ignoring human triage cost. |
| `failure_category` | run | Distinguishes platform failures from unsupported inputs and product gaps. |

Also collect:

- successful run count, failed run count, canceled run count, and retry count.
- actual cost where provider or infrastructure billing exposes it.
- estimated cost where only configured rates are available.
- budget requested, budget consumed, and budget stop reason.
- artifact retention age, deletion request count, and deletion success.
- user-visible outcome: slice-verified, blocked before slicing, or warning
  blocked after slicing.

Do not convert these metrics into prices until enough beta data exists to
answer:

- What is the median and p95 cost of a slice-verified hosted run?
- How often do retries improve the final outcome?
- Which failures are platform responsibility?
- How much support is required per successful customer outcome?
- What retention window users actually need?
- Which artifact downloads dominate bandwidth?

## Future Billing Considerations

Future billing should price outcomes and limits that users can understand, not
implementation trivia. Possible units to evaluate after telemetry:

- included successful hosted runs per month.
- paid user-requested retry credits.
- large input surcharge or upload limit for videos and heavy existing meshes.
- retained artifact storage after a free retention window.
- team/admin features only after auth and privacy controls are mature.

Guardrails for any future billing design:

- keep local-first usage available outside hosted billing.
- show estimated cost before starting a paid hosted run.
- stop at budget limits instead of silently continuing.
- expose run receipts that separate meshgen, storage, slicing, bandwidth,
  support, and failed-run costs.
- never make a raw mesh generation success the billable success definition; the
  cloud product promise must remain tied to a slice-verified run or a clearly
  reported failure.
