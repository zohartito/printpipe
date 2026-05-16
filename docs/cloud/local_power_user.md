# Local Power-User Plan

Status: Wave 10 hosted-future boundary. Cloud is optional later product
infrastructure; the local app remains the power-user version even if cloud exists later.

## Decision

PrintPipe should keep the local CLI and local app as the most capable surface.
Cloud can make setup, sharing, queueing, or hosted mesh generation easier, but it
must not become the only way to run advanced workflows, inspect receipts, keep
private inputs local, or hand off to Bambu Studio.

The local product boundary stays the same: a user can create a run folder, repair
and validate geometry, bundle a Bambu-native `.3mf`, run local slice checks when
Bambu Studio/Bambu CLI is installed, and keep the generated reports without a
hosted account.

## Local Capabilities To Preserve

- CLI parity: any future cloud workflow needs a command-line equivalent for
  setup, run creation, status, report opening, artifact inspection, and
  diagnostic checks. `printpipe run`, `printpipe status`,
  `printpipe open-report`, `printpipe doctor`, and `printpipe serve` remain
  first-class power-user entry points.
- Offline/private runs: users can run local-only jobs with no cloud upload for
  private references, client-owned meshes, unpublished designs, or sensitive
  material settings. Cloud-required providers must be explicit opt-ins.
- Local Bambu Studio integration: the local app keeps direct detection of the
  user's Bambu Studio install, app-shipped profiles, user profile folders, and
  Bambu CLI slice gate. Cloud should not hide local slicer failures or replace
  local profile receipts.
- Local artifacts and run folders: generated meshes, repaired meshes, Bambu
  bundles, logs, manifests, slice outputs, and HTML/Markdown/JSON reports remain
  in readable local run folders. The local run folder is the durable audit trail.
- Export/import between local/cloud: export from local to cloud should upload a
  chosen run bundle or selected artifacts with user consent. Import from cloud to
  local should restore the run folder shape, including manifests, reports, logs,
  artifact hashes, and any cloud execution receipts.

## Cloud As Convenience

Cloud may add hosted GPU workers, queues, remote storage, signed links,
collaboration, or account-backed history after the local pipeline is trustworthy.
Those features should wrap the same pipeline concepts instead of creating a
separate product that only works online.

Good cloud additions:

- Queue a long meshgen or slicing task while preserving the same manifest fields.
- Share a report link while keeping a downloadable local equivalent.
- Store a run archive for backup or collaboration.
- Resume a cloud run locally when the user wants private inspection or Bambu
  Studio handoff.

Bad cloud additions:

- Cloud-only advanced settings that cannot be expressed by the CLI.
- Hosted runs with weaker geometry, Bambu profile, or slice receipts than local.
- Storage that cannot export a complete local run folder.
- Account requirements for local report viewing, run replay, or Bambu handoff.

## Compatibility Rules

Cloud and local should exchange a versioned run archive rather than loose files.
The archive should include:

- `manifest.json` plus provider, repair, orientation, profile, bundle, and slice
  receipts.
- All user-approved input references or explicit placeholders for private inputs
  that were never uploaded.
- Generated and repaired mesh artifacts with hashes.
- Bambu `.3mf` output and local Bambu Studio/Bambu CLI slice evidence when
  available.
- HTML, Markdown, and JSON reports.

The cloud importer can mark unavailable private files as missing, but it should
not silently substitute different inputs. The local importer can mark cloud-only
compute receipts as remote, but it should still expose them in the same report
surfaces.

## Acceptance Gate

Before PrintPipe treats any hosted product surface as ready, prove that a
power-user can still:

1. Run the same core workflow locally from the CLI.
2. Keep a fully offline/private run path.
3. Use the installed local Bambu Studio/Bambu CLI for final verification.
4. Inspect and preserve all artifacts in local run folders.
5. Export from local to cloud and import from cloud to local without losing
   receipts, hashes, reports, or Bambu handoff evidence.
