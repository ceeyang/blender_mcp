"""Scene & Objects。"""
from __future__ import annotations

from ..server import mcp
from ._base import call

Objects = list[str] | dict | str


@mcp.tool()
def get_scene_info() -> dict:
    """场景概况：名称、帧范围、fps、单位、活动物体/相机、选择、按类型计数、集合树。"""
    return call("get_scene_info")


@mcp.tool()
def list_objects(type: str | None = None, collection: str | None = None, pattern: str | None = None, selected: bool = False) -> list[dict]:
    """列出场景对象（可按类型 MESH/LIGHT/CAMERA…、集合、名字通配符、是否选中过滤）。"""
    return call("list_objects", type=type, collection=collection, pattern=pattern, selected=selected or None)


@mcp.tool()
def get_object_info(name: str) -> dict:
    """对象详情：变换、世界位置、父子、集合、修改器、约束、材质槽、网格统计、自定义属性。"""
    return call("get_object_info", name=name)


@mcp.tool()
def create_primitive(type: str, name: str | None = None, location: list[float] | None = None, rotation: list[float] | None = None,
                     scale: list[float] | None = None, size: float | None = None, radius: float | None = None,
                     depth: float | None = None, segments: int | None = None, text: str | None = None,
                     collection: str | None = None) -> dict:
    """新建基础物体。type: cube/plane/uv_sphere/ico_sphere/cylinder/cone/torus/circle/monkey/empty/text。
    size 用于 cube/plane/monkey；radius 用于球/柱/锥/环/圆；depth 用于柱/锥（torus 时为 minor_radius）；segments 为分段数。"""
    return call("create_primitive", type=type, name=name, location=location, rotation=rotation, scale=scale, size=size,
                radius=radius, depth=depth, segments=segments, text=text, collection=collection)


@mcp.tool()
def delete_object(objects: Objects, delete_children: bool = False) -> dict:
    """删除对象（名字列表或过滤器），可连带子物体。"""
    return call("delete_object", objects=objects, delete_children=delete_children)


@mcp.tool()
def duplicate_object(name: str, new_name: str | None = None, linked: bool = False, offset: list[float] | None = None) -> dict:
    """复制对象；linked=true 共享网格数据；offset 为位置偏移。"""
    return call("duplicate_object", name=name, new_name=new_name, linked=linked, offset=offset)


@mcp.tool()
def set_transform(name: str, location: list[float] | None = None, rotation: list[float] | None = None,
                  scale: list[float] | None = None, relative: bool = False) -> dict:
    """设置位置/旋转（弧度欧拉）/缩放；relative=true 时为增量（缩放为乘法）。"""
    return call("set_transform", name=name, location=location, rotation=rotation, scale=scale, relative=relative)


@mcp.tool()
def rename_object(name: str, new_name: str, rename_data: bool = True) -> dict:
    """重命名对象（默认连同其数据块）。"""
    return call("rename_object", name=name, new_name=new_name, rename_data=rename_data)


@mcp.tool()
def set_parent(child: str, parent: str | None = None, keep_transform: bool = True) -> dict:
    """设置父子关系；parent 省略即清除父级。keep_transform 保持世界变换。"""
    return call("set_parent", child=child, parent=parent, keep_transform=keep_transform)


@mcp.tool()
def set_visibility(objects: Objects, hide_viewport: bool | None = None, hide_render: bool | None = None,
                   hide_select: bool | None = None) -> dict:
    """设置视口/渲染/可选中的隐藏状态。"""
    return call("set_visibility", objects=objects, hide_viewport=hide_viewport, hide_render=hide_render, hide_select=hide_select)


@mcp.tool()
def select_objects(objects: Objects, mode: str = "replace", active: str | None = None) -> dict:
    """选择对象。mode: replace/add/remove；active 指定活动对象。"""
    return call("select_objects", objects=objects, mode=mode, active=active)


@mcp.tool()
def manage_collection(action: str, name: str, parent: str | None = None, objects: Objects | None = None,
                      new_name: str | None = None) -> dict:
    """集合管理。action: create/delete/move/link/unlink/rename。move 会把对象从其它集合移出。"""
    return call("manage_collection", action=action, name=name, parent=parent, objects=objects, new_name=new_name)


@mcp.tool()
def join_objects(objects: Objects, target: str | None = None) -> dict:
    """合并多个网格对象到 target（默认第一个）。"""
    return call("join_objects", objects=objects, target=target)


@mcp.tool()
def apply_transforms(objects: Objects, location: bool = True, rotation: bool = True, scale: bool = True) -> list[dict]:
    """应用变换到网格数据（Ctrl+A）。"""
    return call("apply_transforms", objects=objects, location=location, rotation=rotation, scale=scale)


@mcp.tool()
def set_origin(name: str, type: str = "GEOMETRY") -> dict:
    """设置原点。type: GEOMETRY/CURSOR/CENTER_OF_MASS/CENTER_OF_VOLUME/BOUNDS/GEOMETRY_TO_ORIGIN。"""
    return call("set_origin", name=name, type=type)


@mcp.tool()
def set_custom_property(name: str, key: str, value: float | int | str | bool | list | None = None) -> dict:
    """设置对象自定义属性；value 省略即删除该属性。"""
    return call("set_custom_property", name=name, key=key, value=value)
