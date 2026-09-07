"""Materials（9）。"""
from __future__ import annotations

import bpy

from .. import nodes_common as nc
from ..registry import command
from ..utils import ToolError, abs_path, color4, find_material, find_object, mat_brief, serialize, vec

_MAIN_SOCKETS = ("Base Color", "Metallic", "Roughness", "IOR", "Alpha", "Emission Color", "Emission Strength",
                 "Subsurface Weight", "Specular IOR Level", "Transmission Weight", "Coat Weight", "Sheen Weight")


def _output(tree):
    for n in tree.nodes:
        if n.bl_idname == "ShaderNodeOutputMaterial":
            return n
    return tree.nodes.new("ShaderNodeOutputMaterial")


def principled(mat: bpy.types.Material):
    tree = nc.get_tree(material=mat.name)
    for n in tree.nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            return n
    n = tree.nodes.new("ShaderNodeBsdfPrincipled")
    out = _output(tree)
    tree.links.new(n.outputs["BSDF"], out.inputs["Surface"])
    return n


def _users(mat) -> list[str]:
    return [o.name for o in bpy.data.objects if any(s.material == mat for s in o.material_slots)]


def material_info(mat) -> dict:
    tree = mat.node_tree
    bsdf = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None) if tree else None
    images = []
    if tree:
        for n in tree.nodes:
            if n.bl_idname == "ShaderNodeTexImage" and n.image:
                images.append({"node": n.name, "image": n.image.name, "path": n.image.filepath})
    return {
        "name": mat.name, "users": mat.users, "objects": _users(mat),
        "node_count": len(tree.nodes) if tree else 0,
        "principled": {s: nc.socket_value(bsdf.inputs[s]) for s in _MAIN_SOCKETS if bsdf and s in bsdf.inputs} if bsdf else None,
        "images": images,
        "settings": {"surface_render_method": mat.surface_render_method, "backface_culling": mat.use_backface_culling,
                     "displacement_method": mat.displacement_method, "pass_index": mat.pass_index},
    }


@command("list_materials", mutates=False)
def list_materials(used_only: bool = False):
    out = []
    for m in bpy.data.materials:
        if used_only and m.users == 0:
            continue
        d = mat_brief(m)
        d["objects"] = _users(m)
        out.append(d)
    return out


@command("get_material_info", mutates=False)
def get_material_info(name: str):
    return material_info(find_material(name))


def _apply_principled(mat, values: dict):
    bsdf = principled(mat)
    for k, v in values.items():
        if v is None:
            continue
        nc.set_socket_value(nc.find_socket(bsdf.inputs, k), v)


@command("create_material")
def create_material(name: str, base_color=None, metallic=None, roughness=None, emission_color=None,
                    emission_strength=None, alpha=None, ior=None, assign_to: str | None = None):
    mat = bpy.data.materials.new(name)
    _apply_principled(mat, {"Base Color": base_color, "Metallic": metallic, "Roughness": roughness,
                            "Emission Color": emission_color, "Emission Strength": emission_strength,
                            "Alpha": alpha, "IOR": ior})
    if alpha is not None and alpha < 1:
        mat.surface_render_method = "BLENDED"
    if assign_to:
        assign_material(assign_to, mat.name)
    return material_info(mat)


@command("assign_material")
def assign_material(object: str, material: str, slot: int | None = None):
    o = find_object(object)
    m = find_material(material)
    if o.data is None or not hasattr(o.data, "materials"):
        raise ToolError(f"object '{o.name}' ({o.type}) cannot hold materials")
    if slot is None:
        slot = 0
    while len(o.material_slots) <= slot:
        o.data.materials.append(None)
    o.material_slots[slot].material = m
    return {"object": o.name, "slot": slot, "materials": [s.material.name if s.material else None for s in o.material_slots]}


@command("set_principled_inputs")
def set_principled_inputs(material: str, inputs: dict):
    mat = find_material(material)
    bsdf = principled(mat)
    changed = {}
    for k, v in inputs.items():
        sock = nc.find_socket(bsdf.inputs, k)
        nc.set_socket_value(sock, v)
        changed[sock.name] = nc.socket_value(sock)
    return {"material": mat.name, "changed": changed}


@command("set_material_settings")
def set_material_settings(material: str, surface_render_method: str | None = None, backface_culling: bool | None = None,
                          displacement_method: str | None = None, pass_index: int | None = None):
    mat = find_material(material)
    if surface_render_method is not None:
        mat.surface_render_method = surface_render_method.upper()
    if backface_culling is not None:
        mat.use_backface_culling = backface_culling
    if displacement_method is not None:
        mat.displacement_method = displacement_method.upper()
    if pass_index is not None:
        mat.pass_index = pass_index
    return material_info(mat)["settings"]


_TARGETS = ("Base Color", "Roughness", "Metallic", "Normal", "Alpha", "Emission Color", "Height", "Displacement", "AO",
            "Specular IOR Level", "Sheen Weight", "Coat Weight", "Transmission Weight", "Subsurface Weight")


def _add_image_texture(mat, image_path: str, target: str, colorspace=None, projection=None) -> dict:
    tree = nc.get_tree(material=mat.name)
    bsdf = principled(mat)
    path = abs_path(image_path)
    try:
        img = bpy.data.images.load(path, check_existing=True)
    except RuntimeError as e:
        raise ToolError(f"cannot load image '{image_path}': {e}") from e
    if target not in _TARGETS:
        raise ToolError(f"unknown target '{target}'. Options: {', '.join(_TARGETS)}")
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.name = tex.label = f"Tex {target}"
    n_tex = sum(1 for n in tree.nodes if n.bl_idname == "ShaderNodeTexImage")
    tex.location = (bsdf.location.x - 600, bsdf.location.y + 300 - 300 * (n_tex - 1))
    if colorspace:
        img.colorspace_settings.name = colorspace
    elif target not in ("Base Color", "Emission Color"):
        img.colorspace_settings.name = "Non-Color"
    if projection:
        tex.projection = projection.upper()
    extra = None
    if target == "Normal":
        extra = tree.nodes.new("ShaderNodeNormalMap")
        extra.location = (bsdf.location.x - 300, tex.location.y)
        tree.links.new(tex.outputs["Color"], extra.inputs["Color"])
        tree.links.new(extra.outputs["Normal"], bsdf.inputs["Normal"])
    elif target in ("Height", "Displacement"):
        extra = tree.nodes.new("ShaderNodeDisplacement")
        extra.location = (bsdf.location.x + 100, bsdf.location.y - 500)
        tree.links.new(tex.outputs["Color"], extra.inputs["Height"])
        tree.links.new(extra.outputs["Displacement"], _output(tree).inputs["Displacement"])
    elif target == "AO":
        extra = tree.nodes.new("ShaderNodeMix")
        extra.data_type = "RGBA"
        extra.blend_type = "MULTIPLY"
        extra.inputs["Factor"].default_value = 1.0
        extra.location = (bsdf.location.x - 300, bsdf.location.y + 300)
        base_links = [l for l in tree.links if l.to_node == bsdf and l.to_socket.name == "Base Color"]
        if base_links:
            src = base_links[0].from_socket
            tree.links.remove(base_links[0])
            tree.links.new(src, extra.inputs[6])   # A (RGBA)
        else:
            extra.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
        tree.links.new(tex.outputs["Color"], extra.inputs[7])  # B
        tree.links.new(extra.outputs[2], bsdf.inputs["Base Color"])  # Result (RGBA)
    else:
        tree.links.new(tex.outputs["Color"], bsdf.inputs[target])
    return {"material": mat.name, "node": tex.name, "image": img.name, "path": img.filepath, "target": target,
            "colorspace": img.colorspace_settings.name, "helper_node": extra.name if extra else None}


@command("add_image_texture")
def add_image_texture(material: str, image_path: str, target: str = "Base Color", colorspace: str | None = None,
                      projection: str | None = None):
    return _add_image_texture(find_material(material), image_path, target, colorspace, projection)


@command("create_pbr_material")
def create_pbr_material(name: str, base_color=None, roughness=None, metallic=None, normal=None, height=None, ao=None,
                        assign_to: str | None = None):
    mat = bpy.data.materials.new(name)
    principled(mat)
    added = []
    for target, path in (("Base Color", base_color), ("Roughness", roughness), ("Metallic", metallic),
                         ("Normal", normal), ("Height", height), ("AO", ao)):
        if path:
            added.append(_add_image_texture(mat, path, target))
    if assign_to:
        assign_material(assign_to, mat.name)
    info = material_info(mat)
    info["textures"] = added
    return info


@command("delete_material")
def delete_material(name: str, unlink_only: bool = False):
    mat = find_material(name)
    objs = _users(mat)
    for o in bpy.data.objects:
        for s in o.material_slots:
            if s.material == mat:
                s.material = None
    if not unlink_only:
        bpy.data.materials.remove(mat)
    return {"material": name, "unlinked_from": objs, "deleted": not unlink_only}
