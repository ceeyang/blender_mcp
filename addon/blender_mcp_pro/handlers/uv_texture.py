"""UV & Texture（10）。"""
from __future__ import annotations

import math
import os

import bmesh
import bpy

from ..registry import command
from ..utils import ToolError, abs_path, color4, enum_check, find_image, find_object, mode, select_only

_METHODS = ["ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH", "SMART_PROJECT", "CUBE", "CYLINDER", "SPHERE", "LIGHTMAP"]
_BAKE_TYPES = ["COMBINED", "AO", "SHADOW", "POSITION", "NORMAL", "UV", "ROUGHNESS", "EMIT", "ENVIRONMENT", "DIFFUSE",
               "GLOSSY", "TRANSMISSION"]


def _mesh(name):
    o = find_object(name, "MESH")
    return o, o.data


def _uv_bounds(me):
    uv = me.uv_layers.active
    if uv is None or not len(uv.data):
        return None
    us = [d.uv.x for d in uv.data]
    vs = [d.uv.y for d in uv.data]
    return {"min": [round(min(us), 6), round(min(vs), 6)], "max": [round(max(us), 6), round(max(vs), 6)]}


@command("list_uv_maps", mutates=False)
def list_uv_maps(object: str):
    o, me = _mesh(object)
    return [{"name": u.name, "active": u == me.uv_layers.active, "active_render": u.active_render} for u in me.uv_layers]


@command("add_uv_map")
def add_uv_map(object: str, name: str | None = None, set_active: bool = True):
    o, me = _mesh(object)
    uv = me.uv_layers.new(name=name or "UVMap")
    if set_active:
        me.uv_layers.active = uv
    return {"object": o.name, "uv_map": uv.name, "uv_maps": [u.name for u in me.uv_layers]}


@command("remove_uv_map")
def remove_uv_map(object: str, name: str):
    o, me = _mesh(object)
    uv = me.uv_layers.get(name)
    if uv is None:
        raise ToolError(f"uv map '{name}' not found. Available: {', '.join(u.name for u in me.uv_layers)}")
    me.uv_layers.remove(uv)
    return {"object": o.name, "removed": name, "uv_maps": [u.name for u in me.uv_layers]}


@command("unwrap_uv")
def unwrap_uv(object: str, method: str = "ANGLE_BASED", margin: float = 0.001, angle_limit: float | None = None,
              uv_map: str | None = None):
    o, me = _mesh(object)
    m = enum_check(method, _METHODS, "method")
    if uv_map:
        uv = me.uv_layers.get(uv_map)
        if uv is None:
            raise ToolError(f"uv map '{uv_map}' not found")
        me.uv_layers.active = uv
    elif not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    with mode(o, "EDIT"):
        bpy.ops.mesh.select_all(action="SELECT")
        if m in ("ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH"):
            bpy.ops.uv.unwrap(method=m, margin=margin)
        elif m == "SMART_PROJECT":
            bpy.ops.uv.smart_project(angle_limit=angle_limit if angle_limit is not None else math.radians(66), island_margin=margin)
        elif m == "CUBE":
            bpy.ops.uv.cube_project(scale_to_bounds=True)
        elif m == "CYLINDER":
            bpy.ops.uv.cylinder_project(scale_to_bounds=True)
        elif m == "SPHERE":
            bpy.ops.uv.sphere_project(scale_to_bounds=True)
        elif m == "LIGHTMAP":
            bpy.ops.uv.lightmap_pack(PREF_MARGIN_DIV=max(margin, 0.001) * 100)
    return {"object": o.name, "method": m, "uv_map": me.uv_layers.active.name, "uv_bounds": _uv_bounds(me)}


@command("pack_uv_islands")
def pack_uv_islands(object: str, margin: float = 0.001, rotate: bool = True):
    o, me = _mesh(object)
    if not me.uv_layers:
        raise ToolError(f"'{o.name}' has no UV map; unwrap_uv first")
    with mode(o, "EDIT"):
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(margin=margin, rotate=rotate)
    return {"object": o.name, "uv_bounds": _uv_bounds(me)}


@command("mark_seams")
def mark_seams(object: str, edges: list[int] | None = None, from_sharp: bool = False, clear: bool = False):
    o, me = _mesh(object)
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        bm.edges.ensure_lookup_table()
        if clear:
            for e in bm.edges:
                e.seam = False
        if from_sharp:
            for e in bm.edges:
                if not e.smooth:
                    e.seam = True
        for i in edges or []:
            if i < 0 or i >= len(bm.edges):
                raise ToolError(f"edge index {i} out of range (0..{len(bm.edges) - 1})")
            bm.edges[i].seam = True
        count = sum(1 for e in bm.edges if e.seam)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return {"object": o.name, "seams": count}


@command("create_image")
def create_image(name: str, width: int = 1024, height: int = 1024, color=None, alpha: bool = True, float_buffer: bool = False):
    img = bpy.data.images.new(name, int(width), int(height), alpha=alpha, float_buffer=float_buffer)
    if color is not None:
        img.generated_color = color4(color)
    return {"name": img.name, "size": list(img.size), "alpha": alpha, "float_buffer": float_buffer}


@command("bake_texture")
def bake_texture(object: str, bake_type: str, image: str | None = None, size: int = 1024, output_path: str | None = None,
                 margin: int = 16, selected_to_active: bool = False, cage_extrusion: float = 0.0, samples: int = 16):
    o, me = _mesh(object)
    bt = enum_check(bake_type, _BAKE_TYPES, "bake_type")
    sc = bpy.context.scene
    prev_engine, prev_samples, prev_device = sc.render.engine, sc.cycles.samples, sc.cycles.device
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(samples)
    sc.cycles.device = "CPU"
    if image and image in bpy.data.images:
        img = find_image(image)
    else:
        img = bpy.data.images.new(image or f"{o.name}_{bt}", int(size), int(size))
    if not me.uv_layers:
        unwrap_uv(o.name, "SMART_PROJECT")
    if not any(s.material for s in o.material_slots):
        mat = bpy.data.materials.new(f"{o.name}_bake")
        if o.material_slots:
            o.material_slots[0].material = mat
        else:
            me.materials.append(mat)
    bake_nodes = []
    for slot in o.material_slots:
        mat = slot.material
        if mat is None:
            continue
        if mat.node_tree is None:
            mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.name = "__mcp_bake_target"
        mat.node_tree.nodes.active = node
        bake_nodes.append((mat, node))
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if selected_to_active:
        others = [x for x in bpy.context.selected_objects if x != o]
        select_only(others + [o], o)
    else:
        select_only([o], o)
    try:
        bpy.ops.object.bake(type=bt, margin=int(margin), use_selected_to_active=selected_to_active,
                            cage_extrusion=cage_extrusion, use_clear=True)
    except RuntimeError as e:
        raise ToolError(f"bake failed: {e}") from e
    finally:
        for mat, node in bake_nodes:
            mat.node_tree.nodes.remove(node)
        sc.render.engine, sc.cycles.samples, sc.cycles.device = prev_engine, prev_samples, prev_device
    out = {"object": o.name, "bake_type": bt, "image": img.name, "size": list(img.size)}
    if output_path:
        out["path"] = save_image(img.name, output_path)["path"]
    return out


@command("save_image")
def save_image(image: str, path: str, format: str | None = None):
    img = find_image(image)
    p = abs_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fmt_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR", ".tif": "TIFF", ".tiff": "TIFF", ".bmp": "BMP", ".tga": "TARGA"}
    img.filepath_raw = p
    img.file_format = format.upper() if format else fmt_map.get(os.path.splitext(p)[1].lower(), "PNG")
    img.save()
    return {"image": img.name, "path": p, "format": img.file_format, "size_bytes": os.path.getsize(p)}


@command("list_images", mutates=False)
def list_images():
    return [{"name": i.name, "size": list(i.size), "filepath": i.filepath, "has_data": i.has_data, "users": i.users,
             "source": i.source, "colorspace": i.colorspace_settings.name} for i in bpy.data.images]
