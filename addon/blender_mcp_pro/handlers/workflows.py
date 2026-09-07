"""Workflows（7）：组合其它 handler 的宏。直接调 Python 函数，不走 socket。"""
from __future__ import annotations

import math
import os
import random

import bmesh
import bpy
from mathutils import Vector

from ..registry import command
from ..utils import ToolError, abs_path, find_object, link_to_scene, look_at, obj_brief, refresh, resolve_objects, select_only, vec
from . import animation as A
from . import camera as C
from . import geometry_nodes as GN
from . import io as IO
from . import lights as L
from . import materials as M
from . import modifiers as MOD
from . import render as R
from . import scene as S

_KELVIN = [(2000, (1.0, 0.55, 0.2)), (3000, (1.0, 0.70, 0.45)), (4000, (1.0, 0.82, 0.65)), (5000, (1.0, 0.90, 0.80)),
           (6500, (1.0, 1.0, 1.0)), (8000, (0.85, 0.90, 1.0)), (10000, (0.75, 0.83, 1.0))]


def _kelvin_rgb(k: float):
    k = max(_KELVIN[0][0], min(_KELVIN[-1][0], k))
    for (k0, c0), (k1, c1) in zip(_KELVIN, _KELVIN[1:]):
        if k0 <= k <= k1:
            t = (k - k0) / (k1 - k0)
            return [a + (b - a) * t for a, b in zip(c0, c1)]
    return [1.0, 1.0, 1.0]


def _bounds(objs):
    refresh()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx, (mn + mx) / 2, max((mx - mn).length / 2, 0.01)


@command("setup_three_point_lighting")
def setup_three_point_lighting(target: str, distance: float = 6.0, height: float = 3.0, key_energy: float = 1000.0,
                               fill_ratio: float = 0.4, rim_ratio: float = 0.8, color_temp: float | None = None):
    t = find_object(target)
    refresh()
    c = t.matrix_world.translation
    color = _kelvin_rgb(color_temp) if color_temp else None
    d = distance
    specs = [("Key", (-0.7 * d, -0.7 * d, height), key_energy, 2.0),
             ("Fill", (0.8 * d, -0.6 * d, height * 0.5), key_energy * fill_ratio, 3.0),
             ("Rim", (0.3 * d, d, height * 1.2), key_energy * rim_ratio, 1.5)]
    made = []
    for name, off, energy, size in specs:
        info = L.create_light("AREA", name=name, location=list(c + Vector(off)), energy=energy, color=color, size=size, target=target)
        made.append(info)
    return {"target": t.name, "lights": made}


def _make_backdrop(name: str, center: Vector, radius: float, floor_z: float) -> bpy.types.Object:
    w, depth, h, bend = radius * 8, radius * 6, radius * 6, radius * 1.5
    bm = bmesh.new()
    x0, x1 = -w / 2, w / 2
    y_front, y_back = -depth * 0.6, depth * 0.4
    v = [bm.verts.new((x0, y_front, 0)), bm.verts.new((x1, y_front, 0)), bm.verts.new((x1, y_back, 0)), bm.verts.new((x0, y_back, 0)),
         bm.verts.new((x1, y_back, h)), bm.verts.new((x0, y_back, h))]
    bm.faces.new((v[0], v[1], v[2], v[3]))
    bm.faces.new((v[3], v[2], v[4], v[5]))
    bm.edges.ensure_lookup_table()
    corner = [e for e in bm.edges if {e.verts[0], e.verts[1]} == {v[2], v[3]}]
    bmesh.ops.bevel(bm, geom=corner, offset=bend, segments=12, affect="EDGES", profile=0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link_to_scene(o)
    o.location = (center.x, center.y, floor_z)
    for p in me.polygons:
        p.use_smooth = True
    return o


@command("setup_studio_scene")
def setup_studio_scene(subject: str | None = None, backdrop: bool = True, ground: bool = True, hdri_path: str | None = None,
                       camera: bool = True):
    created = []
    if subject:
        subj = find_object(subject)
        mn, mx, center, r = _bounds([subj])
        floor_z = mn.z
    else:
        subj, center, r, floor_z = None, Vector((0, 0, 0)), 2.0, 0.0
    mat = bpy.data.materials.get("Studio_Backdrop") or bpy.data.materials.new("Studio_Backdrop")
    M._apply_principled(mat, {"Base Color": [0.8, 0.8, 0.8, 1], "Roughness": 0.6})
    if backdrop:
        o = _make_backdrop("Backdrop", center, r, floor_z)
        o.data.materials.append(mat)
        created.append(o.name)
    elif ground:
        S.create_primitive("plane", name="Ground", location=[center.x, center.y, floor_z], size=r * 10)
        bpy.data.objects["Ground"].data.materials.append(mat)
        created.append("Ground")
    if hdri_path:
        L.set_world_lighting(hdri_path=hdri_path)
    else:
        L.set_world_lighting(color=[0.05, 0.05, 0.05], strength=1.0)
        if subj:
            for info in setup_three_point_lighting(subj.name, distance=r * 3, height=r * 1.5, key_energy=250 * r * r)["lights"]:
                created.append(info["name"])
    cam_name = None
    if camera:
        cam = C.create_camera(name="StudioCam", location=[center.x, center.y - r * 4, center.z + r], lens=50)
        cam_name = cam["name"]
        if subj:
            C.frame_objects(cam_name, [subj.name], margin=1.3)
        else:
            look_at(bpy.data.objects[cam_name], list(center))
        created.append(cam_name)
    return {"subject": subj.name if subj else None, "created": created, "camera": cam_name}


@command("turntable_animation")
def turntable_animation(object: str, frames: int = 120, revolutions: float = 1.0, camera: str | None = None):
    o = find_object(object)
    refresh()
    pivot = bpy.data.objects.new(f"{o.name}_Turntable", None)
    link_to_scene(pivot)
    pivot.location = o.matrix_world.translation.copy()
    pivot.empty_display_type = "PLAIN_AXES"
    S.set_parent(o.name, pivot.name, keep_transform=True)
    A.set_frame_range(1, int(frames))
    A.insert_keyframe(pivot.name, "rotation_euler", frame=1, index=2, value=0.0)
    A.insert_keyframe(pivot.name, "rotation_euler", frame=int(frames), index=2, value=2 * math.pi * revolutions)
    A.set_interpolation(pivot.name, "LINEAR", data_path="rotation_euler")
    A.add_fcurve_modifier(pivot.name, "rotation_euler", "CYCLES")
    if camera is None:
        cam = C.create_camera(name="TurntableCam", location=list(pivot.location + Vector((0, -6, 3))), lens=50)["name"]
    else:
        cam = find_object(camera, "CAMERA").name
    C.frame_objects(cam, [o.name], margin=1.3)
    bpy.context.scene.frame_set(1)
    return {"object": o.name, "pivot": pivot.name, "camera": cam, "frames": int(frames), "revolutions": revolutions}


@command("quick_product_render")
def quick_product_render(object: str, output_path: str, resolution=None, samples: int = 64, engine: str = "BLENDER_EEVEE"):
    o = find_object(object)
    mn, mx, center, r = _bounds([o])
    lights = setup_three_point_lighting(o.name, distance=r * 3, height=r * 1.5, key_energy=250 * r * r)
    cam = C.create_camera(name="ProductCam", location=list(center + Vector((r * 2, -r * 3, r * 1.5))), lens=60)["name"]
    C.frame_objects(cam, [o.name], margin=1.25)
    L.set_world_lighting(color=[0.1, 0.1, 0.1], strength=1.0)
    R.set_render_settings(engine=engine, resolution=resolution or [1280, 960], percentage=100, samples=samples, film_transparent=True)
    out = R.render_image(output_path=output_path, return_image=True, max_preview_size=768)
    out["camera"] = cam
    out["lights"] = [l["name"] for l in lights["lights"]]
    return out


_ROLE_TOKENS = {
    "base_color": ("basecolor", "base_color", "albedo", "diffuse", "diff", "color", "col"),
    "roughness": ("roughness", "rough", "rgh"),
    "metallic": ("metallic", "metalness", "metal"),
    "normal": ("normal", "nor", "nrm", "norm"),
    "height": ("height", "displacement", "disp", "bump"),
    "ao": ("ao", "ambientocclusion", "ambient_occlusion", "occlusion"),
}
_IMG_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".tga", ".bmp")


def classify_texture(filename: str) -> str | None:
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    tokens = [t for t in stem.replace("-", "_").replace(" ", "_").split("_") if t]
    for role, keys in _ROLE_TOKENS.items():
        if any(t in keys for t in tokens):
            return role
    for role, keys in _ROLE_TOKENS.items():
        if any(k in stem for k in keys if len(k) >= 4):
            return role
    return None


@command("material_from_texture_folder")
def material_from_texture_folder(folder: str, name: str | None = None, assign_to: str | None = None):
    root = abs_path(folder)
    if not os.path.isdir(root):
        raise ToolError(f"folder not found: {root}")
    found = {}
    for f in sorted(os.listdir(root)):
        if not f.lower().endswith(_IMG_EXT):
            continue
        role = classify_texture(f)
        if role and role not in found:
            found[role] = os.path.join(root, f)
    if not found:
        raise ToolError(f"no recognizable texture maps in {root} (looked for basecolor/roughness/metallic/normal/height/ao in file names)")
    mat_name = name or os.path.basename(root.rstrip(os.sep))
    info = M.create_pbr_material(mat_name, base_color=found.get("base_color"), roughness=found.get("roughness"),
                                 metallic=found.get("metallic"), normal=found.get("normal"), height=found.get("height"),
                                 ao=found.get("ao"), assign_to=assign_to)
    info["detected"] = {k: os.path.basename(v) for k, v in found.items()}
    return info


def _surface_area(o) -> float:
    refresh()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        area = sum(p.area for p in me.polygons)
    finally:
        ev.to_mesh_clear()
    s = o.matrix_world.to_scale()
    return area * abs(s.x * s.y)


@command("scatter_objects")
def scatter_objects(source: str, surface: str, count: int = 100, seed: int = 0, scale_range=None, align_to_normal: bool = True,
                    method: str = "GEOMETRY_NODES"):
    src = find_object(source)
    surf = find_object(surface, "MESH")
    method = method.upper()
    if method == "GEOMETRY_NODES":
        gname = f"Scatter_{src.name}"
        r = GN.create_geometry_nodes(surf.name, group_name=gname, modifier_name=gname)
        tree = bpy.data.node_groups[r["node_group"]]
        density = count / max(_surface_area(surf), 1e-6)
        nodes = [
            {"type": "DistributePointsOnFaces", "name": "Dist", "inputs": {"Density": density, "Seed": seed}},
            {"type": "ObjectInfo", "name": "Src", "properties": {"transform_space": "RELATIVE"}, "inputs": {"Object": src.name, "As Instance": True}},
            {"type": "InstanceOnPoints", "name": "Inst"},
            {"type": "JoinGeometry", "name": "Join"},
        ]
        links = [
            {"from_node": "Group Input", "from_socket": "Geometry", "to_node": "Dist", "to_socket": "Mesh"},
            {"from_node": "Dist", "from_socket": "Points", "to_node": "Inst", "to_socket": "Points"},
            {"from_node": "Src", "from_socket": "Geometry", "to_node": "Inst", "to_socket": "Instance"},
            {"from_node": "Inst", "from_socket": "Instances", "to_node": "Join", "to_socket": "Geometry"},
            {"from_node": "Group Input", "from_socket": "Geometry", "to_node": "Join", "to_socket": "Geometry"},
            {"from_node": "Join", "from_socket": "Geometry", "to_node": "Group Output", "to_socket": "Geometry"},
        ]
        if align_to_normal:
            links.append({"from_node": "Dist", "from_socket": "Rotation", "to_node": "Inst", "to_socket": "Rotation"})
        if scale_range:
            nodes.append({"type": "FunctionNodeRandomValue", "name": "Scale", "properties": {"data_type": "FLOAT"},
                          "inputs": {"Min": float(scale_range[0]), "Max": float(scale_range[1]), "Seed": seed}})
            links.append({"from_node": "Scale", "from_socket": "Value", "to_node": "Inst", "to_socket": "Scale"})
        GN.unlink_geometry_nodes(tree.name, "Group Output", "Geometry")  # 拆掉直通，保留 Group Input/Output
        GN.build_geometry_node_tree(tree.name, nodes, links, clear=False)
        refresh()
        dg = bpy.context.evaluated_depsgraph_get()
        n = sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == surf)
        return {"method": method, "source": src.name, "surface": surf.name, "node_group": tree.name, "requested": count, "instances": n}
    if method != "COPIES":
        raise ToolError("method must be GEOMETRY_NODES or COPIES")
    rng = random.Random(seed)
    refresh()
    bm = bmesh.new()
    bm.from_mesh(surf.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    tris = [(f, f.calc_area()) for f in bm.faces]
    total = sum(a for _, a in tris) or 1.0
    parent = bpy.data.objects.new(f"Scatter_{src.name}", None)
    link_to_scene(parent)
    made = []
    for i in range(int(count)):
        x = rng.uniform(0, total)
        acc = 0.0
        face = tris[-1][0]
        for f, a in tris:
            acc += a
            if x <= acc:
                face = f
                break
        r1, r2 = rng.random(), rng.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        v0, v1, v2 = [v.co for v in face.verts]
        p = v0 + (v1 - v0) * r1 + (v2 - v0) * r2
        world = surf.matrix_world @ p
        dup = src.copy()
        dup.name = f"{src.name}_scatter_{i:03d}"
        link_to_scene(dup)
        dup.parent = parent
        dup.location = world
        if align_to_normal:
            n = (surf.matrix_world.to_3x3() @ face.normal).normalized()
            dup.rotation_euler = n.to_track_quat("Z", "Y").to_euler()
        if scale_range:
            s = rng.uniform(float(scale_range[0]), float(scale_range[1]))
            dup.scale = [c * s for c in src.scale]
        made.append(dup.name)
    bm.free()
    return {"method": method, "source": src.name, "surface": surf.name, "parent": parent.name, "instances": len(made), "objects": made[:20]}


@command("export_for_game")
def export_for_game(objects, path: str, format: str = "GLB", apply_modifiers: bool = True, triangulate: bool = True,
                    scale: float = 1.0, forward: str = "-Z", up: str = "Y"):
    objs = resolve_objects(objects)
    fmt = format.lower()
    if fmt not in ("glb", "gltf", "fbx", "obj"):
        raise ToolError("format must be GLB/GLTF/FBX/OBJ")
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    coll = bpy.data.collections.new("__mcp_export")
    bpy.context.scene.collection.children.link(coll)
    copies = []
    try:
        for o in objs:
            c = o.copy()
            if o.data is not None:
                c.data = o.data.copy()
            c.name = f"{o.name}"  # 会得到 .001 后缀；导出后原名对象不受影响
            coll.objects.link(c)
            c.parent = None
            c.matrix_world = o.matrix_world.copy()
            copies.append(c)
        for c in copies:
            if c.type != "MESH":
                continue
            select_only([c], c)
            if apply_modifiers:
                for m in list(c.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=m.name)
                    except RuntimeError:
                        c.modifiers.remove(m)
            if triangulate:
                m = c.modifiers.new("Triangulate", "TRIANGULATE")
                bpy.ops.object.modifier_apply(modifier=m.name)
            if scale != 1.0:
                c.scale = [s * scale for s in c.scale]
                c.location = c.location * scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        options = {}
        if fmt == "fbx":
            options = {"axis_forward": forward, "axis_up": up, "apply_scale_options": "FBX_SCALE_ALL", "mesh_smooth_type": "FACE"}
        elif fmt == "obj":
            options = {"forward_axis": forward.replace("-", "NEGATIVE_") if forward.startswith("-") else forward,
                       "up_axis": up.replace("-", "NEGATIVE_") if up.startswith("-") else up}
        for c in copies:
            c.name = c.name.rsplit(".", 1)[0] + "_export" if c.name.endswith((".001", ".002", ".003")) else c.name
        r = IO.export_file(path, fmt, [c.name for c in copies], options)
        r["source_objects"] = [o.name for o in objs]
        r["applied_modifiers"], r["triangulated"] = apply_modifiers, triangulate
        return r
    finally:
        for c in copies:
            data = c.data
            bpy.data.objects.remove(c, do_unlink=True)
            if data is not None and data.users == 0:
                try:
                    getattr(bpy.data, {"MESH": "meshes", "CURVE": "curves"}.get(type(data).__name__.upper(), "meshes")).remove(data)
                except Exception:  # noqa: BLE001
                    pass
        bpy.data.collections.remove(coll)
