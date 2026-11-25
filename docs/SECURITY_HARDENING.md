# PrintPipe security hardening boundaries

This project is local-first, but local inputs and a repository checkout are not
automatically trusted to choose executable work.

## Executable regression manifests

`readiness`, release-status, and planning commands never discover or execute
`regressions/dogfood_failures.json` automatically. To execute a regression
manifest, use the explicit operator command:

```text
printpipe run-regressions /absolute/or/reviewed/manifest.json --strict
```

Passing `--regression-manifest` to a status or planning command is explicit
operator input and remains supported for an intentional regression evaluation.
Review every listed argv before using it; manifests execute with the invoking
user's authority.

Web readiness, release, and planning surfaces are manifest-free. The legacy
`printpipe serve --regression-manifest` option is accepted only for
compatibility and ignored.

## Media command adapters

`PRINTPIPE_MEDIA_MESHGEN_COMMAND` is an explicit user-scoped command source.
PrintPipe does not automatically load `media_meshgen_command` from the current
project's `.printpipe/config.json`. An operator may opt in for a known project
only by setting `PRINTPIPE_TRUST_PROJECT_MEDIA_COMMAND=1` (or by explicitly
selecting a config path). For one smoke invocation use
`printpipe media-meshgen-smoke reference.png --command "reviewed-adapter"`.
For a run, set `PRINTPIPE_MEDIA_MESHGEN_COMMAND` explicitly in that invocation;
`printpipe run` has no `--media-command` option.

## Bounded local integrations

ComfyUI preflight accepts only finite timeouts up to 10 seconds and reads at
most 1 MiB from each API response. The built-in PNG heightfield adapter and the
Windows installer ZIP staging path reject inputs that exceed documented,
conservative byte, dimension, member, or compression-ratio limits.

## CI actions

This revision tracks `ci.yml` (tests and secret scanning), `secret-scan.yml`
(secret scanning), and `claude-pr-review.yml` (conditional PR review). Every
`uses:` reference must use a reviewed full commit SHA; mutable tags such as
`@v4` are prohibited. Keep permissions minimal and do not expose
secrets to untrusted pull-request code.
