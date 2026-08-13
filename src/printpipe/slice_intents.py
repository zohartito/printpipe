"""Natural-language slicer intents -> validated Bambu overrides (all groups).

This is the deterministic translation layer between conversational requests
("make it stronger", "run the bed hotter") and the flat Bambu keyspace that
``slice_with_settings`` applies. Keeping the intent->settings mapping in code
(not in the model) means a smaller or local model only has to pick intent
*names* — the concrete key changes, group routing, relative-value math,
conflict handling, and key validation stay deterministic and testable here.

Each intent override value is either:
  * an ABSOLUTE token  — "4", "40%", "tree(auto)", "top surfaces"
  * a RELATIVE directive against the current value — "+5", "-5", "*0.5"
Relative directives are resolved against the live keyspace, so a "+5" nozzle
bump lands correctly whether the material currently prints at 220 or 250, and
disabled settings (value 0, e.g. an unused build plate) are left untouched.
Any token whose first character is +, -, or * followed by a number is treated
as RELATIVE; a negative absolute value therefore cannot be set this way.

Each override key is auto-routed to its group (process / filament / printer) by
looking it up in the resolved keyspace, so a single intent can span groups.
``resolve_intents`` returns one override dict per group, each ready to pass to
the matching ``slice_with_settings`` argument.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from printpipe.pipeline import resolve_slice_settings

_GROUPS = ("process", "filament", "printer")


@dataclass(frozen=True)
class SliceIntent:
    """One named, curated bundle of Bambu overrides (may span groups)."""

    name: str
    summary: str
    overrides: Mapping[str, str]
    rationale: str


# Curated starter vocabulary. Every key here is validated against the live
# keyspace by tests/test_slice_intents.py, so typos cannot ship.
INTENTS: dict[str, SliceIntent] = {
    # --- process group -----------------------------------------------------
    "stronger": SliceIntent(
        name="stronger",
        summary="More walls, denser infill, and thicker shells for load-bearing parts.",
        overrides={
            "wall_loops": "4",
            "sparse_infill_density": "40%",
            "top_shell_layers": "6",
            "bottom_shell_layers": "4",
        },
        rationale=(
            "Perimeters carry most of a print's strength; more walls plus denser "
            "infill and thicker shells resist load and layer separation. Costs time "
            "and plastic."
        ),
    ),
    "lightweight": SliceIntent(
        name="lightweight",
        summary="Less plastic and faster, for non-structural or draft parts.",
        overrides={
            "sparse_infill_density": "8%",
            "sparse_infill_pattern": "gyroid",
        },
        rationale=(
            "Gyroid at low density keeps near-isotropic stiffness per gram while "
            "cutting material and time on parts that don't bear load."
        ),
    ),
    "fine_detail": SliceIntent(
        name="fine_detail",
        summary="Thin layers for crisp detail and smooth curves.",
        overrides={"layer_height": "0.12"},
        rationale=(
            "0.12 mm layers reduce stair-stepping on curves and small features, at "
            "the cost of noticeably longer print time."
        ),
    ),
    "draft": SliceIntent(
        name="draft",
        summary="Thick layers for the fastest possible print.",
        overrides={"layer_height": "0.28"},
        rationale=(
            "0.28 mm layers move the most plastic per pass for the fastest print; "
            "layer lines are clearly visible."
        ),
    ),
    "smooth_top": SliceIntent(
        name="smooth_top",
        summary="Iron the top surface flat and add top layers for a clean finish.",
        overrides={
            "ironing_type": "top surfaces",
            "top_shell_layers": "6",
        },
        rationale=(
            "Ironing reflows the top skin for a smooth finish; extra top layers "
            "prevent pillowing and gaps over infill."
        ),
    ),
    "needs_supports": SliceIntent(
        name="needs_supports",
        summary="Enable tree supports for overhangs and bridges.",
        overrides={
            "enable_support": "1",
            "support_type": "tree(auto)",
            "support_threshold_angle": "30",
        },
        rationale=(
            "Tree supports use less material and peel off more cleanly; a 30 degree "
            "threshold catches steep overhangs that would sag unsupported."
        ),
    ),
    "strong_adhesion": SliceIntent(
        name="strong_adhesion",
        summary="Wider brim and slower first layer to stop warping and lifting.",
        overrides={
            "brim_width": "8",
            "initial_layer_speed": "30",
        },
        rationale=(
            "A wider brim and slower first layer improve bed grip on tall or "
            "small-footprint parts that are prone to lifting at the corners."
        ),
    ),
    # --- filament group (relative temps so they track the material) --------
    "hotter_nozzle": SliceIntent(
        name="hotter_nozzle",
        summary="Raise nozzle temperature by 5 C for better layer adhesion.",
        overrides={
            "nozzle_temperature": "+5",
            "nozzle_temperature_initial_layer": "+5",
        },
        rationale=(
            "A few degrees hotter improves inter-layer bonding and flow on tall or "
            "fast prints, at the cost of slightly more stringing."
        ),
    ),
    "cooler_nozzle": SliceIntent(
        name="cooler_nozzle",
        summary="Lower nozzle temperature by 5 C to reduce stringing and ooze.",
        overrides={
            "nozzle_temperature": "-5",
            "nozzle_temperature_initial_layer": "-5",
        },
        rationale=(
            "A slightly cooler nozzle reduces stringing, blobbing, and heat creep on "
            "fine detail, at the cost of a little layer strength."
        ),
    ),
    "hotter_bed": SliceIntent(
        name="hotter_bed",
        summary="Raise the active build-plate temperature by 5 C for adhesion.",
        overrides={
            "cool_plate_temp": "+5",
            "cool_plate_temp_initial_layer": "+5",
            "eng_plate_temp": "+5",
            "eng_plate_temp_initial_layer": "+5",
            "hot_plate_temp": "+5",
            "hot_plate_temp_initial_layer": "+5",
            "textured_plate_temp": "+5",
            "textured_plate_temp_initial_layer": "+5",
        },
        rationale=(
            "Bumps every plate-temperature so whichever build plate is active prints "
            "warmer for better first-layer grip. Disabled plates (temp 0) are left "
            "off."
        ),
    ),
    "cooler_bed": SliceIntent(
        name="cooler_bed",
        summary="Lower the active build-plate temperature by 5 C.",
        overrides={
            "cool_plate_temp": "-5",
            "cool_plate_temp_initial_layer": "-5",
            "eng_plate_temp": "-5",
            "eng_plate_temp_initial_layer": "-5",
            "hot_plate_temp": "-5",
            "hot_plate_temp_initial_layer": "-5",
            "textured_plate_temp": "-5",
            "textured_plate_temp_initial_layer": "-5",
        },
        rationale=(
            "Cools every active plate-temperature by 5 C to ease part release and "
            "reduce elephant-foot on materials that don't need a hot bed."
        ),
    ),
    # --- printer group -----------------------------------------------------
    "quiet": SliceIntent(
        name="quiet",
        summary="Halve max X/Y acceleration for a quieter, gentler print.",
        overrides={
            "machine_max_acceleration_x": "*0.5",
            "machine_max_acceleration_y": "*0.5",
        },
        rationale=(
            "Lower acceleration limits cut the sharp direction-change noise and "
            "ringing/ghosting, trading some print speed for quiet and surface "
            "quality."
        ),
    ),
}


SLICE_CHAT_SYSTEM_PROMPT = """\
You help a user prepare 3D prints for a Bambu Lab P2S by changing slicer settings \
in plain language, using the printpipe-slicer MCP tools.

Loop for every request:
1. Map the request to one or more intent names with list_slice_intents (call it \
once, then reuse). Prefer named intents over hand-picking raw keys.
2. Call resolve_slice_intents to turn those names into concrete overrides. It \
returns process_overrides, filament_overrides, and printer_overrides separately, \
plus before->after changes and conflicts. ALWAYS show the user the changes BEFORE \
slicing — never silently change settings.
3. Call slice_with_settings, passing each non-empty group to its matching argument: \
overrides=process_overrides, filament_overrides=..., printer_overrides=.... Then \
get_fabrication_report on the returned run_root.
4. Report ready_to_print. If not ready, name the failing check, propose the fix, \
re-slice.

Rules:
- One material per job; pass it through every call (default "Generic PLA").
- For a SPECIFIC value request ("nozzle at 230", "bed to 60") that no intent covers, \
first read the current value with get_slice_settings, then set the exact key via \
the right override group (nozzle/bed temps are FILAMENT keys, motion limits are \
PRINTER keys).
- If two intents conflict (e.g. 'draft' vs 'fine_detail' on layer_height, or \
'hotter_nozzle' vs 'cooler_nozzle'), surface the conflict and ask — do not pick \
silently.
- State the trade-off in one line when you apply an intent.
- Never claim a print is ready unless get_fabrication_report says ready_to_print \
is true.
"""


def list_intents() -> list[dict[str, Any]]:
    """The intent catalog: name, summary, rationale, and raw override directives."""

    return [
        {
            "name": intent.name,
            "summary": intent.summary,
            "rationale": intent.rationale,
            "overrides": dict(intent.overrides),
        }
        for intent in INTENTS.values()
    ]


def _display(value: Any) -> Any:
    """Unwrap Bambu's single-element list form for readable before/after values."""

    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _norm(value: Any) -> str:
    """Stable comparison key for resolved values (list or scalar)."""

    return json.dumps(value, sort_keys=True)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value] if value is not None else []


def _fmt_number(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)


def _group_of(key: str, groups: Mapping[str, Mapping[str, Any]]) -> str | None:
    for group in _GROUPS:
        if key in groups[group]:
            return group
    return None


def _resolve_value(directive: str, current: Any) -> tuple[str, Any]:
    """Resolve one override directive against the current keyspace value.

    Returns (status, value) where status is:
      * "set"        -> value is the absolute value to write
      * "noop"       -> the directive would not change the current value
      * "unresolved" -> a relative directive against a missing/non-numeric value
    """

    if not (isinstance(directive, str) and directive[:1] and directive[0] in "+-*"):
        return ("set", directive)  # absolute token (incl. the empty string)

    operator, magnitude = directive[0], directive[1:].strip()
    try:
        factor = float(magnitude)
    except ValueError:
        return ("set", directive)  # not a relative directive after all

    if current is None:
        return ("unresolved", None)

    resolved: list[str] = []
    changed = False
    for element in _as_list(current):
        try:
            value = float(element)
        except (TypeError, ValueError):
            return ("unresolved", None)
        if operator in "+-":
            if value == 0:  # disabled setting — leave it off
                resolved.append(_fmt_number(value))
                continue
            new_value = value + factor if operator == "+" else value - factor
        else:  # "*"
            new_value = value * factor
        if _fmt_number(new_value) != _fmt_number(value):
            changed = True
        resolved.append(_fmt_number(new_value))

    if not changed:
        return ("noop", None)
    return ("set", resolved)


def resolve_intents(
    intent_names: Sequence[str],
    *,
    material: str = "Generic PLA",
) -> dict[str, Any]:
    """Merge named intents into validated, group-routed override maps.

    Intents are applied in the given order; when two set the same key the later
    one wins and the clash is reported in ``conflicts``. Each override key is
    routed to its group (process / filament / printer) and relative directives
    are resolved against the live keyspace. The returned ``*_overrides`` dicts
    are ready to pass to the matching ``slice_with_settings`` argument.
    """

    requested = list(intent_names)
    applied = [name for name in requested if name in INTENTS]
    unknown_intents = [name for name in requested if name not in INTENTS]

    keyspace = resolve_slice_settings(material)
    groups = {group: keyspace.get(group, {}) for group in _GROUPS}

    # key -> [(intent_name, directive), ...] in application order.
    setters_by_key: dict[str, list[tuple[str, str]]] = {}
    for name in applied:
        for key, directive in INTENTS[name].overrides.items():
            setters_by_key.setdefault(key, []).append((name, directive))

    overrides: dict[str, dict[str, Any]] = {group: {} for group in _GROUPS}
    changes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    unknown_keys: list[str] = []
    unresolved: list[dict[str, Any]] = []

    for key, setters in setters_by_key.items():
        group = _group_of(key, groups)
        if group is None:
            unknown_keys.append(key)
            continue
        current = groups[group].get(key)

        status, value = _resolve_value(setters[-1][1], current)  # last intent wins
        if status == "unresolved":
            unresolved.append({"key": key, "group": group, "directive": setters[-1][1]})
            continue
        if status == "noop":
            continue

        overrides[group][key] = value

        resolved_by_intent = [
            (name, directive, _resolve_value(directive, current))
            for name, directive in setters
        ]
        usable = [
            {"intent": name, "directive": directive, "value": _display(res[1])}
            for name, directive, res in resolved_by_intent
            if res[0] == "set"  # exclude noop (value None) and unresolved from the clash test
        ]
        if len({_norm(item["value"]) for item in usable}) > 1:
            conflicts.append({"key": key, "group": group, "resolved_to": _display(value), "set_by": usable})

        changes.append(
            {
                "key": key,
                "group": group,
                "from": _display(current),
                "to": _display(value),
                "set_by": [name for name, _ in setters],
            }
        )

    changes.sort(key=lambda change: (change["group"], change["key"]))
    return {
        "material": material,
        "requested_intents": requested,
        "applied_intents": applied,
        "unknown_intents": unknown_intents,
        "process_overrides": overrides["process"],
        "filament_overrides": overrides["filament"],
        "printer_overrides": overrides["printer"],
        "changes": changes,
        "conflicts": conflicts,
        "unknown_keys": sorted(unknown_keys),
        "unresolved": unresolved,
    }
