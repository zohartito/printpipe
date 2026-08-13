"""Persisted store of already-sent notification ids.

A small JSON state file remembers which notification ids have been delivered so
a re-run, MQTT reconnect, or re-fired event is skipped instead of double-sent.

The store deliberately exposes the mira pattern as two distinct calls:

  * ``has_seen(notification_id)`` -- check BEFORE attempting a send.
  * ``mark_seen(notification_id)`` -- call ONLY after the send succeeds.

Keeping them separate is what makes a failed send retry: nothing is recorded
unless the caller explicitly marks it seen after success.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


class SentNotificationStore:
    """A JSON-backed set of notification ids that have been delivered.

    The file format is::

        {"schema_version": 1, "sent": {"<id>": "<iso-utc-timestamp>"}}

    A missing or unreadable file is treated as an empty store so a first run
    (or a corrupted state file) never crashes the notifier -- at worst it
    re-sends, which is the safe direction only when the file is genuinely gone.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._sent: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}
        sent = payload.get("sent")
        if not isinstance(sent, dict):
            return {}
        # Coerce to str/str and drop anything malformed rather than raising.
        return {str(key): str(value) for key, value in sent.items()}

    def has_seen(self, notification_id: str) -> bool:
        """True if this id has already been recorded as sent.

        Call this BEFORE attempting a send to decide whether to skip.
        """
        return notification_id in self._sent

    def mark_seen(self, notification_id: str, *, sent_at: datetime | None = None) -> None:
        """Record an id as sent and persist atomically.

        Call this ONLY after the underlying send has succeeded. Marking an id
        twice is a harmless no-op (the timestamp is refreshed).
        """
        stamp = (sent_at or datetime.now(timezone.utc)).isoformat()
        self._sent[notification_id] = stamp
        self._persist()

    def _persist(self) -> None:
        payload = {"schema_version": SCHEMA_VERSION, "sent": self._sent}
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace: write to a temp file in the same directory, then
        # os.replace so a crash mid-write can't corrupt the existing store.
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_name, self.path)
        except BaseException:
            # Clean up the temp file on any failure so we don't leak it.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def __len__(self) -> int:
        return len(self._sent)
