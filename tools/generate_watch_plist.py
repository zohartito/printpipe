"""Generate a checkout-specific launchd watch plist without loading it."""
from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--bambu-cli', type=Path, required=True)
    parser.add_argument('--inbox', type=Path, default=root / 'runs/inbox')
    parser.add_argument('--output', type=Path, default=root / 'runs/inbox-watch/com.printpipe.watch.plist')
    args = parser.parse_args()
    inbox = args.inbox.expanduser().absolute()
    logs = inbox.parent / f'{inbox.name}-watch'
    output = args.output.expanduser().absolute()
    if output.is_relative_to(inbox):
        parser.error('plist output must stay outside the watched inbox')
    for path in (args.python, args.bambu_cli):
        if not path.expanduser().is_file():
            parser.error('configured Python and slicer must be existing executable files')
    inbox.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'Label': 'com.printpipe.watch',
        'ProgramArguments': [str(args.python.expanduser().absolute()), str(root / 'tools/watch_3mf_queue.py'),
                             '--inbox', str(inbox)],
        'WorkingDirectory': str(root),
        'EnvironmentVariables': {'PRINTPIPE_BAMBU_STUDIO_CLI': str(args.bambu_cli.expanduser().absolute())},
        'WatchPaths': [str(inbox)],
        'RunAtLoad': False,
        'StandardOutPath': str(logs / 'watch.stdout.log'),
        'StandardErrorPath': str(logs / 'watch.stderr.log'),
    }
    output.write_bytes(plistlib.dumps(payload))
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
