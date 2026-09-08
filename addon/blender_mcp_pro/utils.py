"""handler 共用：查找、序列化、模式切换、RNA 属性写入。模块顶层不得调用 bpy。"""
from __future__ import annotations

import fnmatch
from contextlib import contextmanager
from typing import Any, Iterable

import bpy
import mathutils


class ToolError(Exception):
    """参数/查找错误，信息面向 LLM 可读。"""


class NoViewportError(ToolError):
    """需要 3D 视图（GUI），无头模式不可用。"""


def no_viewport():
    raise NoViewportError("此工具需要 Blender GUI 的 3D 视图，无头（-b）模式不可用")


# ---------- 查找 ----------

def _not_found(kind: str, name: str, candidates: Iterable[str]) -> ToolError:
    cands = sorted(candidates)
    close = [c for c in cands if name.lower() in c.lower() or c.lower() in name.lower()] or cands
    hint = ", ".join(close[:10])
    return ToolError(f"{kind} '{name}' not found. Available: {hint}" if hint else f"{kind} '{name}' not found (none exist)")


def find_object(name: str, obj_type: str | None = None) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        pool = [o.name for o in bpy.data.objects if obj_type is None or o.type == obj_type]
        raise _not_found("Object", name, pool)
    if obj_type and obj.type != obj_type:
        raise ToolError(f"Object '{name}' is {obj.type}, expected {obj_type}")
    return obj


def find_material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m is None:
        raise _not_found("Material", name, (x.name for x in bpy.data.materials))
    return m


def find_node_group(name: str) -> bpy.types.NodeTree:
    g = bpy.data.node_groups.get(name)
    if g is None:
        raise _not_found("NodeGroup", name, (x.name for x in bpy.data.node_groups))
    return g


def find_image(name: str) -> bpy.types.Image:
    i = bpy.data.images.get(name)
    if i is None:
        raise _not_found("Image", name, (x.name for x in bpy.data.images))
    return i


def find_action(name: str) -> bpy.types.Action:
    a = bpy.data.actions.get(name)
    if a is None:
        raise _not_found("Action", name, (x.name for x in bpy.data.actions))
    return a


def find_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c is None:
        raise _not_found("Collection", name, (x.name for x in bpy.data.collections))
    return c


def find_camera(name: str) -> bpy.types.Object:
    return find_object(name, "CAMERA")


def find_light(name: str) -> bpy.types.Object:
    return find_object(name, "LIGHT")


def find_armature(name: str) -> bpy.types.Object:
    return find_object(name, "ARMATURE")


def find_texture(name: str):
    t = bpy.data.textures.get(name)
    if t is None:
        raise _not_found("Texture", name, (x.name for x in bpy.data.textures))
    return t


def resolve_objects(objects) -> list[bpy.types.Object]:
    """list[str] | str | {"pattern"|"collection"|"type"|"selected"} → 对象列表。"""
    if objects is None:
        raise ToolError("'objects' is required")
    if isinstance(objects, str):
        return [find_object(objects)]
    if isinstance(objects, list):
        return [find_object(n) for n in objects]
    if isinstance(objects, dict):
        if "pattern" in objects:
            res = [o for o in bpy.data.objects if fnmatch.fnmatchcase(o.name, objects["pattern"])]
        elif "collection" in objects:
            res = list(find_collection(objects["collection"]).all_objects)
        elif "type" in objects:
            res = [o for o in bpy.data.objects if o.type == objects["type"].upper()]
        elif objects.get("selected"):
            res = list(bpy.context.selected_objects)
        else:
            raise ToolError("objects filter must be one of pattern / collection / type / selected")
        if not res:
            raise ToolError(f"no objects matched {objects}")
        return res
    raise ToolError(f"unsupported objects spec: {objects!r}")


# ---------- 序列化 ----------

def vec(v) -> list[float]:
    return [round(float(x), 6) for x in v]


def serialize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (mathutils.Vector, mathutils.Euler, mathutils.Color, mathutils.Quaternion)):
        return vec(value)
    if isinstance(value, mathutils.Matrix):
        return [vec(row) for row in value]
    if isinstance(value, bpy.types.ID):
        return {"name": value.name, "type": type(value).__name__}
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(str(x) for x in value)
    if isinstance(value, (list, tuple)):
        return [serialize(x) for x in value]
    if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
        try:
            return [serialize(x) for x in value]
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def dimensions_of(o: bpy.types.Object) -> list[float]:
    """o.dimensions 依赖 depsgraph 评估：刚改完 scale 立刻读会拿到上一次的值。

    局部包围盒本身不含 object scale，所以手算 bbox_size * scale 就是当前真值，
    而且是 O(1)，不必为了一个返回值去 update() 整个 view layer。
    """
    bb = o.bound_box
    return [round((max(c[i] for c in bb) - min(c[i] for c in bb)) * o.scale[i], 6) for i in range(3)]


def obj_brief(o: bpy.types.Object) -> dict:
    return {
        "name": o.name,
        "type": o.type,
        "location": vec(o.location),
        "rotation": vec(o.rotation_euler),
        "scale": vec(o.scale),
        "dimensions": dimensions_of(o),
        "collections": [c.name for c in o.users_collection],
        "visible": not o.hide_viewport,
        "parent": o.parent.name if o.parent else None,
    }


def mat_brief(m: bpy.types.Material) -> dict:
    return {"name": m.name, "users": m.users, "nodes": len(m.node_tree.nodes) if m.node_tree else 0}


# ---------- 选择、模式、朝向 ----------

def select_only(objs: Iterable[bpy.types.Object], active: bpy.types.Object | None = None):
    objs = list(objs)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        try:
            o.hide_set(False)
            o.select_set(True)
        except RuntimeError:
            pass
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


@contextmanager
def mode(obj: bpy.types.Object, target: str = "EDIT"):
    """把 obj 设为活动并切到 target 模式，退出时恢复。"""
    prev_active = bpy.context.view_layer.objects.active
    prev_selected = list(bpy.context.selected_objects)
    prev_mode = obj.mode
    if bpy.context.mode != "OBJECT" and prev_active is not None:
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only([obj], obj)
    if obj.mode != target:
        bpy.ops.object.mode_set(mode=target)
    try:
        yield obj
    finally:
        if obj.mode != prev_mode:
            bpy.ops.object.mode_set(mode=prev_mode)
        keep = [o for o in prev_selected if o.name in bpy.data.objects]
        select_only(keep, prev_active if prev_active and prev_active.name in bpy.data.objects else None)


def refresh():
    """同一 handler 里改完 location 立刻读 matrix_world 会是旧值，先让 depsgraph 评估一次。"""
    bpy.context.view_layer.update()


def target_point(target) -> mathutils.Vector:
    """对象名 → 世界坐标；[x,y,z] → Vector。"""
    if isinstance(target, str):
        refresh()
        return find_object(target).matrix_world.translation.copy()
    if isinstance(target, (list, tuple)) and len(target) == 3:
        return mathutils.Vector(target)
    raise ToolError("target must be an object name or [x, y, z]")


def look_at(obj: bpy.types.Object, target, use_constraint: bool = False) -> dict:
    """让 obj 的 -Z 轴指向 target（相机/灯光约定）。"""
    if use_constraint:
        if isinstance(target, str):
            tgt = find_object(target)
        else:
            tgt = bpy.data.objects.new(f"{obj.name}_Target", None)
            link_to_scene(tgt)
            tgt.location = target_point(target)
        for c in list(obj.constraints):
            if c.type == "TRACK_TO":
                obj.constraints.remove(c)
        c = obj.constraints.new("TRACK_TO")
        c.target = tgt
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
        return {"constraint": c.name, "target": tgt.name}
    refresh()
    direction = target_point(target) - obj.matrix_world.translation
    if direction.length == 0:
        raise ToolError("object is at the target position; cannot orient")
    quat = direction.to_track_quat("-Z", "Y")
    if obj.parent:
        quat = (obj.parent.matrix_world.to_quaternion().inverted() @ quat)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = quat.to_euler("XYZ")
    return {"rotation": vec(obj.rotation_euler)}


# ---------- RNA 属性 ----------

_POINTER_LOOKUP = {
    "Object": lambda n: find_object(n),
    "Material": lambda n: find_material(n),
    "NodeTree": lambda n: find_node_group(n),
    "GeometryNodeTree": lambda n: find_node_group(n),
    "Image": lambda n: find_image(n),
    "Collection": lambda n: find_collection(n),
    "Texture": lambda n: find_texture(n),
    "Action": lambda n: find_action(n),
}


def rna_props(target) -> dict:
    """可写属性表：name → {type, description, enum?, array_length?, pointer_type?, default?}。"""
    out = {}
    for p in target.bl_rna.properties:
        if p.identifier == "rna_type" or p.is_readonly:
            continue
        d: dict[str, Any] = {"type": p.type, "description": p.description}
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


def set_props(target, settings: dict | None, tool_hint: str = "") -> list[str]:
    """按 RNA 校验写入属性；指针属性接受名字；枚举校验；未知键报错并列出可用键。"""
    if not settings:
        return []
    props = {p.identifier: p for p in target.bl_rna.properties if not p.is_readonly}
    changed = []
    for key, value in settings.items():
        p = props.get(key)
        if p is None:
            raise ToolError(f"{tool_hint}unknown property '{key}' for {type(target).__name__}. "
                            f"Available: {', '.join(sorted(props))}")
        if p.type == "POINTER":
            if value is None:
                setattr(target, key, None)
            else:
                kind = p.fixed_type.identifier
                lookup = _POINTER_LOOKUP.get(kind)
                if lookup is None:
                    raise ToolError(f"cannot set pointer property '{key}' (type {kind}) by name")
                setattr(target, key, lookup(value))
        elif p.type == "ENUM":
            opts = [e.identifier for e in p.enum_items]
            if p.is_enum_flag:
                vals = value if isinstance(value, list) else [value]
                setattr(target, key, {enum_check(v, opts, key) for v in vals})
            else:
                setattr(target, key, enum_check(value, opts, key))
        else:
            setattr(target, key, value)
        changed.append(key)
    return changed


def enum_check(value, options, what: str):
    if isinstance(value, str):
        if value in options:
            return value
        if value.upper() in options:
            return value.upper()
    raise ToolError(f"invalid {what} '{value}'. Options: {', '.join(options)}")


def color4(c, default_alpha: float = 1.0) -> tuple:
    if c is None:
        raise ToolError("color is required")
    c = list(c)
    if len(c) == 3:
        c.append(default_alpha)
    if len(c) != 4:
        raise ToolError("color must be [r,g,b] or [r,g,b,a]")
    return tuple(float(x) for x in c)


def link_to_scene(obj: bpy.types.Object, collection: str | None = None):
    coll = find_collection(collection) if collection else bpy.context.scene.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)


def abs_path(path: str) -> str:
    import os
    return os.path.abspath(bpy.path.abspath(os.path.expanduser(path)))
