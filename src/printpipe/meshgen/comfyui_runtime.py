"""Runtime preflight helpers for ComfyUI API providers."""

from __future__ import annotations

import json
import math
import os
import queue
import string
import threading
import time
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunparse
from urllib.request import HTTPRedirectHandler, build_opener


DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"
DEFAULT_REQUIRED_NODES = ("SaveGLB",)
COMFYUI_ALLOWED_HOSTS_ENV = "PRINTPIPE_COMFYUI_ALLOWED_HOSTS"
MAX_COMFYUI_PREFLIGHT_TIMEOUT_SECONDS = 10.0
MAX_COMFYUI_PREFLIGHT_RESPONSE_BYTES = 1_048_576
MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS = 2
MAX_COMFYUI_PREFLIGHT_REQUIRED_NODES = 128
_transport_slots = threading.BoundedSemaphore(MAX_COMFYUI_PREFLIGHT_TRANSPORT_CALLS)


class _PreflightDeadlineExceeded(TimeoutError):
    """Raised when a preflight operation exhausts its shared deadline."""


class _DeadlineRedirectHandler(HTTPRedirectHandler):
    """Follow redirects only while the original preflight budget remains."""

    def __init__(self, deadline: float) -> None:
        super().__init__()
        self._deadline = deadline

    def http_error_302(self, req, fp, code, msg, headers):
        if "location" in headers:
            newurl = headers["location"]
        elif "uri" in headers:
            newurl = headers["uri"]
        else:
            return None
        urlparts = urlparse(newurl)
        if urlparts.scheme not in {"http", "https", ""}:
            raise HTTPError(
                newurl,
                code,
                f"{msg} - Redirection to url '{newurl}' is not allowed",
                headers,
                fp,
            )
        if not urlparts.path and urlparts.netloc:
            urlparts = list(urlparts)
            urlparts[2] = "/"
        newurl = quote(
            urlunparse(urlparts),
            encoding="iso-8859-1",
            safe=string.punctuation,
        )
        newurl = urljoin(req.full_url, newurl)
        new = self.redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        if hasattr(req, "redirect_dict"):
            visited = new.redirect_dict = req.redirect_dict
            if (
                visited.get(newurl, 0) >= self.max_repeats
                or len(visited) >= self.max_redirections
            ):
                raise HTTPError(req.full_url, code, self.inf_msg + msg, headers, fp)
        else:
            visited = new.redirect_dict = req.redirect_dict = {}
        visited[newurl] = visited.get(newurl, 0) + 1
        fp.close()
        return self.parent.open(new, timeout=_remaining_timeout(self._deadline))

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def preflight_comfyui_runtime(
    comfyui_url: str = DEFAULT_COMFYUI_URL,
    *,
    timeout_seconds: float = 3.0,
    required_nodes: tuple[str, ...] = DEFAULT_REQUIRED_NODES,
) -> dict[str, Any]:
    """Check whether a ComfyUI API endpoint is reachable and has needed nodes."""

    normalized_url = validate_comfyui_url(comfyui_url)
    bounded_timeout = validate_comfyui_preflight_timeout(timeout_seconds)
    deadline = time.monotonic() + bounded_timeout
    try:
        return _call_until_deadline(
            lambda: _preflight_transaction(normalized_url, required_nodes, deadline),
            deadline,
            operation_name="complete ComfyUI preflight transaction",
        )
    except (OSError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        return _preflight_failure_report(
            normalized_url,
            _fallback_required_nodes(required_nodes),
            str(exc),
        )


def _preflight_transaction(
    normalized_url: str,
    required_nodes: tuple[str, ...],
    deadline: float,
) -> dict[str, Any]:
    """Perform transport, parsing, aggregation, and final decision in one worker."""

    required_node_names = _materialize_required_nodes(required_nodes, deadline)
    warnings: list[str] = []
    system_stats = _get_json(normalized_url, "/system_stats", deadline)
    object_info = _get_json(normalized_url, "/object_info", deadline)
    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)

    api_reachable = system_stats["ok"]
    object_keys = object_info.get("object_keys")
    object_info_reachable = object_info["ok"] and isinstance(object_keys, tuple)

    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)
    if not api_reachable:
        warnings.append(f"ComfyUI /system_stats check failed: {system_stats['error']}")

    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)
    if not object_info_reachable:
        error = str(object_info.get("error") or "response was not a JSON object")
        warnings.append(f"ComfyUI /object_info check failed: {error}")

    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)
    available_nodes = list(object_keys) if object_info_reachable else []
    missing_nodes = [
        node
        for node in required_node_names
        if node not in available_nodes
    ]

    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)
    if missing_nodes:
        warnings.append(
            "ComfyUI is reachable, but required node(s) are missing: "
            + ", ".join(missing_nodes)
        )

    if _deadline_expired(deadline):
        return _deadline_expired_report(normalized_url, required_node_names)
    status = (
        "ready"
        if api_reachable and object_info_reachable and not missing_nodes
        else "action_required"
    )
    return {
        "schema_version": 1,
        "status": status,
        "comfyui_url": normalized_url,
        "api_reachable": api_reachable,
        "object_info_reachable": object_info_reachable,
        "required_nodes": list(required_node_names),
        "missing_nodes": missing_nodes,
        "available_node_count": len(available_nodes),
        "warnings": warnings,
    }


def render_comfyui_runtime_preflight(report: dict[str, Any]) -> str:
    """Render a terminal-readable ComfyUI runtime preflight report."""

    lines = [
        f"ComfyUI runtime: {report.get('comfyui_url', '')}",
        f"status: {report.get('status', 'unknown')}",
        f"API reachable: {_yes_no(bool(report.get('api_reachable')))}",
        f"object info reachable: {_yes_no(bool(report.get('object_info_reachable')))}",
        "required nodes: " + _join(report.get("required_nodes")),
        "missing nodes: " + _join(report.get("missing_nodes")),
        f"available node count: {report.get('available_node_count', 0)}",
    ]
    warnings = report.get("warnings", [])
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _get_json(base_url: str, path: str, deadline: float) -> dict[str, Any]:
    url = urljoin(base_url + "/", path.lstrip("/"))
    try:
        object_keys = _fetch_and_extract_json(url, deadline)
    except HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}"}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except (OSError, URLError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "object_keys": object_keys}


def _open_response(url: str, deadline: float) -> Any:
    opener = build_opener(_DeadlineRedirectHandler(deadline))
    return opener.open(url, timeout=_remaining_timeout(deadline))


def _fetch_response_body(url: str, deadline: float) -> bytes:
    """Own a response lifecycle entirely within the bounded transport worker."""

    response = _open_response(url, deadline)
    try:
        content_length = response.headers.get("Content-Length")
        if (
            content_length is not None
            and int(content_length) > MAX_COMFYUI_PREFLIGHT_RESPONSE_BYTES
        ):
            raise ValueError("response exceeds preflight byte limit")
        return _read_response_limited(response, deadline)
    finally:
        _close_response(response)


def _fetch_and_extract_json(url: str, deadline: float) -> tuple[str, ...] | None:
    """Return only the JSON-object key shape from the bounded worker transaction."""

    body = _fetch_response_body(url, deadline)
    try:
        decoded = body.decode("utf-8")
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    _remaining_timeout(deadline)
    if not isinstance(parsed, dict):
        return None
    # The preflight needs only node names, never arbitrary response values.
    object_keys = tuple(sorted(parsed))
    _remaining_timeout(deadline)
    return object_keys


def _read_response_limited(response: Any, deadline: float) -> bytes:
    """Read a preflight response without buffering more than the fixed budget."""

    chunks: list[bytes] = []
    total = 0
    while True:
        _remaining_timeout(deadline)
        read_size = min(65_536, MAX_COMFYUI_PREFLIGHT_RESPONSE_BYTES + 1 - total)
        chunk = response.read(read_size)
        _remaining_timeout(deadline)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > MAX_COMFYUI_PREFLIGHT_RESPONSE_BYTES:
            raise ValueError("response exceeds preflight byte limit")
        chunks.append(chunk)


def _close_response(response: Any) -> None:
    """Close inside the worker, which retains its slot until cleanup finishes."""

    close = getattr(response, "close", None)
    if callable(close):
        close()


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _PreflightDeadlineExceeded("preflight deadline exceeded")
    return remaining


def _deadline_expired(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _deadline_expired_report(
    normalized_url: str,
    required_nodes: tuple[str, ...],
) -> dict[str, Any]:
    """Keep a late aggregate decision from reporting a stale ready result."""

    return {
        "schema_version": 1,
        "status": "action_required",
        "comfyui_url": normalized_url,
        "api_reachable": False,
        "object_info_reachable": False,
        "required_nodes": list(required_nodes),
        "missing_nodes": list(required_nodes),
        "available_node_count": 0,
        "warnings": ["ComfyUI preflight deadline exceeded before readiness aggregation."],
    }


def _preflight_failure_report(
    normalized_url: str,
    required_nodes: tuple[str, ...],
    error: str,
) -> dict[str, Any]:
    """Return a conservative report when the transaction cannot complete."""

    return {
        "schema_version": 1,
        "status": "action_required",
        "comfyui_url": normalized_url,
        "api_reachable": False,
        "object_info_reachable": False,
        "required_nodes": list(required_nodes),
        "missing_nodes": list(required_nodes),
        "available_node_count": 0,
        "warnings": [f"ComfyUI preflight failed: {error}"],
    }


def _materialize_required_nodes(
    required_nodes: tuple[str, ...],
    deadline: float,
) -> tuple[str, ...]:
    """Copy caller input once under the transaction deadline into a bounded shape."""

    node_names: list[str] = []
    for node in required_nodes:
        _remaining_timeout(deadline)
        if not isinstance(node, str) or not node:
            raise ValueError("required ComfyUI nodes must be non-empty strings")
        if len(node_names) >= MAX_COMFYUI_PREFLIGHT_REQUIRED_NODES:
            raise ValueError(
                "too many required ComfyUI nodes for a bounded preflight transaction"
            )
        node_names.append(node)
    _remaining_timeout(deadline)
    return tuple(node_names)


def _fallback_required_nodes(required_nodes: tuple[str, ...]) -> tuple[str, ...]:
    """Avoid iterating a timed-out caller-owned iterable outside the worker."""

    if required_nodes is DEFAULT_REQUIRED_NODES:
        return DEFAULT_REQUIRED_NODES
    return ()


def _call_until_deadline(callback, deadline: float, *, operation_name: str):
    """Run one untrusted blocking transport operation under the shared deadline."""

    timeout = _remaining_timeout(deadline)
    slot = _transport_slots
    if not slot.acquire(timeout=timeout):
        raise _PreflightDeadlineExceeded(
            f"preflight deadline exceeded waiting for {operation_name}"
        )
    try:
        timeout = _remaining_timeout(deadline)
    except BaseException:
        slot.release()
        raise
    result: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
    expired = threading.Event()

    def run() -> None:
        try:
            try:
                value = callback()
            except BaseException as exc:  # Transport errors must reach the caller.
                value = exc
                succeeded = False
            else:
                succeeded = True
            if not expired.is_set():
                result.put((succeeded, value))
        finally:
            slot.release()

    thread = threading.Thread(target=run, daemon=True)
    try:
        thread.start()
    except BaseException:
        slot.release()
        raise
    try:
        succeeded, value = result.get(timeout=timeout)
    except queue.Empty as exc:
        expired.set()
        raise _PreflightDeadlineExceeded(
            f"preflight deadline exceeded during {operation_name}"
        ) from exc
    if time.monotonic() >= deadline:
        expired.set()
        raise _PreflightDeadlineExceeded(
            f"preflight deadline exceeded during {operation_name}"
        )
    if not succeeded:
        raise value
    return value


def validate_comfyui_preflight_timeout(value: float) -> float:
    """Require the operator-selected preflight timeout to remain finite and small."""

    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("ComfyUI preflight timeout must be a finite positive number.")
    if timeout > MAX_COMFYUI_PREFLIGHT_TIMEOUT_SECONDS:
        raise ValueError(
            "ComfyUI preflight timeout must not exceed "
            f"{MAX_COMFYUI_PREFLIGHT_TIMEOUT_SECONDS:g} seconds."
        )
    return timeout


def _normalize_base_url(value: str) -> str:
    stripped = str(value or "").strip() or DEFAULT_COMFYUI_URL
    return stripped.rstrip("/")


def validate_comfyui_url(value: str) -> str:
    """Return a normalized ComfyUI URL after enforcing the local allowlist."""

    normalized = _normalize_base_url(value)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("ComfyUI URL must use http or https.")
    if parsed.username or parsed.password:
        raise ValueError("ComfyUI URL must not include credentials.")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("ComfyUI URL must include a host.")
    if _is_loopback_host(hostname) or hostname in _allowed_comfyui_hosts():
        return normalized
    raise ValueError(
        "ComfyUI URL host is not allowed. Use localhost/127.0.0.1 or set "
        f"{COMFYUI_ALLOWED_HOSTS_ENV} to an explicit comma-separated host allowlist."
    )


def _is_loopback_host(hostname: str) -> bool:
    if hostname in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _allowed_comfyui_hosts() -> set[str]:
    raw = os.environ.get(COMFYUI_ALLOWED_HOSTS_ENV, "")
    return {host.strip().lower() for host in raw.split(",") if host.strip()}


def _join(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
