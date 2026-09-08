"""Modifiers — the non-destructive stack on an object (subdivision, bevel, array, boolean, ...)."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE

_SETTINGS_DOC = (
    "Modifier properties keyed by their bpy attribute name, e.g. {'levels': 2, 'render_levels': 3} for SUBSURF, "
    "{'width': 0.02, 'segments': 3} for BEVEL, {'count': 8, 'use_constant_offset': true, "
    "'constant_offset_displace': [1.5, 0, 0]} for ARRAY. Properties that point at another datablock take its NAME "
    "(BOOLEAN's 'object', ARMATURE's 'object', SHRINKWRAP's 'target'). An unknown key fails and the error lists every "
    "valid key — or call list_modifier_types / get_modifier_settings up front."
)


@mcp.tool(annotations=READ_ONLY)
def list_modifier_types(
    filter: Annotated[str | None, Field(description="Case-insensitive substring to narrow the list, e.g. 'bevel', 'grease', 'smooth'. Omit to get all 83 types, which is a large response.")] = None,
) -> list[dict]:
    """List every modifier type Blender offers, each with the properties you can set on it (name, type, enum values, default).

    This is the reference for the `settings` argument of add_modifier and set_modifier —
    consult it instead of guessing attribute names. Pass a `filter`; the unfiltered list
    covers all 83 types and is long.
    """
    return call("list_modifier_types", filter=filter)


@mcp.tool(annotations=READ_ONLY)
def list_modifiers(
    object: Annotated[str, Field(description="Object whose modifier stack to list.")],
) -> list[dict]:
    """List an object's modifier stack in evaluation order, with each modifier's name, type and viewport/render visibility.

    Order matters: modifiers evaluate top to bottom, so a BEVEL before a SUBSURF gives a
    different result than after it. Use get_modifier_settings for one modifier's values,
    move_modifier to reorder.
    """
    return call("list_modifiers", object=object)


@mcp.tool(annotations=READ_ONLY)
def get_modifier_settings(
    object: Annotated[str, Field(description="Object that owns the modifier.")],
    modifier: Annotated[str, Field(description="Modifier name as shown in list_modifiers (the name, not the type).")],
) -> dict:
    """Read one modifier's current values plus the full table of properties it accepts.

    Use it before set_modifier to learn the exact attribute names and valid enum values
    for that specific modifier, rather than guessing and getting an error.
    """
    return call("get_modifier_settings", object=object, modifier=modifier)


@mcp.tool(annotations=CREATE)
def add_modifier(
    object: Annotated[str, Field(description="Object to add the modifier to.")],
    type: Annotated[str, Field(description="Modifier type identifier, e.g. SUBSURF, BEVEL, ARRAY, MIRROR, SOLIDIFY, BOOLEAN, DECIMATE, SHRINKWRAP, WELD, WIREFRAME, REMESH, ARMATURE, NODES. 83 exist — list_modifier_types has them all.")],
    name: Annotated[str | None, Field(description="Name for this modifier instance, used to address it later in set_modifier/remove_modifier. Defaults to Blender's own ('Subdivision', 'Bevel').")] = None,
    settings: Annotated[dict | None, Field(description=_SETTINGS_DOC)] = None,
) -> dict:
    """Add one modifier to the end of an object's stack and configure it in the same call.

    Modifiers are non-destructive: the mesh data is untouched and you can change or remove
    them freely until apply_modifier bakes the result. Adding the same type twice gives
    two modifiers. Use batch_add_modifier for many objects at once. The response echoes
    every setting the modifier has, which is a quick way to see what else is tunable.
    """
    return call("add_modifier", object=object, type=type, name=name, settings=settings)


@mcp.tool(annotations=UPDATE)
def set_modifier(
    object: Annotated[str, Field(description="Object that owns the modifier.")],
    modifier: Annotated[str, Field(description="Modifier name (from list_modifiers).")],
    settings: Annotated[dict, Field(description=_SETTINGS_DOC)],
) -> dict:
    """Change properties on an existing modifier.

    Only the keys you pass are touched. Fails if the modifier has already been applied
    (it no longer exists) — check with list_modifiers.
    """
    return call("set_modifier", object=object, modifier=modifier, settings=settings)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_modifier(
    object: Annotated[str, Field(description="Object that owns the modifier.")],
    modifier: Annotated[str, Field(description="Modifier name to delete.")],
) -> dict:
    """Delete a modifier from the stack, discarding its effect.

    The mesh reverts to how it looked without it. To keep the effect permanently instead,
    use apply_modifier.
    """
    return call("remove_modifier", object=object, modifier=modifier)


@mcp.tool(annotations=DESTRUCTIVE)
def apply_modifier(
    object: Annotated[str, Field(description="Object that owns the modifier. Must be a mesh; applying on an object with shared mesh data affects every user of that mesh.")],
    modifier: Annotated[str, Field(description="Modifier name to bake into the mesh.")],
) -> dict:
    """Permanently bake a modifier's result into the mesh and remove it from the stack.

    Irreversible except via `undo`: a SUBSURF that was one adjustable slider becomes tens
    of thousands of real vertices. Apply only when you are done tweaking, or when an
    exporter needs real geometry. Modifiers below it in the stack still evaluate on the
    new mesh. Note that non-uniform object scale changes how widths behave — run
    apply_transforms first if the result looks wrong.
    """
    return call("apply_modifier", object=object, modifier=modifier)


@mcp.tool(annotations=UPDATE)
def move_modifier(
    object: Annotated[str, Field(description="Object that owns the modifier.")],
    modifier: Annotated[str, Field(description="Modifier name to move.")],
    index: Annotated[int | None, Field(description="Exact 0-based position in the stack, 0 being evaluated first. Give this or `direction`, not both.")] = None,
    direction: Annotated[str | None, Field(description="Relative move: UP, DOWN, TOP or BOTTOM.")] = None,
) -> dict:
    """Reorder a modifier within the stack, which changes the result.

    Evaluation runs top to bottom, so order is not cosmetic: MIRROR before SUBSURF gives a
    clean seam, after it does not; BOOLEAN generally belongs before BEVEL. Use
    list_modifiers to see the current order first.
    """
    return call("move_modifier", object=object, modifier=modifier, index=index, direction=direction)
