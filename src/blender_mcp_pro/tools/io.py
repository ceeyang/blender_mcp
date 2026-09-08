"""Import / Export — moving data in and out of the .blend."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, WRITES_FILE

_FORMATS = ("obj, fbx, gltf, glb, usd, usda, usdc, stl, ply, abc (Alembic) and blend")


@mcp.tool(annotations=CREATE)
def import_file(
    path: Annotated[str, Field(description=f"Absolute path to the file. Supported: {_FORMATS}.")],
    format: Annotated[str | None, Field(description="Force a format instead of inferring it from the extension. Only needed when the extension is wrong or missing.")] = None,
    options: Annotated[dict | None, Field(description="Extra arguments passed straight to Blender's importer for that format, e.g. {'global_scale': 0.01} for fbx or {'forward_axis': 'Y', 'up_axis': 'Z'} for obj. Use get_api_docs('bpy.ops.wm.obj_import') etc. for the exact names.")] = None,
    collection: Annotated[str | None, Field(description="Existing collection to put the imported objects in, which keeps a busy scene organised. Create it first with manage_collection.")] = None,
) -> dict:
    """Import a 3D file into the current scene, returning the names of the objects it created.

    Everything is added to the existing scene — nothing is replaced, so importing twice
    gives you two copies. Use the returned names to address the new objects; they often
    differ from what you would guess, since the file's own naming wins. Axis conventions
    vary by format, so imported models may arrive rotated or at the wrong scale; fix that
    with set_transform and apply_transforms, or with `options`.
    """
    return call("import_file", path=path, format=format, options=options, collection=collection)


@mcp.tool(annotations=WRITES_FILE)
def export_file(
    path: Annotated[str, Field(description=f"Absolute destination path; the extension picks the format. Supported: {_FORMATS}. An existing file is overwritten.")],
    format: Annotated[str | None, Field(description="Force a format instead of inferring it from the extension.")] = None,
    objects: Annotated[list[str] | dict | str | None, Field(description="What to export: a list of names or one filter dict ({pattern}/{collection}/{type}/{selected}). OMIT to export the entire scene.")] = None,
    options: Annotated[dict | None, Field(description="Extra arguments for the exporter, e.g. {'export_materials': false} or {'global_scale': 100}. Check names with get_api_docs('bpy.ops.export_scene.gltf').")] = None,
) -> dict:
    """Export objects (or the whole scene) to an interchange format on disk.

    Modifiers are generally evaluated by the exporter, so what you get is the visible
    result rather than the base mesh. For game engines prefer export_for_game, which also
    applies modifiers, triangulates and handles axis conversion. Omitting `objects`
    exports everything including lights, cameras and the ground plane.
    """
    return call("export_file", path=path, format=format, objects=objects, options=options)


@mcp.tool(annotations=CREATE)
def append_from_blend(
    path: Annotated[str, Field(description="Absolute path to another .blend file. It must be a DIFFERENT file — you cannot append from the file currently open.")],
    datablock: Annotated[str, Field(description="Which category to pull from: 'objects', 'materials', 'collections', 'node_groups', 'actions', 'worlds', 'images', 'meshes'.")],
    name: Annotated[str, Field(description="Exact name of the datablock inside that file.")],
    link: Annotated[bool, Field(description="false (default) APPENDS a full independent copy into this file. true LINKS it, keeping it owned by the source file — the data stays read-only here and updates when the source changes, but breaks if that file moves.")] = False,
) -> dict:
    """Pull a specific object, material or node group out of another .blend file.

    This is how you reuse work across files without re-importing geometry. Appending
    brings dependencies with it (an object's mesh and materials come too). Note the hard
    limit: Blender cannot append from the .blend that is currently open.
    """
    return call("append_from_blend", path=path, datablock=datablock, name=name, link=link)


@mcp.tool(annotations=WRITES_FILE)
def save_blend(
    path: Annotated[str | None, Field(description="Absolute path to save to (save-as). Omit to save over the current file — which fails if the file has never been saved and has no path yet.")] = None,
    compress: Annotated[bool, Field(description="true zips the .blend, typically a large size saving on heavy scenes at the cost of slower save and load.")] = False,
) -> dict:
    """Save the current scene to a .blend file.

    Nothing this server does is written to disk until you call this — all other tools only
    change the in-memory scene, and closing Blender would lose them. Passing a `path` does
    a save-as and makes that the current file for subsequent saves.
    """
    return call("save_blend", path=path, compress=compress)


@mcp.tool(annotations=DESTRUCTIVE)
def open_blend(
    path: Annotated[str, Field(description="Absolute path to the .blend file to open.")],
    load_ui: Annotated[bool, Field(description="false (default) keeps the current window layout, which is usually what you want. true also restores the layout saved in that file.")] = False,
) -> dict:
    """Open a .blend file, DISCARDING everything currently in the scene.

    Unsaved changes in the current file are lost without warning and this is not undoable
    — call save_blend first if the current work matters. To bring in data while keeping
    the current scene, use append_from_blend or import_file instead.
    """
    return call("open_blend", path=path, load_ui=load_ui)
