"""Import/Export（5）。"""
from __future__ import annotations

import os

import bpy

from ..registry import command
from ..utils import ToolError, abs_path, find_collection, link_to_scene, resolve_objects, select_only

_IMPORT = {
    "obj": lambda p, o: bpy.ops.wm.obj_import(filepath=p, **o),
    "fbx": lambda p, o: bpy.ops.import_scene.fbx(filepath=p, **o),
    "gltf": lambda p, o: bpy.ops.import_scene.gltf(filepath=p, **o),
    "glb": lambda p, o: bpy.ops.import_scene.gltf(filepath=p, **o),
    "usd": lambda p, o: bpy.ops.wm.usd_import(filepath=p, **o),
    "usda": lambda p, o: bpy.ops.wm.usd_import(filepath=p, **o),
    "usdc": lambda p, o: bpy.ops.wm.usd_import(filepath=p, **o),
    "usdz": lambda p, o: bpy.ops.wm.usd_import(filepath=p, **o),
    "stl": lambda p, o: bpy.ops.wm.stl_import(filepath=p, **o),
    "ply": lambda p, o: bpy.ops.wm.ply_import(filepath=p, **o),
    "abc": lambda p, o: bpy.ops.wm.alembic_import(filepath=p, **o),
}
_EXPORT = {
    "obj": lambda p, sel, o: bpy.ops.wm.obj_export(filepath=p, export_selected_objects=sel, **o),
    "fbx": lambda p, sel, o: bpy.ops.export_scene.fbx(filepath=p, use_selection=sel, **o),
    "gltf": lambda p, sel, o: bpy.ops.export_scene.gltf(filepath=p, export_format="GLTF_SEPARATE", use_selection=sel, **o),
    "glb": lambda p, sel, o: bpy.ops.export_scene.gltf(filepath=p, export_format="GLB", use_selection=sel, **o),
    "usd": lambda p, sel, o: bpy.ops.wm.usd_export(filepath=p, selected_objects_only=sel, **o),
    "usda": lambda p, sel, o: bpy.ops.wm.usd_export(filepath=p, selected_objects_only=sel, **o),
    "usdc": lambda p, sel, o: bpy.ops.wm.usd_export(filepath=p, selected_objects_only=sel, **o),
    "stl": lambda p, sel, o: bpy.ops.wm.stl_export(filepath=p, export_selected_objects=sel, **o),
    "ply": lambda p, sel, o: bpy.ops.wm.ply_export(filepath=p, export_selected_objects=sel, **o),
    "abc": lambda p, sel, o: bpy.ops.wm.alembic_export(filepath=p, selected=sel, **o),
}


def _fmt(path: str, fmt: str | None, table: dict) -> str:
    f = (fmt or os.path.splitext(path)[1].lstrip(".")).lower()
    if f == "blend":
        return f
    if f not in table:
        raise ToolError(f"unsupported format '{f}'. Supported: {', '.join(sorted(table))}, blend")
    return f


def _object_mode():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


@command("import_file")
def import_file(path: str, format: str | None = None, options: dict | None = None, collection: str | None = None):
    p = abs_path(path)
    if not os.path.exists(p):
        raise ToolError(f"file not found: {p}")
    f = _fmt(p, format, _IMPORT)
    before = set(bpy.data.objects.keys())
    _object_mode()
    if f == "blend":
        with bpy.data.libraries.load(p, link=False) as (src, dst):
            dst.objects = list(src.objects)
        for o in dst.objects:
            if o is not None:
                link_to_scene(o)
    else:
        try:
            _IMPORT[f](p, options or {})
        except (RuntimeError, TypeError) as e:
            raise ToolError(f"import failed ({f}): {e}") from e
    new = [n for n in bpy.data.objects.keys() if n not in before]
    if collection:
        target = find_collection(collection)
        for n in new:
            o = bpy.data.objects[n]
            for c in list(o.users_collection):
                c.objects.unlink(o)
            target.objects.link(o)
    return {"path": p, "format": f, "objects": new, "count": len(new)}


@command("export_file")
def export_file(path: str, format: str | None = None, objects=None, options: dict | None = None):
    p = abs_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    f = _fmt(p, format, _EXPORT)
    _object_mode()
    names = None
    sel = objects is not None
    if sel:
        objs = resolve_objects(objects)
        names = [o.name for o in objs]
        select_only(objs, objs[0])
    if f == "blend":
        if sel:
            bpy.data.libraries.write(p, set(objs), fake_user=True)
        else:
            bpy.ops.wm.save_as_mainfile(filepath=p, copy=True)
    else:
        try:
            _EXPORT[f](p, sel, options or {})
        except (RuntimeError, TypeError) as e:
            raise ToolError(f"export failed ({f}): {e}") from e
    if not os.path.exists(p):
        raise ToolError(f"export finished but no file at {p}")
    return {"path": p, "format": f, "size_bytes": os.path.getsize(p), "objects": names or "all"}


@command("append_from_blend")
def append_from_blend(path: str, datablock: str, name: str, link: bool = False):
    p = abs_path(path)
    if not os.path.exists(p):
        raise ToolError(f"file not found: {p}")
    if bpy.data.filepath and os.path.abspath(bpy.data.filepath) == p:
        raise ToolError("cannot append from the currently open .blend file; save a copy first or duplicate_object instead")
    with bpy.data.libraries.load(p, link=link) as (src, dst):
        if not hasattr(src, datablock):
            raise ToolError(f"unknown datablock '{datablock}'. Use objects/materials/meshes/collections/node_groups/actions/images/worlds…")
        available = list(getattr(src, datablock))
        if name not in available:
            raise ToolError(f"'{name}' not in {datablock} of {os.path.basename(p)}. Available: {', '.join(available[:20])}")
        setattr(dst, datablock, [name])
    got = getattr(dst, datablock)[0]
    if got is None:
        raise ToolError(f"failed to load {datablock} '{name}'")
    if datablock == "objects":
        link_to_scene(got)
    elif datablock == "collections":
        bpy.context.scene.collection.children.link(got)
    return {"name": got.name, "datablock": datablock, "linked": link, "path": p}


@command("save_blend")
def save_blend(path: str | None = None, compress: bool = False):
    _object_mode()
    if path:
        p = abs_path(path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=compress)
    else:
        if not bpy.data.filepath:
            raise ToolError("file has never been saved; give a path")
        bpy.ops.wm.save_mainfile(compress=compress)
    return {"path": bpy.data.filepath, "size_bytes": os.path.getsize(bpy.data.filepath)}


@command("open_blend")
def open_blend(path: str, load_ui: bool = False):
    p = abs_path(path)
    if not os.path.exists(p):
        raise ToolError(f"file not found: {p}")
    _object_mode()
    bpy.ops.wm.open_mainfile(filepath=p, load_ui=load_ui)
    return {"path": bpy.data.filepath, "objects": [o.name for o in bpy.data.objects], "scene": bpy.context.scene.name}
