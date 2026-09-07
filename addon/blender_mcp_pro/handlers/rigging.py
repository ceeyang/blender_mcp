"""Rigging（12）。"""
from __future__ import annotations

import bpy

from ..registry import command
from ..utils import (ToolError, enum_check, find_armature, find_object, link_to_scene, mode, resolve_objects, select_only,
                     serialize, set_props, vec)

_PARENT_METHODS = {"AUTOMATIC": "ARMATURE_AUTO", "ENVELOPE": "ARMATURE_ENVELOPE", "EMPTY_GROUPS": "ARMATURE_NAME",
                   "DEFORM": "ARMATURE"}
_METARIGS = {"human": "armature_human_metarig_add", "basic_human": "armature_basic_human_metarig_add",
             "basic_quadruped": "armature_basic_quadruped_metarig_add", "cat": "armature_cat_metarig_add",
             "wolf": "armature_wolf_metarig_add", "horse": "armature_horse_metarig_add", "shark": "armature_shark_metarig_add",
             "bird": "armature_bird_metarig_add"}


def bone_info(b, pb=None) -> dict:
    d = {"name": b.name, "head": vec(b.head_local), "tail": vec(b.tail_local), "length": round(b.length, 6),
         "parent": b.parent.name if b.parent else None, "connected": b.use_connect, "deform": b.use_deform,
         "children": [c.name for c in b.children]}
    if pb is not None:
        d["pose"] = {"location": vec(pb.location), "rotation_mode": pb.rotation_mode,
                     "rotation_euler": vec(pb.rotation_euler), "rotation_quaternion": vec(pb.rotation_quaternion),
                     "scale": vec(pb.scale), "constraints": [{"name": c.name, "type": c.type} for c in pb.constraints]}
    return d


def _edit_bone(o, name):
    b = o.data.edit_bones.get(name)
    if b is None:
        raise ToolError(f"bone '{name}' not found on '{o.name}'. Available: {', '.join(x.name for x in o.data.edit_bones)}")
    return b


def _pose_bone(o, name):
    pb = o.pose.bones.get(name)
    if pb is None:
        raise ToolError(f"bone '{name}' not found on '{o.name}'. Available: {', '.join(x.name for x in o.pose.bones)}")
    return pb


def _add_bones(o, specs: list[dict]) -> list[str]:
    names = []
    with mode(o, "EDIT"):
        eb = o.data.edit_bones
        for s in specs:
            if "name" not in s or "head" not in s or "tail" not in s:
                raise ToolError("each bone needs name, head, tail")
            b = eb.new(s["name"])
            b.head = s["head"]
            b.tail = s["tail"]
            b.roll = float(s.get("roll", 0.0))
            b.use_deform = bool(s.get("deform", True))
            if s.get("parent"):
                b.parent = _edit_bone(o, s["parent"])
                b.use_connect = bool(s.get("connect", False))
            names.append(b.name)
    return names


@command("create_armature")
def create_armature(name: str | None = None, location=None, bones: list | None = None):
    name = name or "Armature"
    arm = bpy.data.armatures.new(name)
    o = bpy.data.objects.new(name, arm)
    link_to_scene(o)
    if location is not None:
        o.location = location
    created = _add_bones(o, bones) if bones else []
    return {"armature": o.name, "bones": created, "bone_count": len(o.data.bones)}


@command("list_bones", mutates=False)
def list_bones(armature: str, pose: bool = False):
    o = find_armature(armature)
    return [bone_info(b, o.pose.bones.get(b.name) if pose else None) for b in o.data.bones]


@command("add_bone")
def add_bone(armature: str, name: str, head, tail, parent: str | None = None, roll: float = 0.0, connect: bool = False):
    o = find_armature(armature)
    created = _add_bones(o, [{"name": name, "head": head, "tail": tail, "parent": parent, "roll": roll, "connect": connect}])
    return bone_info(o.data.bones[created[0]])


@command("set_bone")
def set_bone(armature: str, bone: str, head=None, tail=None, roll: float | None = None, parent: str | None = None,
             connect: bool | None = None, deform: bool | None = None, inherit_scale: str | None = None):
    o = find_armature(armature)
    with mode(o, "EDIT"):
        b = _edit_bone(o, bone)
        if head is not None:
            b.head = head
        if tail is not None:
            b.tail = tail
        if roll is not None:
            b.roll = roll
        if parent is not None:
            b.parent = None if parent == "" else _edit_bone(o, parent)
        if connect is not None:
            b.use_connect = connect
        if deform is not None:
            b.use_deform = deform
        if inherit_scale is not None:
            b.inherit_scale = enum_check(inherit_scale, ["FULL", "FIX_SHEAR", "ALIGNED", "AVERAGE", "NONE", "NONE_LEGACY"], "inherit_scale")
        name = b.name
    return bone_info(o.data.bones[name])


@command("remove_bone")
def remove_bone(armature: str, bone: str):
    o = find_armature(armature)
    with mode(o, "EDIT"):
        b = _edit_bone(o, bone)
        o.data.edit_bones.remove(b)
    return {"armature": o.name, "removed": bone, "bones": [b.name for b in o.data.bones]}


@command("parent_to_armature")
def parent_to_armature(objects, armature: str, method: str = "AUTOMATIC"):
    arm = find_armature(armature)
    objs = [o for o in resolve_objects(objects) if o != arm]
    if not objs:
        raise ToolError("no mesh objects to parent")
    m = _PARENT_METHODS[enum_check(method, list(_PARENT_METHODS), "method")]
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only(objs + [arm], arm)
    try:
        bpy.ops.object.parent_set(type=m)
    except RuntimeError as e:
        raise ToolError(f"parent_set failed: {e}") from e
    return {"armature": arm.name, "method": method.upper(),
            "objects": {o.name: {"parent": o.parent.name if o.parent else None,
                                 "modifiers": [x.type for x in o.modifiers],
                                 "vertex_groups": [g.name for g in o.vertex_groups]} for o in objs}}


@command("add_bone_constraint")
def add_bone_constraint(armature: str, bone: str, type: str, settings: dict | None = None):
    o = find_armature(armature)
    pb = _pose_bone(o, bone)
    types = [e.identifier for e in bpy.types.PoseBoneConstraints.bl_rna.functions["new"].parameters["type"].enum_items]
    t = enum_check(type, types, "type")
    c = pb.constraints.new(t)
    settings = dict(settings or {})
    if "target" in settings:
        tgt = settings.pop("target")
        c.target = find_object(tgt) if tgt else None
    if "subtarget" in settings:
        sub = settings.pop("subtarget")
        if c.target and c.target.type == "ARMATURE" and sub and sub not in c.target.data.bones:
            raise ToolError(f"subtarget bone '{sub}' not in '{c.target.name}'")
        c.subtarget = sub or ""
    set_props(c, settings, tool_hint=f"{t}: ")
    return {"armature": o.name, "bone": pb.name, "constraint": c.name, "type": c.type,
            "target": c.target.name if getattr(c, "target", None) else None, "subtarget": getattr(c, "subtarget", "")}


@command("set_pose")
def set_pose(armature: str, bones: dict, keyframe: bool = False, frame: int | None = None):
    o = find_armature(armature)
    frame = bpy.context.scene.frame_current if frame is None else int(frame)
    out = {}
    for name, t in bones.items():
        pb = _pose_bone(o, name)
        channels = []
        if "location" in t:
            pb.location = t["location"]
            channels.append("location")
        if "rotation_quaternion" in t:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = t["rotation_quaternion"]
            channels.append("rotation_quaternion")
        elif "rotation_euler" in t:
            if pb.rotation_mode not in ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"):
                pb.rotation_mode = "XYZ"
            pb.rotation_euler = t["rotation_euler"]
            channels.append("rotation_euler")
        if "scale" in t:
            pb.scale = t["scale"]
            channels.append("scale")
        if keyframe:
            for ch in channels:
                pb.keyframe_insert(ch, frame=frame)
        out[name] = bone_info(o.data.bones[name], pb)["pose"]
    bpy.context.view_layer.update()
    return {"armature": o.name, "keyframed_at": frame if keyframe else None, "bones": out}


@command("reset_pose")
def reset_pose(armature: str, bones: list | None = None):
    o = find_armature(armature)
    targets = [_pose_bone(o, n) for n in bones] if bones else list(o.pose.bones)
    for pb in targets:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_axis_angle = (0, 0, 1, 0)
        pb.scale = (1, 1, 1)
    return {"armature": o.name, "reset": [pb.name for pb in targets]}


@command("set_vertex_group_weights")
def set_vertex_group_weights(object: str, group: str, weights: list | None = None, all: float | None = None,
                             mode: str = "REPLACE"):
    o = find_object(object, "MESH")
    m = enum_check(mode, ["REPLACE", "ADD", "SUBTRACT"], "mode")
    vg = o.vertex_groups.get(group) or o.vertex_groups.new(name=group)
    n = 0
    if all is not None:
        vg.add(list(range(len(o.data.vertices))), float(all), m)
        n = len(o.data.vertices)
    for pair in weights or []:
        idx, w = int(pair[0]), float(pair[1])
        if idx < 0 or idx >= len(o.data.vertices):
            raise ToolError(f"vertex index {idx} out of range")
        vg.add([idx], w, m)
        n += 1
    return {"object": o.name, "group": vg.name, "vertices": n, "groups": [g.name for g in o.vertex_groups]}


def _ensure_rigify():
    if "rigify" not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module="rigify")


@command("add_rigify_metarig")
def add_rigify_metarig(type: str = "human", name: str | None = None):
    _ensure_rigify()
    t = enum_check(type.lower(), list(_METARIGS), "type")
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    getattr(bpy.ops.object, _METARIGS[t])()
    o = bpy.context.view_layer.objects.active
    if name:
        o.name = name
        o.data.name = name
    return {"metarig": o.name, "type": t, "bones": len(o.data.bones)}


@command("generate_rigify_rig")
def generate_rigify_rig(metarig: str):
    _ensure_rigify()
    o = find_armature(metarig)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only([o], o)
    try:
        bpy.ops.pose.rigify_generate()
    except RuntimeError as e:
        raise ToolError(f"rigify generate failed: {e}") from e
    rig = o.data.rigify_target_rig
    if rig is None:
        raise ToolError("rigify did not produce a rig")
    return {"metarig": o.name, "rig": rig.name, "bones": len(rig.data.bones)}
