# Wave 51 - Windows Portable ZIP

## Question

Can PrintPipe produce a Windows-friendly handoff package instead of requiring a
tester to remember the raw `python printpipe.pyz ...` command?

## Change

Added `printpipe build-windows-portable`, backed by
`printpipe.packaging.windows_portable.build_windows_portable_package()`.

The generated ZIP contains:

- `PrintPipe/printpipe.pyz`
- `PrintPipe/printpipe.cmd`
- `PrintPipe/printpipe.ps1`
- `PrintPipe/README.txt`

The `.cmd` and `.ps1` files forward all arguments to the packaged zipapp.

## Boundaries

This is still not a signed Windows installer. It does not bundle Python, install
Start Menu shortcuts, register file associations, or bundle Bambu Studio.

## Live Windows Smoke

The generated ZIP was copied to `windows-pc`, expanded under the user's temp
folder, and run through both launchers:

- `printpipe.cmd --version` returned `printpipe 0.1.0`
- `printpipe.ps1 --version` returned `printpipe 0.1.0`
- `printpipe.cmd package-smoke --platform windows --json` returned `status=ok`

The smoke run produced reports and a Bambu `.3mf` under:

`C:\Users\sample_user\AppData\Local\Temp\printpipe-windows-portable\runs\20260528-071414-package-smoke-tiny-tetrahedron`

The slice gate remains `manual_required` because Bambu Studio is not installed
on that Windows host.
