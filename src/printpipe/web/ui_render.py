"""HTML fragment for the slicer-settings panel.

Pure rendering helper: returns a self-contained fragment (a container
section, the JS mount point, the asset <link>/<script> tags, and the
init call) that the integrator injects into the run-detail page per the
panel anchor. No routing and no server state live here.
"""

from __future__ import annotations

from html import escape
from json import dumps


def render_settings_panel(run_id: str, material: str) -> str:
    """Return the slicer-settings panel fragment for a single run.

    The fragment loads ``/static/settings.css`` and ``/static/settings.js``
    (served by the binary static route) and calls
    ``window.PrintPipeSettings.init`` against a per-panel mount id so the
    panel can appear more than once on a page without colliding.
    """
    safe_run_id = escape(str(run_id), quote=True)
    safe_material = escape(str(material), quote=True)
    mount_id = f"ppset-mount-{escape(str(run_id), quote=True)}"

    # json.dumps gives correctly escaped, quoted JS string literals. It does
    # NOT escape "<"/">"/"&", so a value containing "</script>" could break
    # out of the inline <script>; neutralise those sequences as \uXXXX.
    init_config = (
        dumps(
            {"material": str(material), "runId": str(run_id), "mountId": mount_id},
            sort_keys=True,
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    return "\n".join(
        [
            '        <link rel="stylesheet" href="/static/settings.css">',
            (
                '        <section class="ppset-panel" '
                f'data-run-id="{safe_run_id}" data-material="{safe_material}">'
            ),
            f'          <div id="{mount_id}" class="ppset-mount"></div>',
            "        </section>",
            '        <script src="/static/settings.js"></script>',
            "        <script>",
            f"          window.PrintPipeSettings.init({init_config});",
            "        </script>",
        ]
    )


__all__ = ["render_settings_panel"]
