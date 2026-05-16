# Future Backend API

Status: Wave 10 sketch only. No backend API is implemented now.

PrintPipe remains local-first. The backend API below is a future backend API
shape for a hosted service after the local CLI, local run folders, local report
format, and local beta feedback loop are reliable. That sequence matters: only after the local workflow works should a cloud service preserve the same run
evidence instead of hiding unfinished local behavior behind a network boundary.

This document is not an OpenAPI contract, not an implementation plan for this
wave, and not evidence that uploads, hosted jobs, hosted artifact storage, or
hosted reports exist today. The current system writes local `runs/<run-id>/`
folders, `manifest.json`, and `80_reports/run_report.*` files.

## Design Rules

- Local runs stay the source of truth until they are proven useful in beta.
- Backend jobs should mirror local run concepts instead of inventing a second
  pipeline model.
- Uploaded inputs and generated artifacts must have retention, deletion, and
  privacy rules before any hosted beta.
- A backend job is allowed to fail, but it must keep enough manifest, stage,
  artifact, warning, and report evidence to reproduce or debug the failure
  locally.
- Hosted reports must keep the same honesty language as local reports: software
  success is not physical print validation.

## Resource Sketch

All `/v1` routes are candidates for a future hosted service. They are not
available in the current local app.

| Resource | Endpoint | Purpose |
| --- | --- | --- |
| Uploads | `POST /v1/uploads` | Create an input upload record and return a signed upload target or inline upload result. |
| Uploads | `GET /v1/uploads/{upload_id}` | Read upload state, media type, size, hash, and retention metadata. |
| Jobs | `POST /v1/jobs` | Start a PrintPipe job from an upload or a server-side imported artifact. |
| Jobs | `GET /v1/jobs/{job_id}` | Read job status, input summary, stage summary, warnings, and report links. |
| Jobs | `GET /v1/jobs/{job_id}/events` | Future polling or streaming event feed for stage progress. |
| Artifacts | `GET /v1/jobs/{job_id}/artifacts` | List artifacts that belong to a job, grouped by local run-stage category. |
| Artifacts | `GET /v1/artifacts/{artifact_id}` | Download or redirect to a specific artifact when access rules allow it. |
| Reports | `GET /v1/jobs/{job_id}/reports` | List report documents for a job, usually JSON, Markdown, and HTML. |
| Reports | `GET /v1/reports/{report_id}` | Fetch a report document or signed report URL. |
| Health | `GET /healthz` | Return service health for load balancers and smoke checks. |

### Uploads

`POST /v1/uploads` accepts metadata before bytes move:

```json
{
  "filename": "reference.gif",
  "content_type": "image/gif",
  "size_bytes": 123456,
  "sha256": "optional-client-hash",
  "purpose": "printpipe_run"
}
```

A future implementation could return an `upload_id`, upload URL, checksum
requirements, and expiration. Local-first behavior means the CLI should still
be able to run the same input without cloud upload.

### Jobs

`POST /v1/jobs` creates the hosted equivalent of a local run:

```json
{
  "upload_id": "upl_123",
  "printer": "Bambu Lab P2S 0.4 nozzle",
  "filament": "SUNLU TPU 90A",
  "target_size_mm": 295
}
```

`GET /v1/jobs/{job_id}` returns a compact status model:

```json
{
  "job_id": "job_123",
  "source_run_id": "20260516-101112-reference",
  "status": "failed",
  "input": {
    "kind": "gif",
    "upload_id": "upl_123"
  },
  "stages": [
    {"name": "classify_input", "status": "succeeded"},
    {"name": "meshgen", "status": "failed"}
  ],
  "warning_count": 2,
  "artifact_count": 5,
  "report_ids": ["rpt_123_json", "rpt_123_html"]
}
```

The status values should align with local `StageStatus`: `pending`, `running`,
`succeeded`, `failed`, and `skipped`.

### Artifacts

Artifact records should mirror local `ArtifactKind` values where possible:

- `original_input`
- `cleaned_frame`
- `generated_mesh`
- `repaired_mesh`
- `oriented_mesh`
- `profile_json`
- `3mf`
- `slice_log`
- `preview`
- `report`

The list endpoint should include stable IDs plus local-style paths so a hosted
job can still be compared to a local run folder:

```json
{
  "artifacts": [
    {
      "artifact_id": "art_001",
      "job_id": "job_123",
      "kind": "original_input",
      "label": "Original input",
      "local_path": "00_input/reference.gif",
      "size_bytes": 123456
    }
  ]
}
```

### Reports

Hosted reports should preserve the local report family:

- JSON for automation and bug reports.
- Markdown for lightweight human review.
- HTML for local or hosted browsing.

The hosted JSON report should be derived from the same fields currently written
to `80_reports/run_report.json`: `run_id`, stage receipts, `artifacts[]`,
`warnings`, `settings_changes`, and `pre_print_checklist`.

### Health

`GET /healthz` should be boring and dependency-light:

```json
{
  "service": "printpipe-backend",
  "status": "ok"
}
```

Readiness checks that touch object storage, queues, databases, slicer workers,
or mesh workers should be separate from the public liveness endpoint.

## Local Manifest Mapping

The backend job and report model should be a projection of the local run folder
model, not a replacement for it.

| Local run field or file | Future backend concept |
| --- | --- |
| `runs/<run-id>/` | Hosted job workspace or object-storage prefix. |
| `manifest.json` | Job manifest snapshot retained with the job. |
| `run_id` | Stable local run identifier; may also be stored as `source_run_id`. |
| `job_id` | Backend identifier for the hosted execution. It should not replace `run_id` in exported reports. |
| `created_at_utc` | Job creation timestamp. |
| `input.kind` | Upload or import media kind: image, gif, video, or mesh. |
| `input.stored_path` | Original input artifact path, usually `00_input/<filename>`. |
| `input.source_path` | Local-only source path; hosted reports should redact or replace it with upload/import metadata. |
| `stages` | Stage directory map and initial stage namespace. Backend status can summarize the same stage names. |
| `00_input/`, `10_frames/`, `20_meshgen/`, `30_repair/`, `40_geometry/`, `50_profiles/`, `60_bundle/`, `70_slice/`, `80_reports/` | Artifact namespaces for listing and retention policy. |
| `80_reports/run_report.json` | Canonical backend report payload. |
| `80_reports/run_report.md` | Human-readable report export. |
| `80_reports/run_report.html` | Browser report export. |
| `artifacts[]` | Backend artifact records with IDs, kinds, labels, local-style paths, size, hash, and download authorization. |
| `warnings` | Job/report warning summary. |
| `settings_changes` | Reported profile or process deltas. |
| `pre_print_checklist` | Report checklist that must remain explicit about physical print validation. |

## Non-Goals For Now

- Do not add backend routes to the current codebase from this sketch alone.
- Do not make the local CLI require cloud credentials.
- Do not upload private beta artifacts automatically.
- Do not claim cloud execution, real-time progress, hosted storage, or remote
  slicing exists until there is implementation and verification.
- Do not treat hosted job success as proof that an object is print-ready.

## First Implementation Gate

The backend API should wait until local runs can repeatedly produce useful
manifest, artifact, and report evidence across the beta object set. After that,
the first backend slice should be narrow: upload an input, create one job,
mirror the local manifest/report model, list artifacts, fetch reports, and
answer health checks. Anything beyond that should come from observed local beta
needs rather than imagined cloud features.
