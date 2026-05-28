# Wave 48 - macOS App Web Launcher

## Question

Can the generated `PrintPipe.app` behave like a usable local app when launched
without CLI arguments?

## Finding

Before this wave, the app bundle's executable forwarded no arguments to the
zipapp. A Finder-style double-click therefore printed CLI help and exited. That
proved the wrapper executable worked, but it was not a useful app launch path.

## Change

The launcher now branches on argument count:

- with arguments, it still forwards to the zipapp unchanged;
- with no arguments, it starts `printpipe serve`;
- the default host is `127.0.0.1`;
- the default port is `8765`;
- the default runs folder is `~/PrintPipe/runs`;
- the launcher opens `http://127.0.0.1:8765/` after startup.

`PRINTPIPE_APP_DRY_RUN=1` prints the launch command and exits, which gives tests
and packaging smoke checks a non-blocking way to verify the Finder-style path.

## Boundaries

This is still a Python zipapp wrapper. It does not bundle Python, does not bundle
Bambu Studio, and is not Developer ID signed or notarized.
