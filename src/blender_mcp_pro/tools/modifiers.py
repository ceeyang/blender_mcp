"""Modifiers。"""
from __future__ import annotations

from ..server import mcp
from ._base import call


@mcp.tool()
def list_modifier_types(filter: str | None = None) -> list[dict]:
    """列出全部修改器类型及各自可设置的属性（名称/类型/枚举/默认值）。"""
    return call("list_modifier_types", filter=filter)


@mcp.tool()
def list_modifiers(object: str) -> list[dict]:
    """列出对象上的修改器栈。"""
    return call("list_modifiers", object=object)


@mcp.tool()
def get_modifier_settings(object: str, modifier: str) -> dict:
    """某修改器的当前值与可设置属性表。"""
    return call("get_modifier_settings", object=object, modifier=modifier)


@mcp.tool()
def add_modifier(object: str, type: str, name: str | None = None, settings: dict | None = None) -> dict:
    """添加修改器（SUBSURF/BEVEL/ARRAY/MIRROR/SOLIDIFY/BOOLEAN/…共 83 种）。settings 键为 bpy 属性名，对象引用直接给对象名。"""
    return call("add_modifier", object=object, type=type, name=name, settings=settings)


@mcp.tool()
def set_modifier(object: str, modifier: str, settings: dict) -> dict:
    """修改修改器属性。"""
    return call("set_modifier", object=object, modifier=modifier, settings=settings)


@mcp.tool()
def remove_modifier(object: str, modifier: str) -> dict:
    """删除修改器。"""
    return call("remove_modifier", object=object, modifier=modifier)


@mcp.tool()
def apply_modifier(object: str, modifier: str) -> dict:
    """应用修改器到网格。"""
    return call("apply_modifier", object=object, modifier=modifier)


@mcp.tool()
def move_modifier(object: str, modifier: str, index: int | None = None, direction: str | None = None) -> dict:
    """调整修改器顺序：给 index，或 direction UP/DOWN/TOP/BOTTOM。"""
    return call("move_modifier", object=object, modifier=modifier, index=index, direction=direction)
