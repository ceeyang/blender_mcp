"""Lights。"""
from __future__ import annotations

from ..server import mcp
from ._base import call


@mcp.tool()
def list_lights() -> list[dict]:
    """列出灯光及参数。"""
    return call("list_lights")


@mcp.tool()
def get_light_info(name: str) -> dict:
    """灯光详情。"""
    return call("get_light_info", name=name)


@mcp.tool()
def create_light(type: str, name: str | None = None, location: list[float] | None = None, rotation: list[float] | None = None,
                 energy: float | None = None, color: list[float] | None = None, radius: float | None = None, size: float | None = None,
                 spot_size: float | None = None, spot_blend: float | None = None, target: str | list[float] | None = None) -> dict:
    """新建灯光。type: POINT/SUN/SPOT/AREA；energy 瓦；radius 软阴影半径；size 面光尺寸；spot_size 弧度；target 指向对象或坐标。"""
    return call("create_light", type=type, name=name, location=location, rotation=rotation, energy=energy, color=color,
                radius=radius, size=size, spot_size=spot_size, spot_blend=spot_blend, target=target)


@mcp.tool()
def set_light(name: str, energy: float | None = None, color: list[float] | None = None, radius: float | None = None,
              size: float | None = None, shape: str | None = None, spot_size: float | None = None, spot_blend: float | None = None,
              use_shadow: bool | None = None, angle: float | None = None) -> dict:
    """修改灯光参数。shape 用于面光 SQUARE/RECTANGLE/DISK/ELLIPSE；angle 用于太阳光。"""
    return call("set_light", name=name, energy=energy, color=color, radius=radius, size=size, shape=shape, spot_size=spot_size,
                spot_blend=spot_blend, use_shadow=use_shadow, angle=angle)


@mcp.tool()
def point_light_at(light: str, target: str | list[float], use_constraint: bool = False) -> dict:
    """让灯光指向对象或坐标；use_constraint 用 Track To 约束持续跟随。"""
    return call("point_light_at", light=light, target=target, use_constraint=use_constraint)


@mcp.tool()
def set_world_lighting(color: list[float] | None = None, strength: float | None = None, hdri_path: str | None = None,
                       rotation: list[float] | None = None) -> dict:
    """世界光：背景颜色/强度，或加载 HDRI（rotation 为 Mapping 旋转弧度）。"""
    return call("set_world_lighting", color=color, strength=strength, hdri_path=hdri_path, rotation=rotation)
