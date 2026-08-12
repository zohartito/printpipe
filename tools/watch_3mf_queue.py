#!/usr/bin/env python3
"""EVENT watch-folder loop for printpipe (loop map #29).

A new ``.3mf`` dropped into the inbox is VALIDATED, then SLICED (only when the
existing Bambu CLI gate env is set/discoverable), then appended to a queue
report. Reuses the repo's own library — `validate_bundle` and
`run_bambu_cli_slice_stage` — so the Bambu CLI gate (`PRINTPIPE_BAMBU_STUDIO_CLI`
and fallbacks) is the SAME gate the pipeline honors: without it, slicing skips
honestly rather than faking a receipt (AGENTS.md danger zone).

Trigger: launchd `WatchPaths` on the inbox fires this on every file-drop. It is
also safe to run on a timer — it is idempotent (a `.3mf` already processed at
its current content hash is skipped) and capped (`--max-files`).

Emits one JSON object (schema `printpipe.watch_queue.v1`) to stdout and to the
queue-report file under the inbox. Dry-run validates only — no slice, no state
or report write.

Usage (via the repo venv or any python with deps):
    python3 tools/watch_3mf_queue.py --dry-run
    python3 tools/watch_3mf_queue.py --inbox runs/inbox --max-files 20
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from printpipe.bambu.slicer import (  # noqa: E402
    discover_bambu_cli_executable,
    run_bambu_cli_slice_stage,
)
from printpipe.bambu.threemf.core import validate_bundle  # noqa: E402

SCHEMA = "printpipe.watch_queue.v1"
LOOP_NAME = "printpipe-watch-3mf"
LEARNINGS = REPO_ROOT / ".claude" / "LEARNINGS.md"
DEFAULT_INBOX = REPO_ROOT / "runs" / "inbox"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_state(state_path: Path) -> dict:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def slice_gate(explicit_cli: str | None) -> tuple[bool, str | None]:
    """Return (gate_open, executable_path). Honors the existing env gate."""
    if explicit_cli:
        return True, str(Path(explicit_cli).expanduser())
    found = discover_bambu_cli_executable(env=os.environ)
    return (found is not None), (str(found) if found else None)


def slice_one(three_mf: Path, inbox: Path, executable: str, plate: int) -> dict:
    slice_dir = inbox / "sliced" / three_mf.stem
    slice_dir.mkdir(parents=True, exist_ok=True)
    receipt = run_bambu_cli_slice_stage(
        three_mf_path=three_mf,
        run_layout=SimpleNamespace(slice_dir=slice_dir),
        executable=executable,
        plate=plate,
    )
    status = getattr(receipt.status, "value", str(receipt.status))
    gcode = receipt.metrics.get("gcode_path") if isinstance(receipt.metrics, dict) else None
    return {"status": status, "message": receipt.message,
            "slice_dir": str(slice_dir), "gcode_path": str(gcode) if gcode else None}


def append_learning(line: str) -> None:
    try:
        LEARNINGS.parent.mkdir(parents=True, exist_ok=True)
        with LEARNINGS.open("a", encoding="utf-8") as fh:
            fh.write(f"- {_now()} [{LOOP_NAME}] {line}\n")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="printpipe .3mf watch-folder loop")
    parser.add_argument("--inbox",
                        default=os.environ.get("PRINTPIPE_WATCH_DIR", str(DEFAULT_INBOX)))
    parser.add_argument("--max-files", type=int, default=20,
                        help="hard cap on .3mf files processed per run")
    parser.add_argument("--plate", type=int, default=0)
    parser.add_argument("--bambu-cli", default=None,
                        help="explicit Bambu Studio CLI (else the env gate is used)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate only; no slice, no state/report write")
    parser.add_argument("--no-learning", action="store_true")
    args = parser.parse_args()

    inbox = Path(args.inbox).expanduser()
    inbox.mkdir(parents=True, exist_ok=True)
    state_path = inbox / ".watch-state.json"
    report_path = inbox / "queue-report.latest.json"
    max_files = max(0, args.max_files)

    gate_open, executable = slice_gate(args.bambu_cli)
    state = load_state(state_path)

    report = {
        "schema": SCHEMA,
        "loop": LOOP_NAME,
        "scanned_at": _now(),
        "inbox": str(inbox),
        "dry_run": args.dry_run,
        "gate_open": gate_open,
        "bambu_cli": executable,
        "max_files": max_files,
        "processed": [],
    }

    candidates = sorted(p for p in inbox.glob("*.3mf") if p.is_file())
    counts = {"scanned": len(candidates), "new": 0, "valid": 0, "invalid": 0,
              "sliced_succeeded": 0, "sliced_skipped": 0, "sliced_failed": 0}

    for path in candidates:
        if counts["new"] >= max_files:
            break
        digest = _hash(path)
        prior = state.get(path.name)
        if prior and prior.get("hash") == digest:
            continue  # idempotent: already processed at this content
        counts["new"] += 1

        result = validate_bundle(path)
        valid = result.ok
        counts["valid" if valid else "invalid"] += 1

        entry = {
            "file": path.name,
            "size": path.stat().st_size,
            "hash": digest,
            "valid": valid,
            "application": result.application,
            "validation_errors": list(result.errors),
            "sliced": None,
        }

        if args.dry_run:
            report["processed"].append(entry)
            continue

        if not valid:
            entry["sliced"] = {"status": "skipped_invalid",
                               "message": "validation failed; not sliced"}
        elif not gate_open:
            entry["sliced"] = {"status": "skipped_gate_closed",
                               "message": "no Bambu Studio CLI (set PRINTPIPE_BAMBU_STUDIO_CLI)"}
            counts["sliced_skipped"] += 1
        else:
            sliced = slice_one(path, inbox, executable, args.plate)
            entry["sliced"] = sliced
            if sliced["status"] == "succeeded":
                counts["sliced_succeeded"] += 1
            elif sliced["status"] == "skipped":
                counts["sliced_skipped"] += 1
            else:
                counts["sliced_failed"] += 1

        state[path.name] = {"hash": digest, "processed_at": _now(),
                            "valid": valid,
                            "sliced_status": (entry["sliced"] or {}).get("status")}
        report["processed"].append(entry)

    report["counts"] = counts
    report["notes"] = ("dry-run: validation only" if args.dry_run
                       else f"{counts['new']} new file(s) processed")

    if not args.dry_run:
        try:
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as err:
            report["notes"] += f"; write failed: {type(err).__name__}"
        if not args.no_learning and counts["new"]:
            append_learning(
                f"new={counts['new']} valid={counts['valid']} invalid={counts['invalid']} "
                f"gate_open={gate_open} sliced_ok={counts['sliced_succeeded']} "
                f"sliced_skipped={counts['sliced_skipped']}"
            )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
