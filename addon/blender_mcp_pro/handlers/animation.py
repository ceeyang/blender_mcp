"""Animation（15）。"""
from __future__ import annotations

import bpy

from ..registry import command
from ..utils import ToolError, enum_check, find_action, find_object, select_only, serialize, set_props, vec


def _fcurves(o):
    ad = o.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except AttributeError:
        pass
    try:
        cb = act.layers[0].strips[0].channelbag(ad.action_slot)
        return list(cb.fcurves) if cb else []
    except (IndexError, AttributeError, TypeError):
        return []


def _set_path(o, data_path: str, value, index=None):
    if data_path.startswith("["):
        key = data_path.strip("[]").strip("\"'")
        o[key] = value
        return
    if "." in data_path:
        base_path, attr = data_path.rsplit(".", 1)
        base = o.path_resolve(base_path)
    else:
        base, attr = o, data_path
    if index is not None:
        cur = list(getattr(base, attr))
        cur[index] = value
        setattr(base, attr, cur)
    else:
        setattr(base, attr, value)


def _fc_summary(fc) -> dict:
    kps = fc.keyframe_points
    return {"data_path": fc.data_path, "index": fc.array_index, "keyframes": len(kps),
            "range": [kps[0].co.x, kps[-1].co.x] if len(kps) else None,
            "modifiers": [m.type for m in fc.modifiers]}


@command("get_animation_info", mutates=False)
def get_animation_info(object: str | None = None):
    sc = bpy.context.scene
    d = {"frame_start": sc.frame_start, "frame_end": sc.frame_end, "frame_current": sc.frame_current, "fps": sc.render.fps,
         "actions": [a.name for a in bpy.data.actions],
         "animated_objects": [o.name for o in bpy.data.objects if o.animation_data and (o.animation_data.action or o.animation_data.nla_tracks)]}
    if object:
        o = find_object(object)
        ad = o.animation_data
        d["object"] = {
            "name": o.name,
            "action": ad.action.name if ad and ad.action else None,
            "fcurves": [_fc_summary(fc) for fc in _fcurves(o)],
            "nla_tracks": [{"name": t.name, "strips": [{"name": s.name, "action": s.action.name if s.action else None,
                                                        "frame_start": s.frame_start, "frame_end": s.frame_end}
                                                       for s in t.strips]} for t in ad.nla_tracks] if ad else [],
            "shape_keys": [k.name for k in o.data.shape_keys.key_blocks] if getattr(o.data, "shape_keys", None) else [],
        }
    return serialize(d)


@command("set_frame_range")
def set_frame_range(start: int, end: int, fps: int | None = None):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = int(start), int(end)
    if fps is not None:
        sc.render.fps = int(fps)
    return {"frame_start": sc.frame_start, "frame_end": sc.frame_end, "fps": sc.render.fps}


@command("set_current_frame", mutates=False)
def set_current_frame(frame: int):
    sc = bpy.context.scene
    sc.frame_set(int(frame))
    return {"frame_current": sc.frame_current}


@command("insert_keyframe")
def insert_keyframe(object: str, data_path: str, frame: int | None = None, index: int | None = None, value=None):
    o = find_object(object)
    if value is not None:
        _set_path(o, data_path, value, index)
    frame = bpy.context.scene.frame_current if frame is None else int(frame)
    try:
        o.keyframe_insert(data_path=data_path, frame=frame, index=-1 if index is None else index)
    except (TypeError, RuntimeError) as e:
        raise ToolError(f"cannot keyframe '{data_path}': {e}") from e
    return {"object": o.name, "data_path": data_path, "frame": frame, "value": serialize(o.path_resolve(data_path)),
            "action": o.animation_data.action.name}


@command("insert_keyframes_batch")
def insert_keyframes_batch(object: str, keys: list):
    o = find_object(object)
    n = 0
    for k in keys:
        frame = int(k["frame"])
        for key, dp in (("location", "location"), ("rotation", "rotation_euler"), ("scale", "scale")):
            if key in k and k[key] is not None:
                setattr(o, dp, k[key])
                o.keyframe_insert(data_path=dp, frame=frame)
                n += 1
        for extra, val in k.items():
            if extra in ("frame", "location", "rotation", "scale"):
                continue
            _set_path(o, extra, val)
            o.keyframe_insert(data_path=extra, frame=frame)
            n += 1
    return {"object": o.name, "inserted": n, "fcurves": [_fc_summary(fc) for fc in _fcurves(o)]}


@command("delete_keyframe")
def delete_keyframe(object: str, data_path: str, frame: int, index: int | None = None):
    o = find_object(object)
    ok = o.keyframe_delete(data_path=data_path, frame=int(frame), index=-1 if index is None else index)
    return {"object": o.name, "data_path": data_path, "frame": frame, "deleted": bool(ok)}


@command("list_keyframes", mutates=False)
def list_keyframes(object: str, data_path: str | None = None):
    o = find_object(object)
    out = []
    for fc in _fcurves(o):
        if data_path and fc.data_path != data_path:
            continue
        out.append({"data_path": fc.data_path, "index": fc.array_index,
                    "keyframes": [{"frame": kp.co.x, "value": kp.co.y, "interpolation": kp.interpolation, "easing": kp.easing}
                                  for kp in fc.keyframe_points],
                    "modifiers": [m.type for m in fc.modifiers]})
    return serialize(out)


@command("set_interpolation")
def set_interpolation(object: str, mode: str, easing: str | None = None, data_path: str | None = None, frame_range=None):
    o = find_object(object)
    modes = [e.identifier for e in bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items]
    m = enum_check(mode, modes, "mode")
    ez = enum_check(easing, [e.identifier for e in bpy.types.Keyframe.bl_rna.properties["easing"].enum_items], "easing") if easing else None
    n = 0
    for fc in _fcurves(o):
        if data_path and fc.data_path != data_path:
            continue
        for kp in fc.keyframe_points:
            if frame_range and not (frame_range[0] <= kp.co.x <= frame_range[1]):
                continue
            kp.interpolation = m
            if ez:
                kp.easing = ez
            n += 1
    return {"object": o.name, "changed": n, "interpolation": m, "easing": ez}


@command("add_fcurve_modifier")
def add_fcurve_modifier(object: str, data_path: str, type: str, settings: dict | None = None):
    o = find_object(object)
    t = enum_check(type, [e.identifier for e in bpy.types.FCurve.bl_rna.functions["modifiers"].parameters["type"].enum_items]
                   if "modifiers" in bpy.types.FCurve.bl_rna.functions else ["CYCLES", "NOISE", "LIMITS", "STEPPED", "ENVELOPE", "GENERATOR", "FNGENERATOR"],
                   "type")
    added = []
    for fc in _fcurves(o):
        if fc.data_path != data_path:
            continue
        m = fc.modifiers.new(t)
        set_props(m, settings, tool_hint=f"{t}: ")
        added.append({"data_path": fc.data_path, "index": fc.array_index, "modifier": m.type})
    if not added:
        raise ToolError(f"no fcurves with data_path '{data_path}' on '{o.name}'")
    return {"object": o.name, "added": added}


@command("assign_action")
def assign_action(object: str, action: str | None = None):
    o = find_object(object)
    ad = o.animation_data or o.animation_data_create()
    act = find_action(action) if action else bpy.data.actions.new(f"{o.name}Action")
    ad.action = act
    try:
        if getattr(act, "slots", None) and len(act.slots) and ad.action_slot is None:
            ad.action_slot = act.slots[0]
    except (AttributeError, TypeError):
        pass
    return {"object": o.name, "action": act.name, "fcurves": len(_fcurves(o))}


@command("nla_push_down")
def nla_push_down(object: str):
    o = find_object(object)
    ad = o.animation_data
    if not ad or not ad.action:
        raise ToolError(f"'{o.name}' has no active action")
    act = ad.action
    track = ad.nla_tracks.new()
    track.name = act.name
    strip = track.strips.new(act.name, int(act.frame_range[0]), act)
    ad.action = None
    return {"object": o.name, "track": track.name, "strip": strip.name, "frame_start": strip.frame_start, "frame_end": strip.frame_end}


@command("add_nla_strip")
def add_nla_strip(object: str, action: str, frame_start: int, track: str | None = None, blend_type: str | None = None):
    o = find_object(object)
    ad = o.animation_data or o.animation_data_create()
    act = find_action(action)
    tr = ad.nla_tracks.get(track) if track else None
    if tr is None:
        tr = ad.nla_tracks.new()
        tr.name = track or act.name
    try:
        strip = tr.strips.new(act.name, int(frame_start), act)
    except RuntimeError as e:
        raise ToolError(f"cannot add strip on track '{tr.name}' at {frame_start}: {e}") from e
    if blend_type:
        strip.blend_type = enum_check(blend_type, ["REPLACE", "COMBINE", "ADD", "SUBTRACT", "MULTIPLY"], "blend_type")
    return {"object": o.name, "track": tr.name, "strip": strip.name, "frame_start": strip.frame_start, "frame_end": strip.frame_end}


@command("bake_animation")
def bake_animation(object: str, frame_start: int | None = None, frame_end: int | None = None, step: int = 1,
                   visual_keying: bool = True, clear_constraints: bool = False):
    o = find_object(object)
    sc = bpy.context.scene
    fs = sc.frame_start if frame_start is None else int(frame_start)
    fe = sc.frame_end if frame_end is None else int(frame_end)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only([o], o)
    bpy.ops.nla.bake(frame_start=fs, frame_end=fe, step=int(step), only_selected=True, visual_keying=visual_keying,
                     clear_constraints=clear_constraints, bake_types={"OBJECT"})
    return {"object": o.name, "frames": [fs, fe], "fcurves": [_fc_summary(fc) for fc in _fcurves(o)]}


@command("list_shape_keys", mutates=False)
def list_shape_keys(object: str):
    o = find_object(object)
    sk = getattr(o.data, "shape_keys", None)
    if not sk:
        return []
    return [{"name": k.name, "value": round(k.value, 6), "min": k.slider_min, "max": k.slider_max,
             "relative_to": k.relative_key.name if k.relative_key else None, "mute": k.mute} for k in sk.key_blocks]


@command("set_shape_key")
def set_shape_key(object: str, name: str, value: float, frame: int | None = None):
    o = find_object(object)
    if not hasattr(o.data, "shape_keys"):
        raise ToolError(f"'{o.name}' ({o.type}) does not support shape keys")
    if not o.data.shape_keys:
        o.shape_key_add(name="Basis", from_mix=False)
    kb = o.data.shape_keys.key_blocks.get(name)
    created = False
    if kb is None:
        kb = o.shape_key_add(name=name, from_mix=False)
        created = True
    kb.value = float(value)
    if frame is not None:
        kb.keyframe_insert("value", frame=int(frame))
    return {"object": o.name, "shape_key": kb.name, "value": round(kb.value, 6), "created": created, "keyframed": frame}
