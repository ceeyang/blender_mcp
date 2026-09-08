"""Batch Processing — act on many objects in one call."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, UPDATE, Objects


@mcp.tool(annotations=UPDATE)
def batch_transform(
    objects: Objects,
    location: Annotated[list[float] | None, Field(description="[x, y, z] in meters. Added to each object's current location when relative=true (the default), otherwise assigned to all of them.")] = None,
    rotation: Annotated[list[float] | None, Field(description="Euler XYZ in RADIANS. Added to the current rotation when relative=true, otherwise assigned.")] = None,
    scale: Annotated[list[float] | None, Field(description="Scale factors [x, y, z]. MULTIPLIED into the current scale when relative=true, otherwise assigned.")] = None,
    relative: Annotated[bool, Field(description="true (default) = offset each object from where it already is; false = assign the same absolute values to every object, stacking them on top of each other. NOTE: set_transform defaults to false, this tool defaults to true.")] = True,
) -> dict:
    """Move, rotate and scale many objects in one call, relative to where each already is.

    Use for more than one object; use set_transform for a single named object (and mind
    the opposite `relative` default), or randomize_transform to scatter them by random
    amounts instead of a uniform offset. Edits objects in place — nothing is created or
    deleted, and `undo` reverts the whole call.
    """
    return call("batch_transform", objects=objects, location=location, rotation=rotation, scale=scale, relative=relative)


@mcp.tool(annotations=UPDATE)
def batch_rename(
    objects: Objects,
    prefix: Annotated[str | None, Field(description="String prepended to each name, e.g. 'Prop_' turns 'Chair' into 'Prop_Chair'.")] = None,
    suffix: Annotated[str | None, Field(description="String appended to each name, applied before numbering.")] = None,
    find: Annotated[str | None, Field(description="Substring to search for; requires `replace`. Plain text, not a regex.")] = None,
    replace: Annotated[str | None, Field(description="Replacement for every occurrence of `find`. Use an empty string to delete it.")] = None,
    numbering: Annotated[bool, Field(description="Append a zero-padded counter (_001, _002, ...) in the order objects were resolved. Use it to make names unique after a prefix/suffix collapses them.")] = False,
) -> dict:
    """Rename many objects at once by prefix, suffix, find/replace and/or numbering.

    All requested operations apply in that order in a single pass. Use rename_object for
    one object or to also rename its mesh datablock. Blender auto-appends .001 on name
    collisions, so pass numbering=true when a rename would produce duplicates.
    """
    return call("batch_rename", objects=objects, prefix=prefix, suffix=suffix, find=find, replace=replace, numbering=numbering)


@mcp.tool(annotations=UPDATE)
def batch_apply_material(
    objects: Objects,
    material: Annotated[str, Field(description="Name of an existing material (create it first with create_material). Must already exist.")],
) -> dict:
    """Put one existing material into slot 0 of many objects, replacing what was there.

    Use assign_material for a single object or to target a slot other than the first.
    Objects that cannot hold materials (cameras, lights, empties) are reported under
    "skipped" rather than failing the call. The material is shared, not copied — editing
    it afterwards changes every object at once.
    """
    return call("batch_apply_material", objects=objects, material=material)


@mcp.tool(annotations=CREATE)
def batch_add_modifier(
    objects: Objects,
    type: Annotated[str, Field(description="Modifier type, e.g. SUBSURF, BEVEL, ARRAY, MIRROR, SOLIDIFY, BOOLEAN, DECIMATE, WELD. Call list_modifier_types for all 83 names and their settable properties.")],
    settings: Annotated[dict | None, Field(description="Modifier properties by bpy attribute name, e.g. {'levels': 2} for SUBSURF or {'width': 0.02, 'segments': 3} for BEVEL. Object-valued properties take an object name. Unknown keys fail with the list of valid ones.")] = None,
) -> dict:
    """Add the same modifier, with the same settings, to many objects at once.

    Appends to the end of each object's stack; it does not replace an existing modifier
    of the same type, so calling twice leaves two. Use add_modifier for a single object
    or to control the modifier's name. Modifiers are non-destructive until apply_modifier.
    """
    return call("batch_add_modifier", objects=objects, type=type, settings=settings)


@mcp.tool(annotations=UPDATE)
def batch_set_property(
    objects: Objects,
    data_path: Annotated[str, Field(description="Property path relative to each object, e.g. 'hide_render', 'show_wire', 'data.materials', or an indexed path like \"modifiers[\\\"Bevel\\\"].width\". Use DOUBLE quotes inside brackets — single quotes are not accepted.")],
    value: Annotated[float | int | bool | str | list | None, Field(description="Value to assign. Must match the property's type; vectors take a list, enums take the identifier string.")],
) -> dict:
    """Set any bpy property, by path, on many objects — the escape hatch for what other tools don't cover.

    Prefer a purpose-built tool when one exists (set_visibility, batch_transform,
    set_modifier): they validate input and report better errors. Reach for this only for
    properties none of them expose. An invalid path or a type mismatch fails the call.
    """
    return call("batch_set_property", objects=objects, data_path=data_path, value=value)


@mcp.tool(annotations=DESTRUCTIVE)
def batch_delete(objects: Objects) -> dict:
    """Permanently delete many objects from the scene, returning the names removed.

    Children of a deleted object are NOT deleted — they are unparented and stay; use
    delete_object with delete_children=true for a whole hierarchy. Meshes and materials
    left with no users remain in the file until purge_orphans. Reversible via `undo`.
    """
    return call("batch_delete", objects=objects)


@mcp.tool(annotations=UPDATE)
def distribute_objects(
    objects: Objects,
    mode: Annotated[str, Field(description="LINE = evenly spaced along one axis; GRID = rows and columns on the two axes after `axis`; CIRCLE = evenly spaced on a circle whose normal is `axis`.")] = "LINE",
    spacing: Annotated[float, Field(description="Distance in meters between neighbours. Used by LINE and GRID; ignored by CIRCLE, which derives spacing from radius and count.")] = 2.0,
    axis: Annotated[str | None, Field(description="X, Y or Z. Defaults to X for LINE/GRID (rows then run along the next axis) and to Z for CIRCLE (the circle's normal, so objects land in the XY plane).")] = None,
    columns: Annotated[int, Field(description="Objects per row in GRID mode. Ignored by LINE and CIRCLE.")] = 5,
    radius: Annotated[float, Field(description="Circle radius in meters. CIRCLE mode only.")] = 5.0,
    center: Annotated[list[float] | None, Field(description="[x, y, z] origin of the arrangement in meters. Defaults to the world origin, NOT to the objects' current centroid.")] = None,
) -> dict:
    """Arrange objects into a line, grid or circle at exact positions, overwriting their locations.

    This assigns deterministic positions — for organic scatter over a surface use
    scatter_objects, and for random jitter around current positions use
    randomize_transform. Rotation and scale are left untouched.
    """
    return call("distribute_objects", objects=objects, mode=mode, spacing=spacing, axis=axis, columns=columns,
                radius=radius, center=center)


@mcp.tool(annotations=UPDATE)
def randomize_transform(
    objects: Objects,
    location: Annotated[list[float] | None, Field(description="Max offset per axis in meters, applied as current_location ± random(0, value). [0.5, 0.5, 0] jitters in XY only.")] = None,
    rotation: Annotated[list[float] | None, Field(description="Max rotation per axis in RADIANS, applied as current_rotation ± random. Use 3.1416 for 'any angle' on an axis.")] = None,
    scale: Annotated[list[float] | None, Field(description="Variation around 1.0, NOT around 0: a value of 0.4 produces scales in 0.6-1.4. Keep below 1.0 or objects can invert.")] = None,
    uniform_scale: Annotated[bool, Field(description="true (default) draws ONE factor and applies it to all three axes, keeping proportions. false stretches each axis independently.")] = True,
    seed: Annotated[int, Field(description="Seed for the random generator. The same seed with the same objects and ranges reproduces the same result exactly.")] = 0,
) -> dict:
    """Jitter position, rotation and scale of many objects by random amounts around their current values.

    Each parameter is a ± range, not a target: scale is variation around 1.0, so 0.4 means
    0.6-1.4. Use it to break up copies that look too regular. For exact placement use
    distribute_objects, for a uniform offset use batch_transform.
    """
    return call("randomize_transform", objects=objects, location=location, rotation=rotation, scale=scale,
                uniform_scale=uniform_scale, seed=seed)
