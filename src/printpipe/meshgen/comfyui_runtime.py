"""Runtime preflight helpers for ComfyUI API providers."""

from __future__ import annotations

import json
import os
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"
DEFAULT_REQUIRED_NODES = ("SaveGLB",)
COMFYUI_ALLOWED_HOSTS_ENV = "PRINTPIPE_COMFYUI_ALLOWED_HOSTS"


def preflight_comfyui_runtime(
    comfyui_url: str = DEFAULT_COMFYUI_URL,
    *,
    timeout_seconds: float = 3.0,
    required_nodes: tuple[str, ...] = DEFAULT_REQUIRED_NODES,
) -> dict[str, Any]:
    """Check whether a ComfyUI API endpoint is reachable and has needed nodes."""

    normalized_url = validate_comfyui_url(comfyui_url)
    warnings: list[str] = []
    system_stats = _get_json(normalized_url, "/system_stats", timeout_seconds)
    object_info = _get_json(normalized_url, "/object_info", timeout_seconds)
    api_reachable = system_stats["ok"]
    object_info_reachable = object_info["ok"] and isinstance(object_info.get("json"), dict)
    if not api_reachable:
        warnings.append(f"ComfyUI /system_stats check failed: {system_stats['error']}")
    if not object_info_reachable:
        error = str(object_info.get("error") or "response was not a JSON object")
        warnings.append(f"ComfyUI /object_info check failed: {error}")

    available_nodes = sorted(str(key) for key in _dict(object_info.get("json")).keys())
    missing_nodes = [
        node
        for node in required_nodes
        if node not in _dict(object_info.get("json"))
    ]
    if missing_nodes:
        warnings.append(
            "ComfyUI is reachable, but required node(s) are missing: "
            + ", ".join(missing_nodes)
        )

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
        "required_nodes": list(required_nodes),
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


def _get_json(base_url: str, path: str, timeout_seconds: float) -> dict[str, Any]:
    url = urljoin(base_url + "/", path.lstrip("/"))
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            body = response.read()
    except HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}"}
    except (OSError, URLError, TimeoutError) as exc:
        return {"ok": False, "error": str(exc)}
    try:
        return {"ok": True, "json": json.loads(body.decode("utf-8"))}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"invalid JSON: {exc}"}


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


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _join(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
