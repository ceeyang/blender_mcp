"""Batch Processing。"""
from __future__ import annotations

from ..server import mcp
from ._base import call

Objects = list[str] | dict | str


@mcp.tool()
def batch_transform(objects: Objects, location: list[float] | None = None, rotation: list[float] | None = None,
                    scale: list[float] | None = None, relative: bool = True) -> dict:
    """批量变换（默认增量）。"""
    return call("batch_transform", objects=objects, location=location, rotation=rotation, scale=scale, relative=relative)


@mcp.tool()
def batch_rename(objects: Objects, prefix: str | None = None, suffix: str | None = None, find: str | None = None,
                 replace: str | None = None, numbering: bool = False) -> dict:
    """批量重命名：前缀/后缀/查找替换/编号。"""
    return call("batch_rename", objects=objects, prefix=prefix, suffix=suffix, find=find, replace=replace, numbering=numbering)


@mcp.tool()
def batch_apply_material(objects: Objects, material: str) -> dict:
    """批量赋材质。"""
    return call("batch_apply_material", objects=objects, material=material)


@mcp.tool()
def batch_add_modifier(objects: Objects, type: str, settings: dict | None = None) -> dict:
    """批量加修改器。"""
    return call("batch_add_modifier", objects=objects, type=type, settings=settings)


@mcp.tool()
def batch_set_property(objects: Objects, data_path: str, value: float | int | bool | str | list | None) -> dict:
    """批量设置任意属性路径（如 hide_render、data.use_auto_smooth、modifiers['Bevel'].width）。"""
    return call("batch_set_property", objects=objects, data_path=data_path, value=value)


@mcp.tool()
def batch_delete(objects: Objects) -> dict:
    """批量删除。"""
    return call("batch_delete", objects=objects)


@mcp.tool()
def distribute_objects(objects: Objects, mode: str = "LINE", spacing: float = 2.0, axis: str | None = None, columns: int = 5,
                       radius: float = 5.0, center: list[float] | None = None) -> dict:
    """排列对象：LINE 沿 axis(默认 X) 等距；GRID 列沿 axis、行沿下一轴，columns 列；CIRCLE 以 axis(默认 Z) 为法线、半径 radius。"""
    return call("distribute_objects", objects=objects, mode=mode, spacing=spacing, axis=axis, columns=columns, radius=radius, center=center)


@mcp.tool()
def randomize_transform(objects: Objects, location: list[float] | None = None, rotation: list[float] | None = None,
                        scale: list[float] | None = None, uniform_scale: bool = True, seed: int = 0) -> dict:
    """随机化变换，各参数为 ± 范围；同 seed 结果可复现。"""
    return call("randomize_transform", objects=objects, location=location, rotation=rotation, scale=scale, uniform_scale=uniform_scale, seed=seed)
