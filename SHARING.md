# Using PrintPipe safely

PrintPipe’s web UI is intentionally private: it binds only to the literal IPv4
loopback address `127.0.0.1`. Run it on the computer that owns the run artifacts:

```bash
printpipe serve
```

Then open `http://127.0.0.1:8765` in a browser on that same computer. The web
UI can inspect local runs and download their artifacts, but it must not be
published through Tailscale, a LAN bind, a reverse proxy, or a public tunnel.
Those artifacts can contain private inputs, reports, logs, and physical-test
evidence, and PrintPipe does not provide web-user authentication or per-run
authorization.

To collaborate, have each person run their own local PrintPipe installation
and exchange only the files they intentionally choose to share. Use the local
CLI for ComfyUI preflight and provider actions; browser-triggered preflight is
disabled so an unauthenticated request cannot probe operator-network services.
