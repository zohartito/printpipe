# Wave 1 Mesh Generation Provider Strategy

Generated: 2026-05-16. Scope: PrintPipe v1 mesh generation strategy.

PrintPipe should treat mesh generation as a replaceable upstream capability, not
as the product boundary. The product boundary is the verified bridge from
reference input to Bambu-native, slice-verified `.3mf` with receipts.

## Source Inputs

Local project context:

- `/Users/zohartito/Desktop/printpipe/docs/APP_ROADMAP.md`
- `/Users/zohartito/Desktop/printpipe/docs/ARCHITECTURE.md`
- `/Users/zohartito/Desktop/slipper_3d/PRODUCT_BRAINSTORM.md`
- `/Users/zohartito/Desktop/slipper_3d/RETROSPECTIVE.md`
- `/Users/zohartito/Desktop/slipper_3d/docs/research/wave_3_bonus_work.md`
- `/Users/zohartito/Desktop/slipper_3d/output/V2_COMPARISON.md`

Current provider docs checked:

- [Tencent Hunyuan3D-2 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Replicate predictions docs](https://replicate.com/docs/topics/predictions/create-a-prediction)
- [Replicate lifecycle docs](https://replicate.com/docs/reference/how-does-replicate-work/)
- [Meshy Image to 3D API](https://docs.meshy.ai/en/api/image-to-3d)
- [Tripo API overview](https://www.tripo3d.ai/api)
- [Hyper3D Rodin generation API](https://developer.hyper3d.ai/api-specification/rodin-generation)

## Provider Interface Shape

The `meshgen` module should expose one stable PrintPipe contract and keep vendor
quirks behind provider adapters.

Suggested shape:

```python
class MeshGenProvider(Protocol):
    provider_id: str
    display_name: str
    capabilities: MeshGenCapabilities

    def estimate(self, request: MeshGenRequest) -> MeshGenEstimate: ...
    def generate(self, request: MeshGenRequest, run: RunContext) -> MeshGenResult: ...
    def healthcheck(self) -> ProviderHealth: ...
    def delete_remote_artifacts(self, result: MeshGenResult) -> DeleteResult: ...
```

Core request fields:

- `input_kind`: `image`, `frames`, `video`, `gif`, or `existing_mesh`.
- `reference_images`: normalized local paths chosen by the input stage.
- `prompt_hint`: optional user/object hint, never required for v1.
- `target_use`: default `3d_printing`.
- `output_formats`: ordered preference, initially `glb`, `stl`, `obj`.
- `quality`: `draft`, `standard`, `high`; maps per provider.
- `seed`: optional, persisted when supported.
- `provider_params`: namespaced vendor escape hatch.
- `privacy_mode`: `local_only`, `cloud_allowed`, or `cloud_required`.
- `max_attempts`, `timeout_seconds`, `budget_usd`, `budget_credits`.

Core result fields:

- `status`: `succeeded`, `failed`, `canceled`, `skipped`.
- `provider_id`, `model_id`, `model_version`, `api_endpoint`.
- `attempt_id`, `remote_job_id`, `remote_request_id`.
- `started_at`, `ended_at`, `queue_seconds`, `run_seconds`, `wall_seconds`.
- `cost`: `{currency, amount, credits, billable_units, estimated}`.
- `input_hashes` and output artifact hashes.
- `raw_output_path`, `normalized_mesh_path`, `preview_path`.
- `mesh_stats`: vertices, faces, bounds, watertight, manifold, boundary edges.
- `error`: normalized category, vendor message, retryable flag.
- `fallback_from` and `fallback_reason`.
- `remote_artifacts_deleted`: true, false, unsupported, or unknown.

Important boundary: `MeshGenProvider.generate()` only creates or imports a raw
mesh and writes provider receipts. Repair, orientation, scale, bed fit, profile
tuning, `.3mf` bundling, and slicing stay outside the provider.

## Provider Candidates

| Provider | V1 role | Strengths | Risks |
|---|---|---|---|
| Existing mesh import | Required provider | Zero cloud upload, deterministic, lets users bypass AI generation | Still needs repair and normalization; user may assume bad STLs are already printable |
| Hunyuan3D local API server | Required adapter shape, optional runtime | Official repo supports launching a local API server and posting image-to-3D requests; aligns with local-first/privacy story | Heavy dependency, GPU/VRAM setup, long local runtimes on non-GPU machines, packaging burden |
| Hunyuan3D via hosted runner | Primary practical v1 generation path when configured | Fast proof from slipper project; open model family; can be run through HF/Replicate/owned GPU | Free HF Spaces were unreliable; hosted runner availability, model slug, and pricing can drift |
| Replicate runner | Placeholder or early paid fallback | Generic async prediction lifecycle, public model catalog, manageable polling model | Model ownership/licenses vary; outputs expire; cost and model versions must be logged per attempt |
| Meshy API | Placeholder paid fallback | Image-to-3D task API, status polling/streaming, model URL outputs, delete endpoint | Vendor-specific credit model and retention; quality must be benchmarked on PrintPipe fixtures |
| Tripo API | Placeholder paid fallback | Publicly advertises image-to-model, multi-image-to-3D, post-processing, and 3D printing use cases | API/account terms and exact output controls need validation before implementation |
| Hyper3D Rodin | Placeholder paid fallback | API supports image-to-3D, multi-view image submission, quality/tier/material options | More vendor-specific surface area; cost/retention and printability need fixture benchmarks |

## Local vs Hosted Tradeoffs

Local generation:

- Best privacy posture: references and generated meshes can stay on the user's
  machine.
- Lowest marginal provider cost after setup.
- Works for users with no network or strict IP constraints.
- Hard to package: GPU drivers, model weights, VRAM, disk, OS differences, and
  cold-start time become PrintPipe support problems.
- May be too slow for one-shot UX on common laptops.

Hosted generation:

- Best early reliability if using paid, maintained runners rather than free
  community spaces.
- Easier to keep PrintPipe v1 focused on repair, Bambu bundling, slice gates,
  and receipts.
- Enables fast retries across providers.
- Adds privacy, retention, API key, rate-limit, cost, and vendor-drift concerns.
- Requires explicit user consent before uploading references or meshes.

Free hosted spaces:

- Good for experiments and demos.
- Not acceptable as the only v1 success path. The slipper project hit paused
  spaces, runtime errors, internal Gradio endpoints, and opaque server failures.

Owned hosted GPU workers later:

- Best long-term control over latency, versions, logs, and privacy promises.
- Not v1. This belongs with the roadmap's Web/Cloud Later phase after the local
  pipeline proves itself.

## Hunyuan3D Lessons from Slipper

1. Single-image Hunyuan3D-2 `/shape_generation` produced a usable slipper mesh
   quickly after several other endpoints failed. The provider adapter should
   encode the known-good call shape and avoid probing internal Gradio state
   endpoints during normal runs.
2. Free HF Spaces are queue- and runtime-dependent. Treat them as experimental
   runners, not production infrastructure.
3. Multi-view can matter more than resolution. The V2 comparison showed that
   higher octree values on a single image created denser but smoother meshes,
   while multi-view input preserved the wavy sole detail at roughly the original
   face count.
4. More polygons are not automatically better for printing. Provider results
   must be scored by downstream printability metrics, not just visual detail.
5. AI-generated mesh output is not production-ready. The slipper mesh had 3,778
   non-manifold edges before repair; PrintPipe must always run topology scan and
   repair after mesh generation.
6. Provider success is not PrintPipe success. A raw GLB can look plausible and
   still fail Bambu import, bed placement, support generation, or slicing.

## Retry and Fallback Policy

Retry only when there is a meaningful chance of a different outcome.

Normalized error categories:

- `transient_network`: retry same provider with backoff.
- `provider_rate_limited`: retry after provider reset if within run budget.
- `provider_unavailable`: fail over to next configured provider.
- `provider_timeout`: one retry with longer timeout, then fail over.
- `invalid_request`: do not retry; surface configuration/input error.
- `bad_output_format`: retry once with alternate output format if supported.
- `mesh_quality_failed`: retry with alternate references, multi-view, or next provider.
- `budget_exceeded`: stop immediately.
- `privacy_blocked`: stop immediately unless user opts into cloud.

Suggested v1 fallback chain:

1. If input is already a mesh, use `ExistingMeshImportProvider`.
2. If `privacy_mode=local_only`, use configured local Hunyuan3D server if
   healthy; otherwise fail clearly with "cloud provider disabled".
3. If cloud is allowed and a hosted Hunyuan3D runner is configured, try it first.
4. If Hunyuan3D fails for transient provider reasons, try the next configured
   paid fallback: Replicate runner, Meshy, Tripo, or Rodin.
5. If output fails topology quality gates, try one alternate generation strategy:
   multi-view references when available, then the next provider.
6. After provider retries are exhausted, stop before repair/orientation and write
   a failed run receipt.

Budget defaults:

- Maximum 2 attempts per provider.
- Maximum 3 provider attempts per run in v1.
- Maximum 1 mesh-quality retry after a non-transient succeeded generation.
- No silent paid fallback if it would exceed `budget_usd` or `budget_credits`.
- Never retry indefinitely to "get lucky"; every retry must record the reason.

## Cost and Time Logging Requirements

Every provider attempt writes one append-only record to:

```text
runs/<run_id>/meshgen/attempts.jsonl
```

Every meshgen phase writes one summary to:

```text
runs/<run_id>/meshgen/summary.json
```

Required per-attempt fields:

- Run ID, provider ID, adapter version, model ID, model version/revision.
- Input artifact paths and SHA-256 hashes.
- Parameters that affect output: seed, quality, format, remesh/topology flags,
  texture flags, multi-view frame list.
- Timestamps for submit, first progress, completed, downloaded, normalized.
- Queue seconds, provider run seconds, download seconds, total wall seconds.
- Provider job/request IDs and HTTP status codes.
- Cost in provider-native units and normalized USD when knowable.
- Whether cost is actual, estimated, user-configured, or unknown.
- Output paths, hashes, file sizes, mesh stats, and repair-required flags.
- Error category, retryable flag, fallback reason, and user-visible summary.
- Remote retention/deletion status when applicable.

Logging rules:

- Never write API keys, bearer tokens, signed URLs, cookies, or full auth
  headers to receipts.
- If a provider returns temporary download URLs, store only a redacted URL host
  and the downloaded artifact hash.
- If a provider does not expose actual cost per job, record the configured rate
  used for estimation and mark it `estimated=true`.
- The final run report should include elapsed time and estimated/actual meshgen
  cost separately from slicer time, material mass, and print cost.

## Privacy Considerations

PrintPipe v1 is local-first, but mesh generation may still call hosted providers.
The user must be able to see and control that boundary.

Required behavior:

- Default to no cloud upload unless the selected provider requires it and the
  user has configured credentials/consent.
- Make provider choice explicit in the run receipt.
- Keep original media, cleaned frames, generated mesh, and provider logs in the
  local run folder unless the user deletes the run.
- Store API keys in environment variables, OS keychain, or a secrets mechanism,
  never in run artifacts.
- Hash inputs before upload and log hashes, not raw personal metadata.
- Strip EXIF/GPS metadata from images before cloud upload.
- Offer remote artifact deletion where the provider API supports it.
- Warn users that reference images may contain personal, proprietary, or
  copyrighted material before using hosted providers.

Provider-specific privacy notes:

- Replicate API outputs can be temporary; downloaded artifacts must be saved
  locally before expiry, and retention behavior differs between API and web use.
- Meshy exposes a delete endpoint for Image-to-3D tasks; the adapter should call
  it when the user requests cloud cleanup.
- Hunyuan3D local API server avoids cloud upload but still needs local model
  weights and hardware capability checks.

## V1 Recommendation

Implement the provider strategy in this order:

1. Define the stable `MeshGenProvider` interface, request/result receipts, and
   normalized error taxonomy before integrating any vendor.
2. Implement `ExistingMeshImportProvider` first so the rest of the pipeline can
   be tested without cloud or GPU dependencies.
3. Implement `Hunyuan3DProvider` against a configurable endpoint, not a hardcoded
   free Space. The same adapter should support a local Hunyuan3D API server, a
   paid hosted Hunyuan endpoint, or an internal runner later.
4. Add provider placeholders for Replicate, Meshy, Tripo, and Rodin with
   capability metadata, config validation, and `NotImplemented` generation.
5. Make hosted fallbacks opt-in and budget-limited.
6. Treat every generated mesh as untrusted. Always run PrintPipe repair,
   topology validation, orientation, bed-fit, Bambu bundling, and slice gate
   before declaring success.

Practical v1 default:

```text
existing mesh input
  -> ExistingMeshImportProvider

image/GIF/video input with cloud disabled
  -> Hunyuan3D local endpoint if configured
  -> otherwise fail with actionable setup message

image/GIF/video input with cloud allowed
  -> configured Hunyuan3D endpoint
  -> configured paid fallback provider if Hunyuan fails
  -> failed run receipt if all provider attempts fail
```

Do not spend v1 complexity on provider auto-shopping, public web queues, billing,
or owned GPU infrastructure. The highest-leverage v1 work is the contract,
receipts, Hunyuan adapter, existing-mesh import, and the downstream gates that
turn any provider's raw mesh into a printable Bambu project.
