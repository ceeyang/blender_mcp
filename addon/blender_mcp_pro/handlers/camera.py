"""Camera（7）。"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from ..registry import command
from ..utils import ToolError, find_camera, find_object, link_to_scene, look_at, obj_brief, refresh, resolve_objects, serialize, vec


def camera_info(o) -> dict:
    c = o.data
    d = obj_brief(o)
    d.update({"lens": c.lens, "type": c.type, "sensor_width": c.sensor_width, "sensor_fit": c.sensor_fit,
              "ortho_scale": c.ortho_scale, "clip_start": c.clip_start, "clip_end": c.clip_end,
              "shift_x": c.shift_x, "shift_y": c.shift_y, "fov_deg": round(math.degrees(c.angle), 3),
              "dof": {"enabled": c.dof.use_dof, "focus_object": c.dof.focus_object.name if c.dof.focus_object else None,
                      "focus_distance": c.dof.focus_distance, "fstop": c.dof.aperture_fstop},
              "is_active": bpy.context.scene.camera == o})
    return serialize(d)


@command("list_cameras", mutates=False)
def list_cameras():
    return [camera_info(o) for o in bpy.context.scene.objects if o.type == "CAMERA"]


@command("get_camera_info", mutates=False)
def get_camera_info(name: str):
    return camera_info(find_camera(name))


def _apply(c, lens=None, type=None, ortho_scale=None, clip_start=None, clip_end=None, shift_x=None, shift_y=None,
           sensor_width=None, dof=None):
    if lens is not None:
        c.lens = lens
    if type is not None:
        c.type = type.upper()
    if ortho_scale is not None:
        c.ortho_scale = ortho_scale
    if clip_start is not None:
        c.clip_start = clip_start
    if clip_end is not None:
        c.clip_end = clip_end
    if shift_x is not None:
        c.shift_x = shift_x
    if shift_y is not None:
        c.shift_y = shift_y
    if sensor_width is not None:
        c.sensor_width = sensor_width
    if dof:
        if "enabled" in dof:
            c.dof.use_dof = bool(dof["enabled"])
        if "focus_object" in dof:
            c.dof.focus_object = find_object(dof["focus_object"]) if dof["focus_object"] else None
        if "focus_distance" in dof:
            c.dof.focus_distance = float(dof["focus_distance"])
        if "fstop" in dof:
            c.dof.aperture_fstop = float(dof["fstop"])
        if "enabled" not in dof:
            c.dof.use_dof = True


@command("create_camera")
def create_camera(name: str | None = None, location=None, rotation=None, lens=None, type=None, sensor_width=None,
                  clip_start=None, clip_end=None, set_active: bool = True):
    name = name or "Camera"
    cam = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, cam)
    link_to_scene(o)
    if location is not None:
        o.location = location
    if rotation is not None:
        o.rotation_euler = rotation
    _apply(cam, lens=lens, type=type, sensor_width=sensor_width, clip_start=clip_start, clip_end=clip_end)
    if set_active:
        bpy.context.scene.camera = o
    return camera_info(o)


@command("set_camera")
def set_camera(name: str, lens=None, type=None, ortho_scale=None, clip_start=None, clip_end=None, shift_x=None,
               shift_y=None, dof: dict | None = None):
    o = find_camera(name)
    _apply(o.data, lens, type, ortho_scale, clip_start, clip_end, shift_x, shift_y, dof=dof)
    return camera_info(o)


@command("set_active_camera")
def set_active_camera(name: str):
    o = find_camera(name)
    bpy.context.scene.camera = o
    return {"active_camera": o.name}


@command("point_camera_at")
def point_camera_at(camera: str, target, use_constraint: bool = False):
    o = find_camera(camera)
    r = look_at(o, target, use_constraint)
    r["camera"] = o.name
    return r


def _bounding_sphere(objs):
    refresh()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    if not pts:
        raise ToolError("objects have no geometry")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (mn + mx) / 2
    r = max((p - center).length for p in pts)
    return center, max(r, 0.01)


@command("frame_objects")
def frame_objects(camera: str, objects, margin: float = 1.1):
    cam = find_camera(camera)
    objs = resolve_objects(objects)
    center, r = _bounding_sphere(objs)
    c = cam.data
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / sc.render.resolution_y
    if c.type == "ORTHO":
        c.ortho_scale = 2 * r * margin * max(aspect, 1 / aspect)  # ortho_scale 覆盖长边，短边要放大 aspect 倍
        dist = r * 3 * margin
    else:
        fov = c.angle  # sensor_fit AUTO：对应较长边
        long_fov, short_fov = fov, 2 * math.atan(math.tan(fov / 2) / max(aspect, 1 / aspect))
        dist = r / math.sin(min(long_fov, short_fov) / 2) * margin
    refresh()
    direction = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    world_pos = center - direction.normalized() * dist
    if cam.parent:
        cam.location = cam.parent.matrix_world.inverted() @ world_pos
    else:
        cam.location = world_pos
    look_at(cam, list(center))
    d = camera_info(cam)
    d.update({"distance": round(dist, 6), "target_center": vec(center), "target_radius": round(r, 6)})
    return d
