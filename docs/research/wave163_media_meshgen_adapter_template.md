# Wave 163 - Media Meshgen Adapter Template

Date: 2026-05-28

## Question

After adding `PRINTPIPE_MEDIA_MESHGEN_COMMAND`, how does a future provider
experiment discover the exact command protocol without reverse-reading tests?

## Change

- Added `printpipe media-meshgen-template`.
- Without flags, it prints a complete Python adapter template to stdout.
- With `--output`, it writes an executable script and prints the matching export
  command for `PRINTPIPE_MEDIA_MESHGEN_COMMAND`.
- The generated script accepts:
  - `--input-kind`
  - `--source`
  - `--reference-image`
  - `--output`
  - `--output-format`
  - `--target-use`
  - `--quality`
  - optional `--prompt`
  - optional `--seed`
  - optional `--params-json`

## Why

Wave 162 made PrintPipe less Hunyuan-specific, but the generic hook still
required implicit knowledge. This wave turns the protocol into something a
second agent can generate, run, inspect, and replace.

## Boundary

The template intentionally does not generate geometry. It exits with a
placeholder error until `generate_mesh()` is replaced with a real local model,
hosted wrapper, or provider API call.
