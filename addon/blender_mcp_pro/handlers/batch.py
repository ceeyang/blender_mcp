"""Batch Processing（8）。"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from ..registry import command
from ..utils import ToolError, enum_check, obj_brief, resolve_objects, serialize, vec
from .animation import _set_path
from .materials import assign_material
from .modifiers import add_modifier
from .scene import delete_object


@command("batch_transform")
def batch_transform(objects, location=None, rotation=None, scale=None, relative: bool = True):
    objs = resolve_objects(objects)
    for o in objs:
        if location is not None:
            o.location = (o.location + Vector(location)) if relative else Vector(location)
        if rotation is not None:
            o.rotation_euler = [a + b for a, b in zip(o.rotation_euler, rotation)] if relative else rotation
        if scale is not None:
            o.scale = [a * b for a, b in zip(o.scale, scale)] if relative else scale
    return {"count": len(objs), "objects": [obj_brief(o) for o in objs]}


@command("batch_rename")
def batch_rename(objects, prefix: str | None = None, suffix: str | None = None, find: str | None = None,
                 replace: str | None = None, numbering: bool = False):
    objs = resolve_objects(objects)
    mapping = {}
    for i, o in enumerate(objs):
        new = o.name
        if find:
            new = new.replace(find, replace or "")
        if prefix:
            new = prefix + new
        if suffix:
            new = new + suffix
        if numbering:
            new = f"{new}_{i + 1:03d}"
        old = o.name
        o.name = new
        if o.data is not None and o.data.users == 1:
            o.data.name = o.name
        mapping[old] = o.name
    return {"count": len(objs), "renamed": mapping}


@command("batch_apply_material")
def batch_apply_material(objects, material: str):
    objs = resolve_objects(objects)
    done, skipped = [], []
    for o in objs:
        if o.data is not None and hasattr(o.data, "materials"):
            assign_material(o.name, material)
            done.append(o.name)
        else:
            skipped.append(o.name)
    return {"material": material, "applied": done, "skipped": skipped}


@command("batch_add_modifier")
def batch_add_modifier(objects, type: str, settings: dict | None = None):
    objs = resolve_objects(objects)
    added = [add_modifier(o.name, type, None, settings)["name"] for o in objs]
    return {"count": len(objs), "modifier_type": type.upper(), "added": dict(zip([o.name for o in objs], added))}


@command("batch_set_property")
def batch_set_property(objects, data_path: str, value):
    objs = resolve_objects(objects)
    for o in objs:
        try:
            _set_path(o, data_path, value)
        except (AttributeError, ValueError, TypeError) as e:
            raise ToolError(f"cannot set '{data_path}' on '{o.name}': {e}") from e
    return {"count": len(objs), "data_path": data_path, "value": serialize(value), "objects": [o.name for o in objs]}


@command("batch_delete")
def batch_delete(objects):
    return delete_object(objects)


@command("distribute_objects")
def distribute_objects(objects, mode: str = "LINE", spacing: float = 2.0, axis: str | None = None, columns: int = 5,
                       radius: float = 5.0, center=None):
    objs = resolve_objects(objects)
    m = enum_check(mode, ["LINE", "GRID", "CIRCLE"], "mode")
    if axis is None:
        axis = "Z" if m == "CIRCLE" else "X"
    ax = "XYZ".index(enum_check(axis, ["X", "Y", "Z"], "axis"))
    c = Vector(center) if center is not None else Vector((0, 0, 0))
    n = len(objs)
    positions = []
    for i, o in enumerate(objs):
        pos = c.copy()
        if m == "LINE":
            pos[ax] += i * spacing - (n - 1) * spacing / 2
        elif m == "GRID":
            cols = max(1, int(columns))
            rows = math.ceil(n / cols)
            a1, a2 = ax, (ax + 1) % 3  # 列沿 axis，行沿下一轴
            pos[a1] += (i % cols) * spacing - (cols - 1) * spacing / 2
            pos[a2] += (i // cols) * spacing - (rows - 1) * spacing / 2
        else:
            ang = 2 * math.pi * i / n
            a1, a2 = [k for k in range(3) if k != ax][:2]
            pos[a1] += radius * math.cos(ang)
            pos[a2] += radius * math.sin(ang)
        o.location = pos
        positions.append({"name": o.name, "location": vec(pos)})
    return {"mode": m, "count": n, "positions": positions}


@command("randomize_transform")
def randomize_transform(objects, location=None, rotation=None, scale=None, uniform_scale: bool = True, seed: int = 0):
    objs = resolve_objects(objects)
    rng = random.Random(seed)
    for o in objs:
        if location:
            o.location = o.location + Vector([rng.uniform(-r, r) for r in location])
        if rotation:
            o.rotation_euler = [a + rng.uniform(-r, r) for a, r in zip(o.rotation_euler, rotation)]
        if scale:
            if uniform_scale:
                f = 1 + rng.uniform(-scale[0], scale[0])
                o.scale = [s * f for s in o.scale]
            else:
                o.scale = [s * (1 + rng.uniform(-r, r)) for s, r in zip(o.scale, scale)]
    return {"seed": seed, "count": len(objs), "objects": [obj_brief(o) for o in objs]}
