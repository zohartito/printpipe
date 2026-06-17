"""Idempotency tests for the print-done notifier.

These prove the mira dedup contract end to end:
  * first send notifies and records the id,
  * a duplicate id is skipped (transport not re-invoked),
  * a failed send does NOT mark the id seen, so it retries,
  * dedup survives a process restart (state is persisted).
"""

from __future__ import annotations

import json

import pytest

from printpipe.notify import (
    PrintDoneEvent,
    PrintDoneNotifier,
    SentNotificationStore,
    notification_id_for_event,
)
from printpipe.notify.notifier import NotifyResult


class RecordingTransport:
    """A send callable that records messages; can be told to fail."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.fail_times = 0

    def __call__(self, message: str) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transport down")
        self.messages.append(message)


def make_event(job_id: str = "job-123") -> PrintDoneEvent:
    return PrintDoneEvent(
        job_id=job_id,
        printer_serial="01S00A000000001",
        file_name="bracket.gcode.3mf",
        result="success",
    )


def test_first_send_notifies_and_records(tmp_path):
    state = tmp_path / "sent.json"
    transport = RecordingTransport()
    notifier = PrintDoneNotifier.from_state_path(state, transport)

    result = notifier.notify_print_done(make_event())

    assert result is NotifyResult.SENT
    assert transport.messages == ["Print done: bracket.gcode.3mf"]
    # The id is persisted to disk.
    persisted = json.loads(state.read_text(encoding="utf-8"))
    expected_id = notification_id_for_event(make_event())
    assert expected_id in persisted["sent"]


def test_duplicate_id_is_skipped(tmp_path):
    state = tmp_path / "sent.json"
    transport = RecordingTransport()
    notifier = PrintDoneNotifier.from_state_path(state, transport)

    first = notifier.notify_print_done(make_event())
    second = notifier.notify_print_done(make_event())

    assert first is NotifyResult.SENT
    assert second is NotifyResult.SKIPPED
    # Transport invoked exactly once for the duplicate event.
    assert transport.messages == ["Print done: bracket.gcode.3mf"]


def test_failed_send_does_not_mark_seen_and_retries(tmp_path):
    state = tmp_path / "sent.json"
    transport = RecordingTransport()
    transport.fail_times = 1  # first send raises, second succeeds
    notifier = PrintDoneNotifier.from_state_path(state, transport)

    # First attempt: transport raises, id must NOT be recorded.
    with pytest.raises(RuntimeError):
        notifier.notify_print_done(make_event())

    store = SentNotificationStore(state)
    assert len(store) == 0
    assert not store.has_seen(notification_id_for_event(make_event()))

    # Retry: same event now succeeds and gets recorded.
    result = notifier.notify_print_done(make_event())
    assert result is NotifyResult.SENT
    assert transport.messages == ["Print done: bracket.gcode.3mf"]

    # And a third identical event is now skipped.
    assert notifier.notify_print_done(make_event()) is NotifyResult.SKIPPED


def test_dedup_survives_restart(tmp_path):
    state = tmp_path / "sent.json"

    transport_one = RecordingTransport()
    PrintDoneNotifier.from_state_path(state, transport_one).notify_print_done(make_event())
    assert transport_one.messages == ["Print done: bracket.gcode.3mf"]

    # Simulate a process restart: brand-new notifier + store reading the file.
    transport_two = RecordingTransport()
    result = PrintDoneNotifier.from_state_path(state, transport_two).notify_print_done(
        make_event()
    )

    assert result is NotifyResult.SKIPPED
    assert transport_two.messages == []


def test_distinct_jobs_each_notify(tmp_path):
    state = tmp_path / "sent.json"
    transport = RecordingTransport()
    notifier = PrintDoneNotifier.from_state_path(state, transport)

    assert notifier.notify_print_done(make_event("job-A")) is NotifyResult.SENT
    assert notifier.notify_print_done(make_event("job-B")) is NotifyResult.SENT
    assert len(transport.messages) == 2


def test_corrupt_state_file_is_treated_as_empty(tmp_path):
    state = tmp_path / "sent.json"
    state.write_text("{not valid json", encoding="utf-8")

    store = SentNotificationStore(state)
    assert len(store) == 0
    assert not store.has_seen("anything")

    # And a send still works, rewriting a clean file.
    transport = RecordingTransport()
    notifier = PrintDoneNotifier(store, transport)
    assert notifier.notify_print_done(make_event()) is NotifyResult.SENT
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 1


def test_custom_message_formatter(tmp_path):
    state = tmp_path / "sent.json"
    transport = RecordingTransport()
    notifier = PrintDoneNotifier.from_state_path(
        state,
        transport,
        format_message=lambda event: f"Done {event.job_id} on {event.printer_serial}",
    )

    notifier.notify_print_done(make_event("job-XYZ"))
    assert transport.messages == ["Done job-XYZ on 01S00A000000001"]
