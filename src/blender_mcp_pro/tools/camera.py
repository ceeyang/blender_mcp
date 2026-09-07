"""Camera。"""
from __future__ import annotations

from ..server import mcp
from ._base import call


@mcp.tool()
def list_cameras() -> list[dict]:
    """列出相机。"""
    return call("list_cameras")


@mcp.tool()
def get_camera_info(name: str) -> dict:
    """相机详情（镜头、类型、裁剪、DOF、是否活动）。"""
    return call("get_camera_info", name=name)


@mcp.tool()
def create_camera(name: str | None = None, location: list[float] | None = None, rotation: list[float] | None = None,
                  lens: float | None = None, type: str | None = None, sensor_width: float | None = None,
                  clip_start: float | None = None, clip_end: float | None = None, set_active: bool = True) -> dict:
    """新建相机。type: PERSP/ORTHO；lens 焦距 mm。"""
    return call("create_camera", name=name, location=location, rotation=rotation, lens=lens, type=type, sensor_width=sensor_width,
                clip_start=clip_start, clip_end=clip_end, set_active=set_active)


@mcp.tool()
def set_camera(name: str, lens: float | None = None, type: str | None = None, ortho_scale: float | None = None,
               clip_start: float | None = None, clip_end: float | None = None, shift_x: float | None = None,
               shift_y: float | None = None, dof: dict | None = None) -> dict:
    """修改相机参数。dof: {enabled, focus_object, focus_distance, fstop}。"""
    return call("set_camera", name=name, lens=lens, type=type, ortho_scale=ortho_scale, clip_start=clip_start, clip_end=clip_end,
                shift_x=shift_x, shift_y=shift_y, dof=dof)


@mcp.tool()
def set_active_camera(name: str) -> dict:
    """设为场景活动相机。"""
    return call("set_active_camera", name=name)


@mcp.tool()
def point_camera_at(camera: str, target: str | list[float], use_constraint: bool = False) -> dict:
    """相机朝向对象或坐标；use_constraint 用 Track To 持续跟随。"""
    return call("point_camera_at", camera=camera, target=target, use_constraint=use_constraint)


@mcp.tool()
def frame_objects(camera: str, objects: list[str] | dict | str, margin: float = 1.1) -> dict:
    """沿相机当前朝向后退到能框住这些对象的距离并对准它们。"""
    return call("frame_objects", camera=camera, objects=objects, margin=margin)
