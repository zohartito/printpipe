from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from printpipe.cli import build_parser, main
from printpipe.meshgen import comfyui_runtime
from printpipe.meshgen.comfyui_runtime import preflight_comfyui_runtime


class _ComfyHandler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, dict[str, object]]] = {}

    def do_GET(self) -> None:
        status, payload = self.responses.get(
            self.path,
            (404, {"error": "not found"}),
        )
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return None


def _serve_comfyui_like(responses: dict[str, tuple[int, dict[str, object]]]) -> str:
    handler = type("ComfyHandler", (_ComfyHandler,), {"responses": responses})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{server.server_port}"


def test_preflight_comfyui_runtime_marks_ready_when_api_and_saveglb_exist() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}, "SaveGLB": {}}),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "ready"
    assert report["api_reachable"] is True
    assert report["object_info_reachable"] is True
    assert report["missing_nodes"] == []


def test_preflight_comfyui_runtime_marks_missing_saveglb_action_required() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}}),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "action_required"
    assert report["missing_nodes"] == ["SaveGLB"]
    assert "SaveGLB" in report["warnings"][0]


def test_preflight_comfyui_runtime_handles_non_object_info_json() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, ["SaveGLB"]),
        }
    )

    report = preflight_comfyui_runtime(url)

    assert report["status"] == "action_required"
    assert report["object_info_reachable"] is False
    assert "response was not a JSON object" in report["warnings"][0]


def test_comfyui_preflight_parser_accepts_url_timeout_and_json() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "media-meshgen-comfyui-preflight",
            "--url",
            "http://127.0.0.1:8188",
            "--timeout",
            "0.25",
            "--json",
        ]
    )

    assert args.command == "media-meshgen-comfyui-preflight"
    assert args.url == "http://127.0.0.1:8188"
    assert args.timeout == 0.25
    assert args.json is True


def test_comfyui_preflight_cli_prints_json(capsys) -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"SaveGLB": {}}),
        }
    )

    exit_code = main(["media-meshgen-comfyui-preflight", "--url", url, "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["comfyui_url"] == url


def test_comfyui_preflight_cli_strict_fails_when_required_node_missing() -> None:
    url = _serve_comfyui_like(
        {
            "/system_stats": (200, {"system": {"os": "posix"}}),
            "/object_info": (200, {"LoadImage": {}}),
        }
    )

    exit_code = main(
        [
            "media-meshgen-comfyui-preflight",
            "--url",
            url,
            "--strict",
        ]
    )

    assert exit_code == 2


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), 10.1])
def test_preflight_rejects_nonfinite_or_excessive_timeouts(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        preflight_comfyui_runtime(timeout_seconds=timeout)


def test_preflight_rejects_oversized_response_before_buffering(monkeypatch) -> None:
    class Response:
        headers = {"Content-Length": "1048577"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size=-1):
            raise AssertionError("oversized response must not be read")

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: Response(),
    )

    report = preflight_comfyui_runtime()

    assert report["status"] == "action_required"
    assert any("response exceeds preflight byte limit" in warning for warning in report["warnings"])


def test_preflight_shared_deadline_stops_transport_that_ignores_timeout_hints(
    monkeypatch,
) -> None:
    closed = threading.Event()

    class SlowResponse:
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def close(self) -> None:
            closed.set()

        def read(self, _size=-1) -> bytes:
            return b'{"SaveGLB": {}}'

    def slow_open(_url: str, _deadline: float) -> SlowResponse:
        # Deliberately ignore the derived timeout/deadline just like a broken
        # transport implementation; the caller must still return at deadline.
        time.sleep(0.229)
        return SlowResponse()

    monkeypatch.setattr(comfyui_runtime, "_open_response", slow_open)

    started = time.monotonic()
    report = preflight_comfyui_runtime(timeout_seconds=0.02)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert report["status"] == "action_required"
    assert any("preflight deadline exceeded" in warning for warning in report["warnings"])
    assert closed.wait(0.3)


def test_preflight_shared_deadline_stops_streamed_read_that_ignores_timeout_hints(
    monkeypatch,
) -> None:
    closed = threading.Event()

    class SlowReadResponse:
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size=-1) -> bytes:
            time.sleep(0.229)
            return b'{"SaveGLB": {}}'

        def close(self) -> None:
            closed.set()

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: SlowReadResponse(),
    )

    started = time.monotonic()
    report = preflight_comfyui_runtime(timeout_seconds=0.02)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert report["status"] == "action_required"
    assert any("preflight deadline exceeded" in warning for warning in report["warnings"])
    assert closed.wait(0.3)


def test_preflight_deadline_covers_slow_second_json_parse(monkeypatch) -> None:
    real_loads = comfyui_runtime.json.loads
    parse_started = threading.Event()
    load_calls = 0
    payloads = iter((b'{"system": {}}', b'{"SaveGLB": {}}'))
    monkeypatch.setattr(
        comfyui_runtime,
        "_transport_slots",
        threading.BoundedSemaphore(comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS),
    )

    class Response:
        headers: dict[str, str] = {}

        def __init__(self, payload: bytes) -> None:
            self._payload = payload
            self._read = False

        def read(self, _size=-1) -> bytes:
            if self._read:
                return b""
            self._read = True
            return self._payload

        def close(self) -> None:
            return None

    def slow_second_loads(value: str, *args, **kwargs):
        nonlocal load_calls
        load_calls += 1
        if load_calls == 2:
            parse_started.set()
            time.sleep(0.08)
        return real_loads(value, *args, **kwargs)

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: Response(next(payloads)),
    )
    monkeypatch.setattr(comfyui_runtime.json, "loads", slow_second_loads)

    started = time.monotonic()
    report = preflight_comfyui_runtime(timeout_seconds=0.03)
    elapsed = time.monotonic() - started

    assert parse_started.wait(0.05)
    assert elapsed < 0.15
    assert report["status"] == "action_required"
    assert any("preflight deadline exceeded" in warning for warning in report["warnings"])


def test_preflight_deadline_covers_slow_second_required_node_iteration(monkeypatch) -> None:
    second_iteration_started = threading.Event()
    payloads = iter((b'{"system": {}}', b'{"SaveGLB": {}}'))
    monkeypatch.setattr(
        comfyui_runtime,
        "_transport_slots",
        threading.BoundedSemaphore(comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS),
    )

    class SleepyRequiredNodes:
        def __iter__(self):
            yield "SaveGLB"
            second_iteration_started.set()
            time.sleep(0.08)
            yield "LoadImage"

    class Response:
        headers: dict[str, str] = {}

        def __init__(self, payload: bytes) -> None:
            self._payload = payload
            self._read = False

        def read(self, _size=-1) -> bytes:
            if self._read:
                return b""
            self._read = True
            return self._payload

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: Response(next(payloads)),
    )

    started = time.monotonic()
    report = preflight_comfyui_runtime(
        timeout_seconds=0.03,
        required_nodes=SleepyRequiredNodes(),
    )
    elapsed = time.monotonic() - started

    assert second_iteration_started.wait(0.05)
    assert elapsed < 0.15
    assert report["status"] == "action_required"
    assert any("preflight deadline exceeded" in warning for warning in report["warnings"])


def test_call_until_deadline_recomputes_remaining_time_after_slot_acquisition(
    monkeypatch,
) -> None:
    released = threading.Event()

    class SlowAcquireSlot:
        def acquire(self, *, timeout: float) -> bool:
            assert timeout > 0
            time.sleep(0.04)
            return True

        def release(self) -> None:
            released.set()

    monkeypatch.setattr(comfyui_runtime, "_transport_slots", SlowAcquireSlot())
    deadline = time.monotonic() + 0.05

    started = time.monotonic()
    with pytest.raises(comfyui_runtime._PreflightDeadlineExceeded):
        comfyui_runtime._call_until_deadline(
            lambda: time.sleep(0.08),
            deadline,
            operation_name="stalled test callback",
        )
    elapsed = time.monotonic() - started

    assert elapsed < 0.07
    assert released.wait(0.15)


def test_call_until_deadline_releases_slot_when_thread_start_fails(monkeypatch) -> None:
    slots = threading.BoundedSemaphore(1)

    class FailingThread:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def start(self) -> None:
            raise RuntimeError("thread creation failed")

    monkeypatch.setattr(comfyui_runtime, "_transport_slots", slots)
    monkeypatch.setattr(comfyui_runtime.threading, "Thread", FailingThread)

    with pytest.raises(RuntimeError, match="thread creation failed"):
        comfyui_runtime._call_until_deadline(
            lambda: None,
            time.monotonic() + 0.1,
            operation_name="thread-start test callback",
        )

    assert slots.acquire(blocking=False)
    slots.release()


def test_preflight_attempts_response_close_after_a_stalled_read_deadline(
    monkeypatch,
) -> None:
    close_started = threading.Event()
    monkeypatch.setattr(
        comfyui_runtime,
        "_transport_slots",
        threading.BoundedSemaphore(comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS),
    )

    class DelayedReadResponse:
        headers: dict[str, str] = {}

        def read(self, _size=-1) -> bytes:
            time.sleep(0.06)
            return b""

        def close(self) -> None:
            close_started.set()

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: DelayedReadResponse(),
    )

    started = time.monotonic()
    report = preflight_comfyui_runtime(timeout_seconds=0.02)
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    assert close_started.wait(0.15)
    assert report["status"] == "action_required"


def test_preflight_deadline_covers_response_close_without_entering_context_exit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        comfyui_runtime,
        "_transport_slots",
        threading.BoundedSemaphore(comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS),
    )
    close_started = threading.Event()
    exit_entered = threading.Event()

    class SleepyCleanupResponse:
        headers: dict[str, str] = {}

        def __init__(self) -> None:
            self._reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            exit_entered.set()
            time.sleep(0.229)

        def read(self, _size=-1) -> bytes:
            self._reads += 1
            return b'{"SaveGLB": {}}' if self._reads == 1 else b""

        def close(self) -> None:
            close_started.set()
            time.sleep(0.229)

    monkeypatch.setattr(
        comfyui_runtime,
        "_open_response",
        lambda *_args, **_kwargs: SleepyCleanupResponse(),
    )

    started = time.monotonic()
    report = preflight_comfyui_runtime(timeout_seconds=0.02)
    elapsed = time.monotonic() - started

    assert close_started.wait(0.05)
    assert elapsed < 0.15
    assert exit_entered.is_set() is False
    assert report["status"] == "action_required"
    assert any("preflight deadline exceeded" in warning for warning in report["warnings"])


def test_permanently_blocked_close_caps_live_transport_workers(monkeypatch) -> None:
    slots = threading.BoundedSemaphore(
        comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS
    )
    monkeypatch.setattr(comfyui_runtime, "_transport_slots", slots)
    release_close = threading.Event()
    close_started = threading.Event()
    opened = 0
    opened_lock = threading.Lock()

    class BlockingCloseResponse:
        headers: dict[str, str] = {}

        def __init__(self) -> None:
            self._reads = 0

        def read(self, _size=-1) -> bytes:
            self._reads += 1
            return b'{"SaveGLB": {}}' if self._reads == 1 else b""

        def close(self) -> None:
            close_started.set()
            release_close.wait(1)

    def open_blocking_response(*_args, **_kwargs) -> BlockingCloseResponse:
        nonlocal opened
        with opened_lock:
            opened += 1
        return BlockingCloseResponse()

    monkeypatch.setattr(comfyui_runtime, "_open_response", open_blocking_response)
    try:
        assert preflight_comfyui_runtime(timeout_seconds=0.02)["status"] == "action_required"
        assert close_started.wait(0.05)
        assert preflight_comfyui_runtime(timeout_seconds=0.02)["status"] == "action_required"

        started = time.monotonic()
        report = preflight_comfyui_runtime(timeout_seconds=0.02)
        elapsed = time.monotonic() - started

        assert report["status"] == "action_required"
        assert elapsed < 0.15
        assert opened == comfyui_runtime.MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS
    finally:
        release_close.set()


def test_redirect_derives_its_timeout_from_the_shared_deadline(monkeypatch) -> None:
    class Request:
        full_url = "http://127.0.0.1:8188/system_stats"
        timeout = 10.0

    class Response:
        closed = False

        def close(self) -> None:
            self.closed = True

    class Parent:
        def __init__(self) -> None:
            self.calls: list[tuple[object, float]] = []

        def open(self, request, *, timeout: float):
            self.calls.append((request, timeout))
            return "redirected"

    class RedirectRequest:
        pass

    response = Response()
    parent = Parent()
    handler = comfyui_runtime._DeadlineRedirectHandler(deadline=20.0)
    handler.parent = parent
    handler.redirect_request = lambda *_args: RedirectRequest()
    monkeypatch.setattr(comfyui_runtime.time, "monotonic", lambda: 13.0)

    result = handler.http_error_302(
        Request(),
        response,
        302,
        "Found",
        {"location": "/object_info"},
    )

    assert result == "redirected"
    assert response.closed is True
    assert len(parent.calls) == 1
    assert parent.calls[0][1] == 7.0
