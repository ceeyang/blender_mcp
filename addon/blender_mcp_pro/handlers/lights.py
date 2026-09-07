"""Lights（6）。"""
from __future__ import annotations

import bpy

from ..registry import command
from ..utils import ToolError, abs_path, color4, enum_check, find_light, link_to_scene, look_at, obj_brief, vec

_LIGHT_TYPES = ["POINT", "SUN", "SPOT", "AREA"]


def light_info(o) -> dict:
    light = o.data
    d = obj_brief(o)
    d.update({"light_type": light.type, "energy": light.energy, "color": vec(light.color),
              "radius": light.shadow_soft_size, "use_shadow": light.use_shadow})
    if light.type == "SPOT":
        d.update({"spot_size": light.spot_size, "spot_blend": light.spot_blend})
    elif light.type == "AREA":
        d.update({"size": light.size, "size_y": light.size_y, "shape": light.shape})
    elif light.type == "SUN":
        d.update({"angle": light.angle})
    return d


@command("list_lights", mutates=False)
def list_lights():
    return [light_info(o) for o in bpy.context.scene.objects if o.type == "LIGHT"]


@command("get_light_info", mutates=False)
def get_light_info(name: str):
    return light_info(find_light(name))


def _apply(light, energy=None, color=None, radius=None, size=None, shape=None, spot_size=None, spot_blend=None,
           use_shadow=None, angle=None):
    if energy is not None:
        light.energy = energy
    if color is not None:
        light.color = color4(color)[:3]
    if radius is not None:
        light.shadow_soft_size = radius
    if use_shadow is not None:
        light.use_shadow = use_shadow
    if light.type == "AREA":
        if size is not None:
            light.size = size
        if shape is not None:
            light.shape = enum_check(shape, ["SQUARE", "RECTANGLE", "DISK", "ELLIPSE"], "shape")
    if light.type == "SPOT":
        if spot_size is not None:
            light.spot_size = spot_size
        if spot_blend is not None:
            light.spot_blend = spot_blend
    if light.type == "SUN" and angle is not None:
        light.angle = angle


@command("create_light")
def create_light(type: str, name: str | None = None, location=None, rotation=None, energy=None, color=None,
                 radius=None, size=None, spot_size=None, spot_blend=None, target=None):
    t = enum_check(type, _LIGHT_TYPES, "type")
    name = name or t.title()
    light = bpy.data.lights.new(name, t)
    o = bpy.data.objects.new(name, light)
    link_to_scene(o)
    if location is not None:
        o.location = location
    if rotation is not None:
        o.rotation_euler = rotation
    _apply(light, energy=energy, color=color, radius=radius, size=size, spot_size=spot_size, spot_blend=spot_blend)
    if target is not None:
        look_at(o, target)
    return light_info(o)


@command("set_light")
def set_light(name: str, energy=None, color=None, radius=None, size=None, shape=None, spot_size=None, spot_blend=None,
              use_shadow=None, angle=None):
    o = find_light(name)
    _apply(o.data, energy, color, radius, size, shape, spot_size, spot_blend, use_shadow, angle)
    return light_info(o)


@command("point_light_at")
def point_light_at(light: str, target, use_constraint: bool = False):
    o = find_light(light)
    r = look_at(o, target, use_constraint)
    r["light"] = o.name
    return r


def _world_tree():
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    w = sc.world
    if w.node_tree is None:
        w.use_nodes = True
    tree = w.node_tree
    out = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputWorld"), None) or tree.nodes.new("ShaderNodeOutputWorld")
    bg = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeBackground"), None)
    if bg is None:
        bg = tree.nodes.new("ShaderNodeBackground")
        tree.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w, tree, bg


@command("set_world_lighting")
def set_world_lighting(color=None, strength=None, hdri_path=None, rotation=None):
    w, tree, bg = _world_tree()
    if color is not None:
        bg.inputs["Color"].default_value = color4(color)
    if strength is not None:
        bg.inputs["Strength"].default_value = float(strength)
    env = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeTexEnvironment"), None)
    if hdri_path is not None:
        try:
            img = bpy.data.images.load(abs_path(hdri_path), check_existing=True)
        except RuntimeError as e:
            raise ToolError(f"cannot load HDRI '{hdri_path}': {e}") from e
        if env is None:
            env = tree.nodes.new("ShaderNodeTexEnvironment")
            env.location = (bg.location.x - 400, bg.location.y)
        env.image = img
        tree.links.new(env.outputs["Color"], bg.inputs["Color"])
        mapping = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeMapping"), None)
        if mapping is None:
            mapping = tree.nodes.new("ShaderNodeMapping")
            mapping.location = (env.location.x - 300, env.location.y)
            coord = tree.nodes.new("ShaderNodeTexCoord")
            coord.location = (mapping.location.x - 250, mapping.location.y)
            tree.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
            tree.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    if rotation is not None:
        mapping = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeMapping"), None)
        if mapping is None:
            raise ToolError("rotation needs an HDRI (hdri_path) first")
        mapping.inputs["Rotation"].default_value = rotation
    return {"world": w.name, "color": vec(bg.inputs["Color"].default_value), "strength": bg.inputs["Strength"].default_value,
            "hdri": env.image.filepath if env and env.image else None}
