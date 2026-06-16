"""Idempotent "print done" notifier.

``PrintDoneNotifier`` wraps a caller-supplied send transport with the persisted
dedup store. The flow mirrors mira's note handler exactly:

    1. derive a stable notification id for the event,
    2. if the store has already seen it -> skip (return SKIPPED),
    3. otherwise call the send transport,
    4. mark the id seen ONLY after the transport returns without raising.

A transport that raises propagates the error and does NOT mark the id seen, so
the next "print done" event (an MQTT reconnect re-firing the same completion)
will retry the send.

The transport is injected as a plain callable ``send(message: str) -> None``.
That keeps this module dependency-free and fully testable; a real deployment
passes a Telegram/MQTT-backed callable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from printpipe.notify.dedup import SentNotificationStore


@dataclass(frozen=True)
class PrintDoneEvent:
    """A printer "print finished" event as received over MQTT.

    ``job_id`` is the printer/print identifier used for dedup. When the printer
    reports a per-job id (Bambu task/subtask id) pass it directly; otherwise a
    stable composite of serial + gcode name + finish timestamp works.
    """

    job_id: str
    printer_serial: str = ""
    file_name: str = ""
    result: str = "success"


class NotifyResult(str, Enum):
    SENT = "sent"
    SKIPPED = "skipped"  # already notified for this id


def notification_id_for_event(event: PrintDoneEvent) -> str:
    """Stable id for an event.

    If the event already carries a unique ``job_id`` we use it verbatim so the
    id is human-readable in the state file. We still fold in the serial so the
    same job id from two different printers can't collide.
    """
    raw = f"{event.printer_serial}|{event.job_id}|{event.file_name}|{event.result}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    if event.job_id:
        return f"{event.job_id}-{digest}"
    return digest


class PrintDoneNotifier:
    """Send at-most-once "print done" notifications, persisted across restarts."""

    def __init__(
        self,
        store: SentNotificationStore,
        send: Callable[[str], None],
        *,
        format_message: Callable[[PrintDoneEvent], str] | None = None,
    ) -> None:
        self._store = store
        self._send = send
        self._format_message = format_message or _default_message

    @classmethod
    def from_state_path(
        cls,
        state_path: str | Path,
        send: Callable[[str], None],
        *,
        format_message: Callable[[PrintDoneEvent], str] | None = None,
    ) -> "PrintDoneNotifier":
        """Convenience constructor that builds the dedup store from a path."""
        return cls(
            SentNotificationStore(state_path),
            send,
            format_message=format_message,
        )

    def notify_print_done(self, event: PrintDoneEvent) -> NotifyResult:
        """Notify once for ``event``; subsequent identical events are skipped.

        Returns ``SENT`` when the transport was invoked and the id recorded,
        ``SKIPPED`` when the id was already seen. Any exception from the
        transport propagates and leaves the id unrecorded so it retries.
        """
        notification_id = notification_id_for_event(event)

        # Check-seen-first: a duplicate id never touches the transport.
        if self._store.has_seen(notification_id):
            return NotifyResult.SKIPPED

        message = self._format_message(event)
        # If this raises, we fall through WITHOUT marking seen -> retried later.
        self._send(message)

        # Mark seen ONLY after a successful send.
        self._store.mark_seen(notification_id)
        return NotifyResult.SENT


def _default_message(event: PrintDoneEvent) -> str:
    name = event.file_name or event.job_id or "print"
    if event.result and event.result != "success":
        return f"Print finished ({event.result}): {name}"
    return f"Print done: {name}"
