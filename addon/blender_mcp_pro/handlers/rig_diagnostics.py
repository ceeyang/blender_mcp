"""Rig Diagnostics（7）。"""
from __future__ import annotations

import bpy

from ..registry import command
from ..utils import ToolError, find_armature, find_object

_SIDE_PAIRS = [(".L", ".R"), ("_L", "_R"), (".l", ".r"), ("_l", "_r"), ("Left", "Right"), ("left", "right")]


def _child_meshes(arm):
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.parent == arm or any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers):
            out.append(o)
    return out


def _armature_of(mesh):
    for m in mesh.modifiers:
        if m.type == "ARMATURE" and m.object:
            return m.object
    return mesh.parent if mesh.parent and mesh.parent.type == "ARMATURE" else None


def _vertex_weights(mesh, group_names=None):
    """每个顶点 → [(group_name, weight)]，可限定组名集合。"""
    names = {g.index: g.name for g in mesh.vertex_groups}
    res = []
    for v in mesh.data.vertices:
        ws = [(names[g.group], g.weight) for g in v.groups if g.group in names and (group_names is None or names[g.group] in group_names)]
        res.append(ws)
    return res


def _mirror_name(name):
    for a, b in _SIDE_PAIRS:
        if name.endswith(a):
            return name[: -len(a)] + b
        if name.endswith(b):
            return name[: -len(b)] + a
    return None


@command("check_rig", mutates=False)
def check_rig(armature: str):
    arm = find_armature(armature)
    issues = []

    def add(severity, code, message, fix, bone=None, obj=None):
        d = {"severity": severity, "code": code, "message": message, "fix_hint": fix}
        if bone:
            d["bone"] = bone
        if obj:
            d["object"] = obj
        issues.append(d)

    bones = list(arm.data.bones)
    roots = [b for b in bones if b.parent is None]
    if len(roots) > 1:
        add("info", "MULTIPLE_ROOTS", f"{len(roots)} root bones: {', '.join(b.name for b in roots)}",
            "通常只保留一根根骨，其余骨骼挂在它下面")
    for b in bones:
        if b.length < 1e-3:
            add("error", "ZERO_LENGTH_BONE", f"bone '{b.name}' length {b.length:.6f}", "删除或拉长该骨骼", bone=b.name)
        mirror = _mirror_name(b.name)
        if mirror and mirror not in arm.data.bones:
            add("info", "ASYMMETRIC_NAME", f"'{b.name}' has no mirror '{mirror}'", "补齐对称骨骼或改名", bone=b.name)
    if any(abs(s - 1) > 1e-4 for s in arm.scale):
        add("warning", "UNAPPLIED_SCALE", f"armature scale {tuple(round(s, 4) for s in arm.scale)}",
            "apply_transforms 应用缩放，否则蒙皮和约束会出问题", obj=arm.name)
    deform = [b.name for b in bones if b.use_deform]
    meshes = _child_meshes(arm)
    for m in meshes:
        groups = {g.name for g in m.vertex_groups}
        for name in deform:
            if name not in groups:
                add("warning", "DEFORM_BONE_NO_GROUP", f"deform bone '{name}' has no vertex group on '{m.name}'",
                    "parent_to_armature(AUTOMATIC) 或 set_vertex_group_weights", bone=name, obj=m.name)
        ws = _vertex_weights(m, set(deform) & groups)
        unweighted = sum(1 for w in ws if sum(x[1] for x in w) <= 1e-4)
        if unweighted:
            add("warning", "UNWEIGHTED_VERTS", f"{unweighted}/{len(ws)} vertices of '{m.name}' have no bone weight",
                "find_unweighted_vertices 定位后补权重", obj=m.name)
        unnormalized = sum(1 for w in ws if w and abs(sum(x[1] for x in w) - 1) > 1e-3)
        if unnormalized:
            add("warning", "UNNORMALIZED_WEIGHTS", f"{unnormalized} vertices of '{m.name}' have weights not summing to 1",
                "normalize_weights", obj=m.name)
        if any(abs(s - 1) > 1e-4 for s in m.scale):
            add("warning", "UNAPPLIED_SCALE", f"mesh '{m.name}' scale {tuple(round(s, 4) for s in m.scale)}",
                "apply_transforms", obj=m.name)
    for it in list_constraint_issues(arm.name):
        add("error" if it["code"] in ("TARGET_MISSING", "SUBTARGET_MISSING") else "info",
            "CONSTRAINT_" + it["code"], it["message"], it["fix_hint"], bone=it["bone"])
    summary = {"bones": len(bones), "deform_bones": len(deform), "meshes": [m.name for m in meshes],
               "errors": sum(1 for i in issues if i["severity"] == "error"),
               "warnings": sum(1 for i in issues if i["severity"] == "warning"),
               "infos": sum(1 for i in issues if i["severity"] == "info")}
    return {"armature": arm.name, "summary": summary, "issues": issues}


@command("check_bone_hierarchy", mutates=False)
def check_bone_hierarchy(armature: str):
    arm = find_armature(armature)

    def node(b):
        return {"name": b.name, "length": round(b.length, 6), "deform": b.use_deform, "children": [node(c) for c in b.children]}

    roots = [b for b in arm.data.bones if b.parent is None]
    return {"armature": arm.name, "bone_count": len(arm.data.bones), "roots": [node(b) for b in roots],
            "isolated": [b.name for b in roots if not b.children],
            "max_depth": max((_depth(b) for b in arm.data.bones), default=0)}


def _depth(b):
    d = 0
    while b.parent:
        b = b.parent
        d += 1
    return d


@command("check_bone_naming", mutates=False)
def check_bone_naming(armature: str, convention: str = "BLENDER"):
    arm = find_armature(armature)
    names = {b.name for b in arm.data.bones}
    missing, ok, unconventional = [], [], []
    for n in sorted(names):
        m = _mirror_name(n)
        if m is None:
            low = n.lower()
            if any(k in low for k in ("left", "right", "_l_", "_r_")):
                unconventional.append(n)
            continue
        (ok if m in names else missing).append({"bone": n, "expected_mirror": m})
    return {"armature": arm.name, "convention": convention.upper(), "paired": len(ok), "missing_mirror": missing,
            "unconventional": unconventional}


@command("find_unweighted_vertices", mutates=False)
def find_unweighted_vertices(object: str, threshold: float = 0.0001):
    o = find_object(object, "MESH")
    arm = _armature_of(o)
    names = {b.name for b in arm.data.bones if b.use_deform} if arm else None
    ws = _vertex_weights(o, names)
    idx = [i for i, w in enumerate(ws) if sum(x[1] for x in w) <= threshold]
    return {"object": o.name, "armature": arm.name if arm else None, "total": len(ws), "count": len(idx), "indices": idx[:500]}


@command("get_bone_influence", mutates=False)
def get_bone_influence(object: str, vertex_index: int):
    o = find_object(object, "MESH")
    if vertex_index < 0 or vertex_index >= len(o.data.vertices):
        raise ToolError(f"vertex index {vertex_index} out of range (0..{len(o.data.vertices) - 1})")
    ws = _vertex_weights(o)[vertex_index]
    return sorted([{"group": g, "weight": round(w, 6)} for g, w in ws], key=lambda d: -d["weight"])


@command("list_constraint_issues", mutates=False)
def list_constraint_issues(armature: str):
    arm = find_armature(armature)
    out = []
    for pb in arm.pose.bones:
        for c in pb.constraints:
            base = {"bone": pb.name, "constraint": c.name, "type": c.type}
            if hasattr(c, "target"):
                if c.target is None:
                    out.append({**base, "code": "TARGET_MISSING", "message": f"{pb.name}/{c.name} ({c.type}) has no target",
                                "fix_hint": "add_bone_constraint 时给 target"})
                    continue
                sub = getattr(c, "subtarget", "")
                if c.target.type == "ARMATURE" and sub and sub not in c.target.data.bones:
                    out.append({**base, "code": "SUBTARGET_MISSING", "message": f"{pb.name}/{c.name}: subtarget '{sub}' not in {c.target.name}",
                                "fix_hint": "改 subtarget 为存在的骨骼名"})
                    continue
            if c.type == "IK" and getattr(c, "chain_count", 0) > _depth(arm.data.bones[pb.name]) + 1 and c.chain_count != 0:
                out.append({**base, "code": "IK_CHAIN_TOO_LONG", "message": f"{pb.name}: chain_count {c.chain_count} exceeds parent depth",
                            "fix_hint": "减小 chain_count"})
            if c.mute:
                out.append({**base, "code": "MUTED", "message": f"{pb.name}/{c.name} is muted", "fix_hint": "确认是否有意禁用"})
            elif c.influence == 0:
                out.append({**base, "code": "ZERO_INFLUENCE", "message": f"{pb.name}/{c.name} influence is 0", "fix_hint": "设置 influence"})
    return out


@command("normalize_weights")
def normalize_weights(object: str, lock_active: bool = False, groups: list | None = None):
    o = find_object(object, "MESH")
    if not o.vertex_groups:
        raise ToolError(f"'{o.name}' has no vertex groups")
    by_name = {g.name: g for g in o.vertex_groups}
    if groups:
        for g in groups:
            if g not in by_name:
                raise ToolError(f"vertex group '{g}' not found. Available: {', '.join(by_name)}")
    active = o.vertex_groups.active.name if (lock_active and o.vertex_groups.active) else None
    changed = 0
    for i, ws in enumerate(_vertex_weights(o, set(groups) if groups else None)):
        if not ws:
            continue
        locked = sum(w for g, w in ws if g == active)
        rest = [(g, w) for g, w in ws if g != active]
        total = sum(w for _, w in rest)
        target = max(0.0, 1.0 - locked)
        if total <= 0 or abs(total - target) < 1e-6:
            continue
        for g, w in rest:
            by_name[g].add([i], w / total * target, "REPLACE")
        changed += 1
    return {"object": o.name, "vertices_changed": changed, "locked": active}
