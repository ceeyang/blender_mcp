"""Scene Utilities。"""
from __future__ import annotations

from ..server import mcp
from ._base import call

Objects = list[str] | dict | str


@mcp.tool()
def execute_code(code: str, return_var: str | None = None) -> dict:
    """在 Blender 里执行任意 Python（预置 bpy/bmesh/mathutils/Vector/math）。返回 stdout；return_var 指定要取回的变量名。"""
    return call("execute_code", timeout=300.0, code=code, return_var=return_var)


@mcp.tool()
def get_blender_info() -> dict:
    """Blender 版本、Python、当前文件、已启用插件、server 状态、Sketchfab token 是否已配置。"""
    return call("get_blender_info")


@mcp.tool()
def get_api_docs(path: str) -> dict:
    """本地查 bpy API 文档。path 形如 bpy.types.Object / bpy.types.Object.location / bpy.ops.mesh.primitive_cube_add。"""
    return call("get_api_docs", path=path)


@mcp.tool()
def undo() -> dict:
    """撤销上一步（Ctrl+Z）。"""
    return call("undo")


@mcp.tool()
def redo() -> dict:
    """重做（Ctrl+Shift+Z）。"""
    return call("redo")


@mcp.tool()
def purge_orphans() -> dict:
    """清理无用户的孤儿数据块（材质、网格、图片…）。"""
    return call("purge_orphans")


@mcp.tool()
def set_units(system: str | None = None, scale_length: float | None = None, length_unit: str | None = None,
              rotation_unit: str | None = None) -> dict:
    """场景单位。system: METRIC/IMPERIAL/NONE；length_unit 如 METERS/CENTIMETERS；rotation_unit: DEGREES/RADIANS。"""
    return call("set_units", system=system, scale_length=scale_length, length_unit=length_unit, rotation_unit=rotation_unit)


@mcp.tool()
def set_cursor(location: list[float] | None = None, rotation: list[float] | None = None) -> dict:
    """设置 3D 游标位置/旋转。"""
    return call("set_cursor", location=location, rotation=rotation)


@mcp.tool()
def measure_distance(a: str | list[float], b: str | list[float]) -> dict:
    """两点距离；a/b 可为对象名或 [x,y,z]。"""
    return call("measure_distance", a=a, b=b)


@mcp.tool()
def get_bounding_box(objects: Objects, world: bool = True) -> dict:
    """合并包围盒：min/max/center/size。"""
    return call("get_bounding_box", objects=objects, world=world)


@mcp.tool()
def ray_cast(origin: list[float], direction: list[float], distance: float = 1000.0) -> dict:
    """从 origin 沿 direction 发射线，返回命中对象/位置/法线/面索引。"""
    return call("ray_cast", origin=origin, direction=direction, distance=distance)


@mcp.tool()
def check_mesh(name: str) -> dict:
    """网格体检：顶点/边/面、三角/四边/ngon、非流形边、松散点、重复顶点。"""
    return call("check_mesh", name=name)


@mcp.tool()
def mesh_cleanup(name: str, recalc_normals: bool = False, inside: bool = False, merge_by_distance: bool = False,
                 threshold: float = 0.0001, shade_smooth: bool | None = None, auto_smooth_angle: float | None = None,
                 dissolve_degenerate: bool = False) -> dict:
    """网格清理：重算法线、按距离合并顶点、溶解退化、平滑着色、按角度自动平滑（弧度）。"""
    return call("mesh_cleanup", name=name, recalc_normals=recalc_normals, inside=inside, merge_by_distance=merge_by_distance,
                threshold=threshold, shade_smooth=shade_smooth, auto_smooth_angle=auto_smooth_angle,
                dissolve_degenerate=dissolve_degenerate)
