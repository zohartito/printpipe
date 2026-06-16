# Sharing PrintPipe with a friend

PrintPipe runs entirely on one computer and serves a small web page you can
open in a browser. There are two ways to let a friend use it.

---

## Option A — Your friend runs it themselves (one command)

PrintPipe ships as a normal Python package, so the fastest path is `uv`
(a tiny, fast Python runner). It downloads PrintPipe, runs it, and cleans up
after itself — no manual install, no virtualenv to manage.

**1. Get `uv`** (one time, copy-paste into a terminal)

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. Run PrintPipe** (one command)

```bash
uvx --from git+<repo-url> printpipe serve
```

`<repo-url>` is the PrintPipe Git URL (for example
`https://github.com/you/printpipe.git`). The first run downloads everything;
later runs are instant.

**3. Open the page**

The terminal prints the address. Open it in any browser:

```
http://127.0.0.1:8765
```

That is the whole app. Leave the terminal window open while using it; close it
(or press `Ctrl+C`) to stop.

---

## Option B — No terminal for your friend (you host it over Tailscale)

If your friend should just click a link and never touch a terminal, **you** run
PrintPipe and expose it on your private [Tailscale](https://tailscale.com)
network. Both of you need to be on the same tailnet (free for personal use).

**1. Start PrintPipe** on your machine:

```bash
printpipe serve
```

It listens on `http://127.0.0.1:8765`.

**2. Share it on the tailnet** — point Tailscale at the local port:

```bash
tailscale serve 8765
```

Tailscale prints a private HTTPS link like
`https://your-machine.your-tailnet.ts.net`. Send that to your friend — anyone
on your tailnet can open it in a browser with no install and no terminal.

**3. Optional — share with someone NOT on your tailnet** using Funnel
(exposes it to the public internet, so only do this for short, trusted demos):

```bash
tailscale funnel 8765
```

Stop sharing at any time:

```bash
tailscale serve --https=443 off   # or: tailscale funnel 8765 off
```

---

### Notes

- PrintPipe is local-first: your files and prints stay on the machine running
  `printpipe serve`. Tailscale only forwards the web page to people you choose.
- Default port is `8765`. Change it with `printpipe serve --port 9000` (and
  point `tailscale serve` at the same number).
- To let other devices on your home Wi-Fi reach it without Tailscale, run
  `printpipe serve --host 0.0.0.0` — but Tailscale is the safer default.
