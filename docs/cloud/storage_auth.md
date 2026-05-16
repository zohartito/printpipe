# Storage and Auth Future Sketch

Status: future design sketch only. Auth and storage are not implemented now.

PrintPipe is currently a private repo and a local-first pipeline. The active
product boundary is: inputs stay on the user's machine, generated artifacts are
written under local run directories, and no hosted account, object store,
multi-tenant API, or upload service is part of the running app. Any cloud path
must be opt-in and must preserve a local equivalent for private or offline use.

## Artifact Classes

Future storage should model each run as a user-owned project with scoped
artifacts:

- Uploaded references: source photos, sketches, captions, masks, calibration
  data, and optional user notes. These are the most privacy-sensitive files and
  should default to local-only unless a user explicitly uploads them.
- Generated meshes: intermediate and final mesh files produced by the pipeline,
  including repair and orientation variants.
- 3MF bundles: slicer-ready packages and Bambu-oriented output bundles.
- Reports: JSON, Markdown, HTML, screenshots, contact sheets, and manifest
  files used to explain a run.
- Logs: pipeline logs, slicer logs, doctor output, queue events, and debug
  traces needed for support or regression analysis.

Object keys should be scoped by owner, project, run, and artifact class rather
than by user-supplied filenames. Local paths should keep the same conceptual
shape under `runs/<run-id>/` so cloud and local tooling can share receipts and
report links without inventing separate artifact semantics.

## Auth Boundary

The current app has no auth layer. A future hosted surface should add auth only
where it creates a real boundary:

- Local mode: the operating system account and filesystem permissions are the
  trust boundary. A local equivalent of cloud sharing is an explicit file path,
  exported bundle, or localhost route that resolves only to the selected run
  artifact.
- Hosted mode: every project, run, object, report, and log row is owned by a
  user or organization. Access checks must happen before metadata lookup,
  object reads, signed URL issuance, deletion, or support export.
- Service workers and background jobs should receive narrow run-scoped grants,
  not broad user credentials. Jobs should write artifacts only for the run they
  were assigned.
- Support access should be off by default and time-bound when enabled by the
  user, with a visible audit trail.

Auth should not be used to imply quality, print safety, or physical validation.
It only controls who can see or mutate stored artifacts.

## Access Links

Cloud downloads and previews should use signed URLs with short expirations,
least-privilege object scope, and no embedded personal metadata. Signed URLs
should be generated after an ownership check and should never be stored in
reports, logs, issue templates, or durable manifests.

The local equivalent is a scoped local artifact reference: a CLI command such as
`printpipe open-report runs/<run-id>`, a direct path under the run directory, or
a localhost-only route that refuses traversal outside the configured runs root.
Local references do not create a network sharing promise; they are conveniences
for files the user already has on disk.

## Deletion and Retention

Deletion must be understandable and complete:

- Deleting a local run means removing the run directory and all uploaded
  references, generated meshes, 3MF bundles, reports, and logs inside it.
- Deleting a hosted project or run should delete object-store files, database
  metadata, previews, derived thumbnails, queue payloads, and support exports.
- Derived artifacts should not outlive the source run unless the user saves or
  exports them into a new owned project.
- Retention defaults should be conservative: uploaded references and generated
  artifacts are retained while the user keeps the run; transient logs, queue
  payloads, and signed URL records should expire on a short operational window.
- Backups may require delayed physical erasure, but the UI and policy should say
  the maximum backup retention window plainly.

Retention should be policy-driven per artifact class, not scattered across
workers. When a user asks to delete a run, storage and auth systems should make
it possible to prove which artifacts were removed or are pending backup expiry.

## User Ownership and Privacy

Users own their uploaded references, generated meshes, 3MFs, reports, and logs.
PrintPipe should not reuse private inputs or outputs for training, fixtures,
marketing, examples, or regression corpora without explicit user consent and a
separate copy into a clearly labeled dataset.

Privacy defaults:

- Do not expose a public gallery or guessable object URLs.
- Do not place faces, addresses, document text, GPS metadata, tokens, API keys,
  or signed URLs in durable reports or logs.
- Prefer private-by-default sharing, with recipient, expiration, and revocation
  controls when hosted sharing exists.
- Keep local-first workflows fully usable without account creation or upload.
- Make export formats portable so users can leave with their references,
  generated meshes, 3MF bundles, reports, and logs.

The future cloud design should make storage boring and explicit: every artifact
has an owner, an artifact class, a retention rule, an access path, and a clear
deletion story.
