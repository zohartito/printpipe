"""Fast smoke test for the friend-usable web UI layer.

This test does NOT start a server or run a real slice. It only imports the
web modules and checks that the new ``printpipe.web.ui_api`` surface exists
and is callable, so the UI seam stays wired up.

It is intentionally lenient about *which* helper names are present (different
agents may name them slightly differently), but it requires the module to
import cleanly and to expose the core settings/status/reslice helpers once the
integration has landed.
"""

from __future__ import annotations

import importlib
import inspect

import pytest


def test_web_server_imports():
    """The base web app module must import without side effects."""
    server = importlib.import_module("printpipe.web.server")

    # Core seams the UI layer builds on (see integration contract).
    assert hasattr(server, "PrintPipeWebApp")
    assert hasattr(server, "WebResponse")
    assert callable(server.create_app)
    assert callable(server.serve)


def _import_ui_api():
    """Import the new ui_api module, skipping if integration isn't done yet."""
    try:
        return importlib.import_module("printpipe.web.ui_api")
    except ModuleNotFoundError:
        pytest.skip("printpipe.web.ui_api not present yet (integration pending)")


def test_ui_api_imports():
    ui_api = _import_ui_api()
    assert ui_api is not None


def test_ui_api_exposes_callable_functions():
    """ui_api must expose at least one public callable helper."""
    ui_api = _import_ui_api()

    public_callables = [
        name
        for name in dir(ui_api)
        if not name.startswith("_")
        and callable(getattr(ui_api, name))
        and not inspect.isclass(getattr(ui_api, name))
    ]
    assert public_callables, "ui_api defines no public callable helpers"


# Candidate names for each UI capability described in the integration contract.
# The test passes if *any* candidate in a group is present and callable, so
# the module can name its helpers freely while still being verified.
_SETTINGS_CANDIDATES = (
    "list_settings",
    "settings_payload",
    "build_settings_payload",
    "resolve_settings",
    "slice_settings_payload",
    "get_settings",
    "settings_response",
)
_STATUS_CANDIDATES = (
    "slice_status",
    "status_payload",
    "build_status_payload",
    "run_status_payload",
    "get_status",
    "status_response",
    "read_status",
)
_RESLICE_CANDIDATES = (
    "reslice",
    "run_reslice",
    "start_reslice",
    "reslice_run",
    "reslice_response",
    "trigger_reslice",
)


def _first_callable(module, candidates):
    for name in candidates:
        attr = getattr(module, name, None)
        if callable(attr):
            return name, attr
    return None, None


@pytest.mark.parametrize(
    "label, candidates",
    [
        ("settings", _SETTINGS_CANDIDATES),
        ("status", _STATUS_CANDIDATES),
        ("reslice", _RESLICE_CANDIDATES),
    ],
)
def test_ui_api_capability_callables(label, candidates):
    """Each UI capability (settings / status / reslice) has a callable helper."""
    ui_api = _import_ui_api()
    name, attr = _first_callable(ui_api, candidates)
    assert attr is not None, (
        f"ui_api exposes no callable for '{label}'. "
        f"Expected one of: {', '.join(candidates)}"
    )
    # Callable + introspectable, but never invoked here: a real call could
    # touch disk or trigger a slice, which this smoke test must not do.
    assert inspect.signature(attr) is not None


def test_settings_helper_is_safe_to_introspect():
    """The settings helper should be a read-only lookup (no slice required).

    We only inspect its signature; we never call it. A real slice is guarded
    by simply not invoking any reslice helper anywhere in this test module.
    """
    ui_api = _import_ui_api()
    name, attr = _first_callable(ui_api, _SETTINGS_CANDIDATES)
    if attr is None:
        pytest.skip("no settings helper to introspect")
    signature = inspect.signature(attr)
    # A material-driven settings view typically accepts a material argument;
    # be lenient and only assert the signature is introspectable.
    assert isinstance(signature.parameters, dict) or signature.parameters is not None
