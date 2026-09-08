"""Scene & Objects — inspect the scene, create primitives, transform and organise objects."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE, Location, Objects, Rotation


@mcp.tool(annotations=READ_ONLY)
def get_scene_info() -> dict:
    """Survey the whole scene: name, frame range, fps, units, render engine, active object and camera, object counts by type, and the collection tree.

    Call this first when you don't know what is in the file — it is the cheapest way to
    learn which object names exist before any other tool. Use list_objects to filter that
    set, or get_object_info for one object's full detail.
    """
    return call("get_scene_info")


@mcp.tool(annotations=READ_ONLY)
def list_objects(
    type: Annotated[str | None, Field(description="Keep only this object type: MESH, LIGHT, CAMERA, EMPTY, ARMATURE, CURVE, FONT, SURFACE, META, VOLUME, GPENCIL.")] = None,
    collection: Annotated[str | None, Field(description="Keep only objects inside this collection, including its nested collections.")] = None,
    pattern: Annotated[str | None, Field(description="Glob on the object name, case-sensitive: 'Rock_*', '*_L', 'Wheel_?'.")] = None,
    selected: Annotated[bool, Field(description="true keeps only currently selected objects. Selection is scene state, so it reflects whatever the user or a previous tool last selected.")] = False,
) -> list[dict]:
    """List objects with their transform, dimensions, collections and visibility, sorted by name.

    Filters combine with AND. Returns a compact summary per object — call get_object_info
    for modifiers, constraints, materials and mesh statistics of a single one.
    """
    return call("list_objects", type=type, collection=collection, pattern=pattern, selected=selected or None)


@mcp.tool(annotations=READ_ONLY)
def get_object_info(
    name: Annotated[str, Field(description="Exact object name. If it doesn't exist, the error lists the closest existing names.")],
) -> dict:
    """Get everything about one object: local and world transform, parent and children, collections, modifier and constraint stacks, material slots, custom properties, and type-specific data (mesh counts and UV maps, camera lens, light energy, bone count).

    Use after list_objects narrowed things down. `location` is local to the parent while
    `world_location` is absolute — they differ once the object is parented.
    """
    return call("get_object_info", name=name)


@mcp.tool(annotations=CREATE)
def create_primitive(
    type: Annotated[str, Field(description="cube, plane, circle, uv_sphere, ico_sphere, cylinder, cone, torus, monkey, empty, or text.")],
    name: Annotated[str | None, Field(description="Name for the new object and its data. Blender appends .001 if the name is taken. Defaults to Blender's own ('Cube', 'Sphere', ...).")] = None,
    location: Location = None,
    rotation: Rotation = None,
    scale: Annotated[list[float] | None, Field(description="Non-uniform size [x, y, z] BAKED INTO THE MESH at creation, not stored as object scale — the object comes back with scale [1,1,1] and dimensions reflecting this. Combine with `size`: a cube with size=2 and scale=[1,3,0.5] measures 2x6x1.")] = None,
    size: Annotated[float | None, Field(description="Edge length for cube/plane/monkey (default 2.0, so a cube is 2m across). Ignored by round primitives, which use `radius`.")] = None,
    radius: Annotated[float | None, Field(description="Radius for sphere/cylinder/cone/circle, or the major (ring) radius for torus. Ignored by cube/plane/monkey.")] = None,
    depth: Annotated[float | None, Field(description="Height along Z for cylinder and cone. For torus this is reinterpreted as the minor (tube) radius.")] = None,
    segments: Annotated[int | None, Field(description="Radial resolution: segments for uv_sphere, vertices for cylinder/cone/circle, subdivisions for ico_sphere (2 gives a nice low-poly rock, 1 an octahedron), major segments for torus. Lower means blockier and cheaper.")] = None,
    text: Annotated[str | None, Field(description="The string to display. Only meaningful when type='text'.")] = None,
    collection: Annotated[str | None, Field(description="Existing collection to place the object in instead of the scene's active one. Create it first with manage_collection.")] = None,
) -> dict:
    """Add one mesh primitive, empty or text object to the scene.

    `size`/`radius`/`depth`/`segments` are passed to the primitive's own constructor, so
    which of them apply depends on `type`. Note that `scale` here is baked into the mesh —
    use set_transform afterwards if you want a live object-level scale instead.
    """
    return call("create_primitive", type=type, name=name, location=location, rotation=rotation, scale=scale, size=size,
                radius=radius, depth=depth, segments=segments, text=text, collection=collection)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_object(
    objects: Objects,
    delete_children: Annotated[bool, Field(description="true also deletes the entire descendant hierarchy. false (default) keeps children, which become unparented and stay where they are.")] = False,
) -> dict:
    """Permanently delete objects from the file, returning the names removed.

    Meshes and materials that lose their last user stay in the file as orphans until
    purge_orphans. Reversible with `undo`. Use batch_delete when you just want many
    objects gone and don't need the hierarchy option.
    """
    return call("delete_object", objects=objects, delete_children=delete_children)


@mcp.tool(annotations=CREATE)
def duplicate_object(
    name: Annotated[str, Field(description="Object to copy.")],
    new_name: Annotated[str | None, Field(description="Name for the copy. Defaults to Blender's numbering ('Cube.001').")] = None,
    linked: Annotated[bool, Field(description="true shares the mesh datablock with the original, so later edits to either mesh affect both (cheap, good for repeated props). false (default) makes an independent copy.")] = False,
    offset: Annotated[list[float] | None, Field(description="[x, y, z] in meters ADDED to the original's location. Omit to place the copy exactly on top of the original.")] = None,
) -> dict:
    """Copy one object, keeping its modifiers, materials and transform.

    Children are not copied. For many copies in a regular pattern an ARRAY modifier
    (add_modifier) is far cheaper than calling this repeatedly.
    """
    return call("duplicate_object", name=name, new_name=new_name, linked=linked, offset=offset)


@mcp.tool(annotations=UPDATE)
def set_transform(
    name: Annotated[str, Field(description="Object to transform.")],
    location: Annotated[list[float] | None, Field(description="[x, y, z] in meters, local to the parent. Assigned outright unless relative=true, in which case it is added.")] = None,
    rotation: Annotated[list[float] | None, Field(description="Euler XYZ in RADIANS (90 deg = 1.5708). Assigned outright unless relative=true, in which case it is added.")] = None,
    scale: Annotated[list[float] | None, Field(description="Scale factors [x, y, z]; 1.0 is unchanged. Assigned outright unless relative=true, in which case it MULTIPLIES the current scale.")] = None,
    relative: Annotated[bool, Field(description="false (default) assigns absolute values; true offsets from the current transform (scale multiplies). NOTE: batch_transform defaults to true — the opposite of this tool.")] = False,
) -> dict:
    """Set one object's location, rotation and/or scale, absolutely by default.

    Omitted channels are left alone. Values are local to the parent, so a parented object's
    `location` is an offset from its parent, not a world position — the returned
    `world_location` from get_object_info shows the absolute result. Use batch_transform
    for many objects, apply_transforms to bake the result into the mesh.
    """
    return call("set_transform", name=name, location=location, rotation=rotation, scale=scale, relative=relative)


@mcp.tool(annotations=UPDATE)
def rename_object(
    name: Annotated[str, Field(description="Current object name.")],
    new_name: Annotated[str, Field(description="New name. Blender appends .001 if it is already taken.")],
    rename_data: Annotated[bool, Field(description="true (default) also renames the underlying mesh/curve/light datablock to match, which keeps the outliner readable. Set false to leave shared data alone.")] = True,
) -> dict:
    """Rename one object, by default renaming its data datablock to match.

    Use batch_rename for prefix/suffix/find-replace across many objects.
    """
    return call("rename_object", name=name, new_name=new_name, rename_data=rename_data)


@mcp.tool(annotations=UPDATE)
def set_parent(
    child: Annotated[str, Field(description="Object that will be parented.")],
    parent: Annotated[str | None, Field(description="Object to parent it to. Omit or pass null to CLEAR the parent instead. Parenting to itself or one of its own descendants fails.")] = None,
    keep_transform: Annotated[bool, Field(description="true (default) compensates so the child does not visually move. false lets the child snap into the parent's local space, which usually jumps it.")] = True,
) -> dict:
    """Parent one object to another, or clear its parent, without moving it on screen.

    The child then inherits the parent's transform: moving the parent moves the child, and
    the child's own `location` becomes an offset relative to the parent. A common pattern
    is to parent a whole assembly to one `empty` so it can be moved as a unit.
    """
    return call("set_parent", child=child, parent=parent, keep_transform=keep_transform)


@mcp.tool(annotations=UPDATE)
def set_visibility(
    objects: Objects,
    hide_viewport: Annotated[bool | None, Field(description="true hides the object in the 3D viewport (it still renders unless hide_render is also set).")] = None,
    hide_render: Annotated[bool | None, Field(description="true excludes the object from renders while leaving it visible while working.")] = None,
    hide_select: Annotated[bool | None, Field(description="true makes the object unselectable by clicking, useful for locking down background geometry.")] = None,
) -> dict:
    """Hide or show objects in the viewport, in renders, and for selection — independently.

    Omitted flags are left unchanged. Hiding is not deleting: hidden objects keep their
    data and still appear in list_objects.
    """
    return call("set_visibility", objects=objects, hide_viewport=hide_viewport, hide_render=hide_render,
                hide_select=hide_select)


@mcp.tool(annotations=UPDATE)
def select_objects(
    objects: Objects,
    mode: Annotated[str, Field(description="'replace' (default) deselects everything else first; 'add' extends the current selection; 'remove' deselects just these.")] = "replace",
    active: Annotated[str | None, Field(description="Object to make the ACTIVE one — the single object operators act on. Defaults to the first resolved object.")] = None,
) -> dict:
    """Change which objects are selected and which one is active.

    Most tools here take object names directly and ignore selection, so you rarely need
    this — it matters for the user's own next click in the UI, and for the
    {"selected": true} filter that other tools accept.
    """
    return call("select_objects", objects=objects, mode=mode, active=active)


@mcp.tool(annotations=UPDATE)
def manage_collection(
    action: Annotated[str, Field(description="create (new collection, optionally under `parent`), delete (removes the collection, its objects fall back to the scene collection), move (unlink objects from all other collections, then link here), link (add objects while leaving existing links), unlink (remove objects from this collection), rename.")],
    name: Annotated[str, Field(description="Collection to act on, or the name to give a new one.")],
    parent: Annotated[str | None, Field(description="Parent collection for action='create'. Defaults to the scene's root collection.")] = None,
    objects: Annotated[list[str] | dict | str | None, Field(description="Objects for create/move/link/unlink: a list of names or one filter dict ({pattern}/{collection}/{type}/{selected}).")] = None,
    new_name: Annotated[str | None, Field(description="Required for action='rename'.")] = None,
) -> dict:
    """Create, delete, rename collections and move objects between them.

    Collections are Blender's grouping mechanism; other tools accept
    {"collection": "Name"} as an object filter, so grouping first makes later batch calls
    much shorter. Note 'move' is exclusive (unlinks from everywhere else) while 'link' is
    additive — an object can legitimately live in several collections.
    """
    return call("manage_collection", action=action, name=name, parent=parent, objects=objects, new_name=new_name)


@mcp.tool(annotations=DESTRUCTIVE)
def join_objects(
    objects: Objects,
    target: Annotated[str | None, Field(description="The object that survives and absorbs the others; it keeps its name, origin and transform. Defaults to the first resolved object. Must be one of `objects` or it is added.")] = None,
) -> dict:
    """Merge several mesh objects into one, destroying all of them except the target.

    MESH only — joining a camera or light fails. Material slots are merged and per-face
    assignments preserved, but the separate objects are gone, so this is irreversible
    except via `undo`. To keep objects distinct while moving them together, use set_parent.
    """
    return call("join_objects", objects=objects, target=target)


@mcp.tool(annotations=DESTRUCTIVE)
def apply_transforms(
    objects: Objects,
    location: Annotated[bool, Field(description="Bake location into the mesh, moving the object origin to the world origin.")] = True,
    rotation: Annotated[bool, Field(description="Bake rotation, resetting the object's rotation to zero.")] = True,
    scale: Annotated[bool, Field(description="Bake scale, resetting it to 1.0. This is the one that matters for modifiers and physics, which misbehave on non-uniform scale.")] = True,
) -> dict:
    """Bake an object's transform into its mesh data, resetting the transform to identity (Blender's Ctrl+A).

    The object looks identical but its vertices have moved, so this changes shared mesh
    data and cannot be undone by simply setting the transform back. Apply scale before
    adding modifiers like BEVEL or SOLIDIFY, whose widths are in local space.
    """
    return call("apply_transforms", objects=objects, location=location, rotation=rotation, scale=scale)


@mcp.tool(annotations=UPDATE)
def set_origin(
    name: Annotated[str, Field(description="Object whose origin to move.")],
    type: Annotated[str, Field(description="GEOMETRY = median of the geometry; BOUNDS = centre of the bounding box; CURSOR = the 3D cursor (set it with set_cursor); CENTER_OF_MASS / CENTER_OF_VOLUME = mass-based; GEOMETRY_TO_ORIGIN moves the GEOMETRY to the origin instead of the origin to the geometry.")] = "GEOMETRY",
) -> dict:
    """Move an object's origin point without moving the object on screen.

    The origin is the pivot for rotation and scaling, so this is how you make a door swing
    on its hinge or a tree scale up from its base (set_cursor to the base, then
    type='CURSOR'). It does not change where the object appears.
    """
    return call("set_origin", name=name, type=type)


@mcp.tool(annotations=UPDATE)
def set_custom_property(
    name: Annotated[str, Field(description="Object to annotate.")],
    key: Annotated[str, Field(description="Property name. These are arbitrary user keys stored on the object, visible in the UI under Object Properties > Custom Properties.")],
    value: Annotated[float | int | str | bool | list | None, Field(description="Value to store (number, string, bool or list). Pass null or omit to DELETE the property.")] = None,
) -> dict:
    """Attach, change or delete an arbitrary key/value on an object.

    Useful for tagging objects with your own metadata (asset id, LOD level, export group)
    that survives in the .blend and can be read back from get_object_info. Omitting
    `value` deletes the key rather than setting it to nothing.
    """
    return call("set_custom_property", name=name, key=key, value=value)
