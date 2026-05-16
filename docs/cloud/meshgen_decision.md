# Hosted Meshgen Decision

Status: Wave 10 decision note. Current answer: not yet; evaluate after local dogfood/beta.

## Decision

Do not add hosted GPU workers or make hosted mesh generation a required v1 path
yet. PrintPipe should stay local-only by default until the existing local run
pipeline has dogfood and beta evidence that the downstream gates are reliable.

Hosted providers may remain in the provider-interface design as explicit,
opt-in adapters, but the product should not take on public web queues, owned GPU
capacity, billing, or cloud storage before local runs prove that PrintPipe can
turn a mesh into a Bambu-ready, slice-verified project.

## Local-Only Default

Local-only remains enough when:

- The user supplies an STL/3MF or an existing local mesh output.
- A local meshgen endpoint can be configured without cloud upload.
- The main risk is repair, orientation, bed fit, material settings, bundle
  validity, slicing, or physical print outcome rather than raw mesh availability.
- Privacy, IP ownership, copyrighted reference material, or customer files make
  cloud upload unacceptable.
- Beta failures can be reproduced and fixed with local fixtures and run-folder
  artifacts.

This keeps the first beta honest: PrintPipe is proving the print pipeline, not
the economics or reliability of a hosted AI mesh service.

## When Hosted Mesh Generation Is Needed

Hosted mesh generation is needed when beta evidence shows that local-only blocks
the product goal in a way hosted execution can actually solve. Good reasons
would include:

- Trusted beta users consistently need image/GIF/video-to-mesh generation but
  cannot run a local model because of GPU, VRAM, disk, driver, or setup limits.
- A configured hosted provider produces better raw meshes than the local path,
  and those meshes pass PrintPipe topology, repair, orientation, bed-fit,
  bundling, slicing, and physical dogfood gates.
- The same provider behavior is repeatable enough to support regression
  fixtures, retry policy, cost receipts, and actionable failure messages.
- The hosted path improves beta completion rate without hiding provider
  failures behind queues or vague "generation failed" messages.

Hosted mesh generation is not needed merely because it is easier to demo, avoids
local dependency work, or moves an unsolved downstream printability problem to a
server.

## Gates Before Hosted Meshgen

All of these gates must be true before PrintPipe invests in hosted workers:

1. Local pipeline works first. The CLI path can import or generate a mesh, write
   run receipts, repair/validate topology, orient/fit, bundle a Bambu 3MF, slice
   it, and preserve artifacts for regression.
2. GPU/provider cost. There is a documented per-job cost model, budget cap,
   quota behavior, retry cost, idle GPU cost if owned, and an answer for who
   pays during beta.
3. Privacy/IP. Cloud upload is explicit opt-in, reference images are scrubbed of
   EXIF/GPS metadata, API keys never enter artifacts, retention/deletion behavior
   is documented, and users are warned about personal, proprietary, or
   copyrighted inputs.
4. Queue latency. The expected wait, timeout, retry, cancellation, and fallback
   behavior is acceptable for beta runs and visible in run receipts.
5. Beta evidence. Local dogfood and trusted-user beta runs show repeated,
   artifact-backed failures where hosted meshgen is the smallest fix.

If any gate is missing, keep hosted meshgen as a future adapter and improve the
local beta path first.

## Evaluation Trigger After Local Dogfood/Beta

Reopen this decision after local dogfood/beta, not before. The evaluation packet
should include:

- Slipper dogfood results, including software gates and physical print outcome.
- At least three non-slipper beta object runs with run reports and failure notes.
- Trusted-user setup feedback showing whether local dependencies blocked runs.
- A short provider comparison with real wall time, queue latency, failure modes,
  and GPU/provider cost.
- A privacy/IP review for any provider that would receive user media.

Until that packet exists, the decision remains: not yet; evaluate after local
dogfood/beta.
