"""Scene Utilities（13）。"""
from __future__ import annotations

import contextlib
import io
import math
import sys

import bmesh
import bpy
import mathutils
from mathutils import Vector

from ..registry import command
from ..utils import ToolError, abs_path, find_object, resolve_objects, rna_props, select_only, serialize, target_point, vec


@command("execute_code")
def execute_code(code: str, return_var: str | None = None):
    ns = {"bpy": bpy, "bmesh": bmesh, "mathutils": mathutils, "Vector": Vector, "math": math, "__name__": "__mcp__"}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<mcp>", "exec"), ns)
    out = {"stdout": buf.getvalue()}
    if return_var:
        if return_var not in ns:
            raise ToolError(f"variable '{return_var}' was not defined by the code")
        out["result"] = serialize(ns[return_var])
    return out


@command("get_blender_info", mutates=False)
def get_blender_info():
    from .. import ADDON_VERSION
    from ..server import _prefs, status
    p = _prefs()
    return {
        "blender": bpy.app.version_string, "version": list(bpy.app.version),
        "python": sys.version.split()[0], "binary": bpy.app.binary_path,
        "background": bpy.app.background, "file": bpy.data.filepath,
        "addon_version": ADDON_VERSION, "server": status(),
        "extensions_dir": bpy.utils.user_resource("EXTENSIONS"),
        "enabled_addons": sorted(a.module for a in bpy.context.preferences.addons),
        "sketchfab_token_configured": bool(p and p.sketchfab_token),
        "render_engine": bpy.context.scene.render.engine,
    }


def _struct_props(struct) -> dict:
    out = {}
    for p in struct.properties:
        if p.identifier == "rna_type":
            continue
        d = {"type": p.type, "description": p.description, "readonly": p.is_readonly}
        if p.type == "ENUM":
            d["enum"] = [e.identifier for e in p.enum_items]
        elif p.type == "POINTER":
            d["pointer_type"] = p.fixed_type.identifier
        elif p.type in ("INT", "FLOAT", "BOOLEAN") and getattr(p, "array_length", 0) > 1:
            d["array_length"] = p.array_length
        elif p.type in ("INT", "FLOAT", "BOOLEAN", "STRING"):
            d["default"] = serialize(getattr(p, "default", None))
        out[p.identifier] = d
    return out


def _similar(name: str, pool) -> list[str]:
    n = name.lower()
    return sorted(x for x in pool if n in x.lower() or x.lower() in n)[:20]


@command("get_api_docs", mutates=False)
def get_api_docs(path: str):
    parts = path.strip().split(".")
    if parts[:2] == ["bpy", "ops"]:
        if len(parts) != 4:
            raise ToolError("operator path must be bpy.ops.<module>.<operator>")
        mod = getattr(bpy.ops, parts[2], None)
        if mod is None:
            raise ToolError(f"unknown operator module '{parts[2]}'")
        try:
            op = getattr(mod, parts[3])
            rna = op.get_rna_type()
        except (AttributeError, KeyError):
            raise ToolError(f"operator '{path}' not found. Similar: {', '.join(_similar(parts[3], dir(mod)))}")
        return {"path": path, "kind": "operator", "name": rna.name, "description": rna.description,
                "properties": _struct_props(rna)}
    if parts[:2] == ["bpy", "types"] and len(parts) in (3, 4):
        t = getattr(bpy.types, parts[2], None)
        if t is None:
            raise ToolError(f"type '{parts[2]}' not found. Similar: {', '.join(_similar(parts[2], dir(bpy.types)))}")
        rna = t.bl_rna
        if len(parts) == 3:
            return {"path": path, "kind": "type", "name": rna.name, "description": rna.description,
                    "base": rna.base.identifier if rna.base else None,
                    "properties": _struct_props(rna),
                    "functions": [f.identifier for f in rna.functions]}
        member = parts[3]
        p = rna.properties.get(member)
        if p is not None:
            d = {"path": path, "kind": "property", "name": p.name, "type": p.type, "description": p.description,
                 "readonly": p.is_readonly}
            if p.type == "ENUM":
                d["enum"] = [{"id": e.identifier, "name": e.name, "description": e.description} for e in p.enum_items]
            elif p.type == "POINTER":
                d["pointer_type"] = p.fixed_type.identifier
            elif p.type in ("INT", "FLOAT"):
                d["min"], d["max"] = serialize(p.hard_min), serialize(p.hard_max)
                if getattr(p, "array_length", 0) > 1:
                    d["array_length"] = p.array_length
                    d["default"] = serialize(list(p.default_array))
                else:
                    d["default"] = serialize(p.default)
            elif p.type in ("BOOLEAN", "STRING"):
                d["default"] = serialize(p.default)
            return d
        f = rna.functions.get(member)
        if f is not None:
            return {"path": path, "kind": "function", "description": f.description,
                    "parameters": {q.identifier: {"type": q.type, "description": q.description,
                                                  "is_output": q.is_output, "required": q.is_required}
                                   for q in f.parameters}}
        raise ToolError(f"'{member}' not found on {parts[2]}. Similar: "
                        f"{', '.join(_similar(member, [q.identifier for q in rna.properties] + [q.identifier for q in rna.functions]))}")
    raise ToolError("path must be like bpy.types.Object, bpy.types.Object.location or bpy.ops.mesh.primitive_cube_add")


def _undo_op(op, what):
    if bpy.app.background:
        raise ToolError(f"{what} 在无头（-b）模式下不可用：background 模式没有 undo 栈")
    try:
        op()
    except RuntimeError as e:
        raise ToolError(f"{what} failed: {e}") from e
    return {"objects": [o.name for o in bpy.data.objects]}


@command("undo", mutates=False)
def undo():
    return _undo_op(bpy.ops.ed.undo, "undo")


@command("redo", mutates=False)
def redo():
    return _undo_op(bpy.ops.ed.redo, "redo")


@command("purge_orphans")
def purge_orphans():
    n = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    return {"purged": n}


@command("set_units")
def set_units(system: str | None = None, scale_length: float | None = None, length_unit: str | None = None,
              rotation_unit: str | None = None):
    us = bpy.context.scene.unit_settings
    if system is not None:
        us.system = system.upper()
    if scale_length is not None:
        us.scale_length = scale_length
    if length_unit is not None:
        us.length_unit = length_unit.upper()
    if rotation_unit is not None:
        us.system_rotation = rotation_unit.upper()
    return {"system": us.system, "scale_length": us.scale_length, "length_unit": us.length_unit,
            "rotation": us.system_rotation}


@command("set_cursor")
def set_cursor(location=None, rotation=None):
    cur = bpy.context.scene.cursor
    if location is not None:
        cur.location = location
    if rotation is not None:
        cur.rotation_euler = rotation
    return {"location": vec(cur.location), "rotation": vec(cur.rotation_euler)}


@command("measure_distance", mutates=False)
def measure_distance(a, b):
    pa, pb = target_point(a), target_point(b)
    return {"distance": round((pa - pb).length, 6), "a": vec(pa), "b": vec(pb), "delta": vec(pb - pa)}


@command("get_bounding_box", mutates=False)
def get_bounding_box(objects, world: bool = True):
    objs = resolve_objects(objects)
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append((o.matrix_world @ Vector(c)) if world else Vector(c))
    if not pts:
        raise ToolError("no geometry")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return {"min": vec(mn), "max": vec(mx), "center": vec((mn + mx) / 2), "size": vec(mx - mn),
            "objects": [o.name for o in objs]}


@command("ray_cast", mutates=False)
def ray_cast(origin, direction, distance: float = 1000.0):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, normal, index, obj, _ = bpy.context.scene.ray_cast(dg, Vector(origin), Vector(direction).normalized(),
                                                                 distance=distance)
    if not hit:
        return {"hit": False}
    return {"hit": True, "object": obj.name, "location": vec(loc), "normal": vec(normal), "face_index": index,
            "distance": round((loc - Vector(origin)).length, 6)}


@command("check_mesh", mutates=False)
def check_mesh(name: str):
    o = find_object(name, "MESH")
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        non_manifold = [e.index for e in bm.edges if not e.is_manifold]
        loose_verts = [v.index for v in bm.verts if not v.link_edges]
        loose_edges = [e.index for e in bm.edges if not e.link_faces]
        ngons = [f.index for f in bm.faces if len(f.verts) > 4]
        tris = sum(1 for f in bm.faces if len(f.verts) == 3)
        quads = sum(1 for f in bm.faces if len(f.verts) == 4)
        doubles = bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-4)["targetmap"]
        tri_count = sum(len(f.verts) - 2 for f in bm.faces)
    finally:
        bm.free()
    return {"object": o.name, "vertices": len(me.vertices), "edges": len(me.edges), "faces": len(me.polygons),
            "triangles_when_triangulated": tri_count, "tris": tris, "quads": quads, "ngons": len(ngons),
            "non_manifold_edges": len(non_manifold), "loose_vertices": len(loose_verts), "loose_edges": len(loose_edges),
            "duplicate_vertices": len(doubles), "is_manifold": not non_manifold,
            "samples": {"non_manifold_edges": non_manifold[:20], "ngons": ngons[:20], "loose_vertices": loose_verts[:20]}}


@command("mesh_cleanup")
def mesh_cleanup(name: str, recalc_normals: bool = False, inside: bool = False, merge_by_distance: bool = False,
                 threshold: float = 0.0001, shade_smooth: bool | None = None, auto_smooth_angle: float | None = None,
                 dissolve_degenerate: bool = False):
    o = find_object(name, "MESH")
    me = o.data
    before = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        if merge_by_distance:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=threshold)
        if dissolve_degenerate:
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=threshold)
        if recalc_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            if inside:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    if shade_smooth is not None:
        for p in me.polygons:
            p.use_smooth = shade_smooth
    if auto_smooth_angle is not None:
        select_only([o], o)
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=auto_smooth_angle)
        except (AttributeError, RuntimeError):
            bpy.ops.object.shade_auto_smooth(angle=auto_smooth_angle)
    return {"object": o.name, "vertices_before": before, "vertices_after": len(me.vertices),
            "faces": len(me.polygons), "smooth": all(p.use_smooth for p in me.polygons) if me.polygons else None}
