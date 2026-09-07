"""Modifiers（8）。"""
from __future__ import annotations

import bpy

from ..registry import command
from ..utils import ToolError, enum_check, find_object, rna_props, select_only, serialize, set_props

_TYPES_CACHE: list[dict] | None = None
_BASE_PROPS: set[str] | None = None


def _mod_enum():
    return [(e.identifier, e.name, e.description)
            for e in bpy.types.ObjectModifiers.bl_rna.functions["new"].parameters["type"].enum_items]


def _base_props() -> set[str]:
    global _BASE_PROPS
    if _BASE_PROPS is None:
        _BASE_PROPS = {p.identifier for p in bpy.types.Modifier.bl_rna.properties}
    return _BASE_PROPS


def _settings_table(mod) -> dict:
    base = _base_props()
    return {k: v for k, v in rna_props(mod).items() if k not in base}


def _find_mod(o, name: str):
    m = o.modifiers.get(name)
    if m is None:
        raise ToolError(f"modifier '{name}' not found on '{o.name}'. Available: {', '.join(x.name for x in o.modifiers)}")
    return m


def mod_info(o, m) -> dict:
    base = _base_props()
    values = {}
    for p in m.bl_rna.properties:
        if p.identifier in base or p.is_readonly:
            continue
        try:
            values[p.identifier] = serialize(getattr(m, p.identifier))
        except Exception:  # noqa: BLE001
            pass
    return {"object": o.name, "name": m.name, "type": m.type, "index": list(o.modifiers).index(m),
            "show_viewport": m.show_viewport, "show_render": m.show_render, "settings": values}


@command("list_modifier_types", mutates=False)
def list_modifier_types(filter: str | None = None):
    global _TYPES_CACHE
    if _TYPES_CACHE is None:
        me = bpy.data.meshes.new("__mcp_probe")
        o = bpy.data.objects.new("__mcp_probe", me)
        out = []
        for ident, name, desc in _mod_enum():
            entry = {"type": ident, "name": name, "description": desc}
            try:
                m = o.modifiers.new("probe", ident)
                if m is None:
                    raise RuntimeError("not applicable to mesh")
                entry["settings"] = _settings_table(m)
                o.modifiers.remove(m)
            except RuntimeError as e:
                entry["settings"] = {}
                entry["note"] = f"cannot add to a mesh object: {e}"
            out.append(entry)
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
        _TYPES_CACHE = out
    res = _TYPES_CACHE
    if filter:
        f = filter.lower()
        res = [t for t in res if f in t["type"].lower() or f in t["name"].lower()]
    return res


@command("list_modifiers", mutates=False)
def list_modifiers(object: str):
    o = find_object(object)
    return [{"name": m.name, "type": m.type, "index": i, "show_viewport": m.show_viewport, "show_render": m.show_render}
            for i, m in enumerate(o.modifiers)]


@command("get_modifier_settings", mutates=False)
def get_modifier_settings(object: str, modifier: str):
    o = find_object(object)
    m = _find_mod(o, modifier)
    d = mod_info(o, m)
    d["available"] = _settings_table(m)
    return d


@command("add_modifier")
def add_modifier(object: str, type: str, name: str | None = None, settings: dict | None = None):
    o = find_object(object)
    idents = [e[0] for e in _mod_enum()]
    t = enum_check(type, idents, "type")
    m = o.modifiers.new(name or t.title().replace("_", " "), t)
    if m is None:
        raise ToolError(f"modifier type {t} cannot be added to a {o.type} object")
    set_props(m, settings, tool_hint=f"{t}: ")
    return mod_info(o, m)


@command("set_modifier")
def set_modifier(object: str, modifier: str, settings: dict):
    o = find_object(object)
    m = _find_mod(o, modifier)
    changed = set_props(m, settings, tool_hint=f"{m.type}: ")
    d = mod_info(o, m)
    d["changed"] = changed
    return d


@command("remove_modifier")
def remove_modifier(object: str, modifier: str):
    o = find_object(object)
    m = _find_mod(o, modifier)
    name = m.name
    o.modifiers.remove(m)
    return {"object": o.name, "removed": name, "modifiers": [x.name for x in o.modifiers]}


@command("apply_modifier")
def apply_modifier(object: str, modifier: str):
    o = find_object(object)
    m = _find_mod(o, modifier)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    select_only([o], o)
    name = m.name
    bpy.ops.object.modifier_apply(modifier=name)
    d = {"object": o.name, "applied": name, "modifiers": [x.name for x in o.modifiers]}
    if o.type == "MESH":
        d["vertices"] = len(o.data.vertices)
        d["faces"] = len(o.data.polygons)
    return d


@command("move_modifier")
def move_modifier(object: str, modifier: str, index: int | None = None, direction: str | None = None):
    o = find_object(object)
    m = _find_mod(o, modifier)
    cur = list(o.modifiers).index(m)
    n = len(o.modifiers)
    if index is None:
        d = enum_check(direction or "", ["UP", "DOWN", "TOP", "BOTTOM"], "direction")
        index = {"UP": cur - 1, "DOWN": cur + 1, "TOP": 0, "BOTTOM": n - 1}[d]
    index = max(0, min(n - 1, index))
    select_only([o], o)
    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=index)
    return {"object": o.name, "modifier": m.name, "index": list(o.modifiers).index(m),
            "order": [x.name for x in o.modifiers]}
