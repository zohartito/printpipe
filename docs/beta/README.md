# PrintPipe Beta

Status: limited local beta notes for 3-5 trusted users.

PrintPipe is local-first, but it is not a finished print-ready pipeline. The
current beta is for people who can run a terminal command, inspect generated
reports, and give artifact-backed feedback before any real printing decision.

Start with [onboarding.md](onboarding.md).

## Ground Rules

- Keep the first pass local: run setup, `printpipe doctor`, and one tiny fixture.
- Treat generated reports as diagnostic evidence, not permission to print.
- Return the requested feedback artifacts even when the run looks boring.
- Do not use beta outputs for unattended, wearable, food-contact,
  load-bearing, medical, child, pet, electrical, or heat-exposed parts.

## Current Folder

- `onboarding.md`: setup, test object choice, run/report collection, safety
  boundaries, privacy notes, and feedback expectations.
- `printpipe beta-plan --runs-dir runs`: local command for turning the remaining
  beta evidence gaps into concrete next actions.
- `printpipe record-beta-feedback runs/<run-id>`: writes a structured
  trusted-user feedback packet without claiming physical print proof.
- `printpipe beta-feedback-status --runs-dir runs`: summarizes whether three
  unique trusted users have completed feedback.
- `printpipe record-rule-update runs/<run-id>`: records material, orientation,
  or repair rule changes made after dogfood or beta triage.
- `printpipe rule-update-status --runs-dir runs`: checks whether material,
  orientation, and repair updates have verified packets.
- `printpipe failure-regression-status --runs-dir runs --regression-manifest <manifest>`:
  checks whether every captured failure packet has an executable regression case.
