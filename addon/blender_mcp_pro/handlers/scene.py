"""Scene & Objects（16）。"""
from __future__ import annotations

from collections import Counter

import bpy
from mathutils import Vector

from ..registry import command
from ..utils import (ToolError, enum_check, find_collection, find_object, link_to_scene, obj_brief,
                     resolve_objects, select_only, serialize, vec)

# type → (op 路径, size 走哪个参数, radius 走哪个参数, segments 走哪个参数)
_PRIMITIVES = {
    "cube": ("mesh.primitive_cube_add", "size", None, None),
    "plane": ("mesh.primitive_plane_add", "size", None, None),
    "monkey": ("mesh.primitive_monkey_add", "size", None, None),
    "uv_sphere": ("mesh.primitive_uv_sphere_add", "radius", "radius", "segments"),
    "ico_sphere": ("mesh.primitive_ico_sphere_add", "radius", "radius", "subdivisions"),
    "cylinder": ("mesh.primitive_cylinder_add", "radius", "radius", "vertices"),
    "cone": ("mesh.primitive_cone_add", "radius1", "radius1", "vertices"),
    "torus": ("mesh.primitive_torus_add", "major_radius", "major_radius", "major_segments"),
    "circle": ("mesh.primitive_circle_add", "radius", "radius", "vertices"),
    "empty": ("object.empty_add", "radius", "radius", None),
    "text": ("object.text_add", "radius", "radius", None),
}
_ALIASES = {"sphere": "uv_sphere", "icosphere": "ico_sphere", "box": "cube"}


def _op(path: str):
    mod, name = path.split(".")
    return getattr(getattr(bpy.ops, mod), name)


def _ensure_object_mode():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _coll_tree(c: bpy.types.Collection) -> dict:
    return {"name": c.name, "objects": [o.name for o in c.objects], "children": [_coll_tree(ch) for ch in c.children]}


@command("get_scene_info", mutates=False)
def get_scene_info():
    sc = bpy.context.scene
    active = bpy.context.view_layer.objects.active
    return {
        "name": sc.name,
        "file": bpy.data.filepath,
        "frame_start": sc.frame_start, "frame_end": sc.frame_end, "frame_current": sc.frame_current,
        "fps": sc.render.fps,
        "unit_system": sc.unit_settings.system, "unit_scale": sc.unit_settings.scale_length,
        "render_engine": sc.render.engine,
        "active_object": active.name if active else None,
        "active_camera": sc.camera.name if sc.camera else None,
        "selected": [o.name for o in bpy.context.selected_objects],
        "object_count": len(sc.objects),
        "objects_by_type": dict(Counter(o.type for o in sc.objects)),
        "collections": _coll_tree(sc.collection),
        "materials": len(bpy.data.materials),
    }


@command("list_objects", mutates=False)
def list_objects(type: str | None = None, collection: str | None = None, pattern: str | None = None, selected: bool = False):
    import fnmatch
    objs = list(find_collection(collection).all_objects) if collection else list(bpy.context.scene.objects)
    if type:
        objs = [o for o in objs if o.type == type.upper()]
    if pattern:
        objs = [o for o in objs if fnmatch.fnmatchcase(o.name, pattern)]
    if selected:
        sel = {o.name for o in bpy.context.selected_objects}
        objs = [o for o in objs if o.name in sel]
    return [obj_brief(o) for o in sorted(objs, key=lambda o: o.name)]


@command("get_object_info", mutates=False)
def get_object_info(name: str):
    o = find_object(name)
    d = obj_brief(o)
    d.update({
        "world_location": vec(o.matrix_world.translation),
        "rotation_mode": o.rotation_mode,
        "hide_render": o.hide_render, "hide_select": o.hide_select,
        "children": [c.name for c in o.children],
        "data": o.data.name if o.data else None,
        "modifiers": [{"name": m.name, "type": m.type, "show_viewport": m.show_viewport} for m in o.modifiers],
        "constraints": [{"name": c.name, "type": c.type} for c in o.constraints],
        "materials": [s.material.name if s.material else None for s in o.material_slots],
        "custom_properties": {k: serialize(o[k]) for k in o.keys() if not k.startswith("_")},
        "animated": bool(o.animation_data and o.animation_data.action),
    })
    if o.type == "MESH":
        me = o.data
        d["mesh"] = {"vertices": len(me.vertices), "edges": len(me.edges), "faces": len(me.polygons),
                     "uv_maps": [u.name for u in me.uv_layers],
                     "vertex_groups": [g.name for g in o.vertex_groups],
                     "shape_keys": [k.name for k in me.shape_keys.key_blocks] if me.shape_keys else []}
    elif o.type == "CAMERA":
        c = o.data
        d["camera"] = {"lens": c.lens, "type": c.type, "clip_start": c.clip_start, "clip_end": c.clip_end,
                       "is_active": bpy.context.scene.camera == o}
    elif o.type == "LIGHT":
        light = o.data
        d["light"] = {"light_type": light.type, "energy": light.energy, "color": vec(light.color)}
    elif o.type == "ARMATURE":
        d["armature"] = {"bones": len(o.data.bones)}
    elif o.type == "EMPTY":
        d["empty"] = {"display_type": o.empty_display_type, "size": o.empty_display_size}
    return d


@command("create_primitive")
def create_primitive(type: str, name: str | None = None, location=None, rotation=None, scale=None,
                     size: float | None = None, radius: float | None = None, depth: float | None = None,
                     segments: int | None = None, text: str | None = None, collection: str | None = None):
    t = _ALIASES.get(type.lower(), type.lower())
    if t not in _PRIMITIVES:
        raise ToolError(f"unknown primitive '{type}'. Options: {', '.join(sorted(_PRIMITIVES))}")
    op_path, size_key, radius_key, seg_key = _PRIMITIVES[t]
    kw = {}
    if location is not None:
        kw["location"] = location
    if rotation is not None:
        kw["rotation"] = rotation
    if scale is not None and t not in ("empty", "text"):
        kw["scale"] = scale
    if size is not None:
        kw[size_key] = size
    if radius is not None and radius_key:
        kw[radius_key] = radius
    if depth is not None and t in ("cylinder", "cone"):
        kw["depth"] = depth
    if depth is not None and t == "torus":
        kw["minor_radius"] = depth
    if segments is not None and seg_key:
        kw[seg_key] = segments
    _ensure_object_mode()
    _op(op_path)(**kw)
    obj = bpy.context.view_layer.objects.active
    if t == "text" and text is not None:
        obj.data.body = text
    if scale is not None and t in ("empty", "text"):
        obj.scale = scale
    if name:
        obj.name = name
        if obj.data:
            obj.data.name = name
    if collection:
        target = find_collection(collection)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target.objects.link(obj)
    return obj_brief(obj)


@command("delete_object")
def delete_object(objects, delete_children: bool = False):
    objs = resolve_objects(objects)
    if delete_children:
        extra = []
        for o in objs:
            extra.extend(o.children_recursive)
        objs = list({o.name: o for o in objs + extra}.values())
    _ensure_object_mode()
    names = [o.name for o in objs]
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return {"deleted": names}


@command("duplicate_object")
def duplicate_object(name: str, new_name: str | None = None, linked: bool = False, offset=None):
    o = find_object(name)
    new = o.copy()
    if o.data is not None and not linked:
        new.data = o.data.copy()
    if o.users_collection:
        for c in o.users_collection:
            c.objects.link(new)
    else:
        link_to_scene(new)
    if new_name:
        new.name = new_name
        if new.data is not None and not linked:
            new.data.name = new_name
    if offset is not None:
        new.location = o.location + Vector(offset)
    return obj_brief(new)


@command("set_transform")
def set_transform(name: str, location=None, rotation=None, scale=None, relative: bool = False):
    o = find_object(name)
    if location is not None:
        o.location = (o.location + Vector(location)) if relative else Vector(location)
    if rotation is not None:
        o.rotation_mode = "XYZ" if o.rotation_mode not in ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX") else o.rotation_mode
        if relative:
            o.rotation_euler = [a + b for a, b in zip(o.rotation_euler, rotation)]
        else:
            o.rotation_euler = rotation
    if scale is not None:
        o.scale = [a * b for a, b in zip(o.scale, scale)] if relative else scale
    return obj_brief(o)


@command("rename_object")
def rename_object(name: str, new_name: str, rename_data: bool = True):
    o = find_object(name)
    old = o.name
    o.name = new_name
    if rename_data and o.data is not None:
        o.data.name = new_name
    return {"old": old, "name": o.name, "data": o.data.name if o.data else None}


@command("set_parent")
def set_parent(child: str, parent: str | None = None, keep_transform: bool = True):
    c = find_object(child)
    if parent is None:
        mw = c.matrix_world.copy()
        c.parent = None
        if keep_transform:
            c.matrix_world = mw
        return {"child": c.name, "parent": None}
    p = find_object(parent)
    if p == c or p in c.children_recursive:
        raise ToolError("cannot parent an object to itself or its descendant")
    c.parent = p
    if keep_transform:
        c.matrix_parent_inverse = p.matrix_world.inverted()
    else:
        c.matrix_parent_inverse.identity()
    return {"child": c.name, "parent": p.name, "world_location": vec(c.matrix_world.translation)}


@command("set_visibility")
def set_visibility(objects, hide_viewport: bool | None = None, hide_render: bool | None = None, hide_select: bool | None = None):
    objs = resolve_objects(objects)
    for o in objs:
        if hide_viewport is not None:
            o.hide_viewport = hide_viewport
            try:
                o.hide_set(hide_viewport)
            except RuntimeError:
                pass
        if hide_render is not None:
            o.hide_render = hide_render
        if hide_select is not None:
            o.hide_select = hide_select
    return {"objects": [o.name for o in objs]}


@command("select_objects")
def select_objects(objects, mode: str = "replace", active: str | None = None):
    mode = enum_check(mode.lower() if isinstance(mode, str) else mode, ["replace", "add", "remove"], "mode")
    objs = resolve_objects(objects)
    if mode == "replace":
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
    for o in objs:
        try:
            o.select_set(mode != "remove")
        except RuntimeError as e:
            raise ToolError(f"cannot select '{o.name}': {e}") from e
    if active:
        bpy.context.view_layer.objects.active = find_object(active)
    elif mode != "remove" and objs:
        bpy.context.view_layer.objects.active = objs[0]
    return {"selected": [o.name for o in bpy.context.selected_objects],
            "active": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None}


@command("manage_collection")
def manage_collection(action: str, name: str, parent: str | None = None, objects=None, new_name: str | None = None):
    action = enum_check(action.lower(), ["create", "delete", "move", "link", "unlink", "rename"], "action")
    scene_coll = bpy.context.scene.collection
    if action == "create":
        if bpy.data.collections.get(name):
            raise ToolError(f"collection '{name}' already exists")
        c = bpy.data.collections.new(name)
        (find_collection(parent) if parent else scene_coll).children.link(c)
        if objects:
            for o in resolve_objects(objects):
                c.objects.link(o)
        return {"collection": c.name, "parent": parent or scene_coll.name}
    c = find_collection(name)
    if action == "delete":
        for o in list(c.all_objects):
            if not o.users_collection or all(uc == c or uc in c.children_recursive for uc in o.users_collection):
                scene_coll.objects.link(o)
        bpy.data.collections.remove(c)
        return {"deleted": name}
    if action == "rename":
        if not new_name:
            raise ToolError("new_name is required for rename")
        c.name = new_name
        return {"collection": c.name}
    objs = resolve_objects(objects)
    if action == "move":
        for o in objs:
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            c.objects.link(o)
    elif action == "link":
        for o in objs:
            if o.name not in c.objects:
                c.objects.link(o)
    elif action == "unlink":
        for o in objs:
            if o.name in c.objects:
                c.objects.unlink(o)
            if not o.users_collection:
                scene_coll.objects.link(o)
    return {"collection": c.name, "objects": [o.name for o in c.objects]}


@command("join_objects")
def join_objects(objects, target: str | None = None):
    objs = resolve_objects(objects)
    if any(o.type != "MESH" for o in objs):
        raise ToolError("join_objects only supports MESH objects")
    tgt = find_object(target) if target else objs[0]
    if tgt not in objs:
        objs.append(tgt)
    _ensure_object_mode()
    select_only(objs, tgt)
    bpy.ops.object.join()
    return obj_brief(tgt)


@command("apply_transforms")
def apply_transforms(objects, location: bool = True, rotation: bool = True, scale: bool = True):
    objs = resolve_objects(objects)
    _ensure_object_mode()
    select_only(objs, objs[0])
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale, isolate_users=True)
    return [obj_brief(o) for o in objs]


_ORIGIN = {"GEOMETRY": ("ORIGIN_GEOMETRY", "MEDIAN"), "CURSOR": ("ORIGIN_CURSOR", "MEDIAN"),
           "CENTER_OF_MASS": ("ORIGIN_CENTER_OF_MASS", "MEDIAN"), "CENTER_OF_VOLUME": ("ORIGIN_CENTER_OF_VOLUME", "MEDIAN"),
           "BOUNDS": ("ORIGIN_GEOMETRY", "BOUNDS"), "GEOMETRY_TO_ORIGIN": ("GEOMETRY_ORIGIN", "MEDIAN")}


@command("set_origin")
def set_origin(name: str, type: str = "GEOMETRY"):
    o = find_object(name)
    t = enum_check(type, list(_ORIGIN), "type")
    op_type, center = _ORIGIN[t]
    _ensure_object_mode()
    select_only([o], o)
    bpy.ops.object.origin_set(type=op_type, center=center)
    return obj_brief(o)


@command("set_custom_property")
def set_custom_property(name: str, key: str, value=None):
    o = find_object(name)
    if value is None:
        if key in o:
            del o[key]
        return {"object": o.name, "removed": key}
    o[key] = value
    return {"object": o.name, "key": key, "value": serialize(o[key])}
