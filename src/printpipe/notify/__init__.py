"""Idempotent print-completion notifications.

The notifier wraps an arbitrary "send" transport (Telegram, webhook, log, ...)
with a persisted dedup guard so that an MQTT reconnect or a re-fired
"print done" event cannot double-ping. The dedup contract mirrors mira's note
handler: check-seen-first, then send, then mark-seen ONLY after a successful
send -- a failed send is never recorded, so it retries on the next event.
"""

from __future__ import annotations

from printpipe.notify.dedup import SentNotificationStore
from printpipe.notify.notifier import (
    PrintDoneEvent,
    PrintDoneNotifier,
    notification_id_for_event,
)

__all__ = [
    "PrintDoneEvent",
    "PrintDoneNotifier",
    "SentNotificationStore",
    "notification_id_for_event",
]
