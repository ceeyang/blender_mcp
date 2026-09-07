"""UV & Texture。"""
from __future__ import annotations

from ..server import mcp
from ._base import LONG, call


@mcp.tool()
def list_uv_maps(object: str) -> list[dict]:
    """列出网格的 UV 层。"""
    return call("list_uv_maps", object=object)


@mcp.tool()
def add_uv_map(object: str, name: str | None = None, set_active: bool = True) -> dict:
    """新增 UV 层。"""
    return call("add_uv_map", object=object, name=name, set_active=set_active)


@mcp.tool()
def remove_uv_map(object: str, name: str) -> dict:
    """删除 UV 层。"""
    return call("remove_uv_map", object=object, name=name)


@mcp.tool()
def unwrap_uv(object: str, method: str = "ANGLE_BASED", margin: float = 0.001, angle_limit: float | None = None,
              uv_map: str | None = None) -> dict:
    """UV 展开。method: ANGLE_BASED/CONFORMAL/MINIMUM_STRETCH/SMART_PROJECT/CUBE/CYLINDER/SPHERE/LIGHTMAP。"""
    return call("unwrap_uv", object=object, method=method, margin=margin, angle_limit=angle_limit, uv_map=uv_map)


@mcp.tool()
def pack_uv_islands(object: str, margin: float = 0.001, rotate: bool = True) -> dict:
    """打包 UV 岛。"""
    return call("pack_uv_islands", object=object, margin=margin, rotate=rotate)


@mcp.tool()
def mark_seams(object: str, edges: list[int] | None = None, from_sharp: bool = False, clear: bool = False) -> dict:
    """标记缝合边：按边索引，或从锐边生成；clear 先清空。"""
    return call("mark_seams", object=object, edges=edges, from_sharp=from_sharp, clear=clear)


@mcp.tool()
def create_image(name: str, width: int = 1024, height: int = 1024, color: list[float] | None = None, alpha: bool = True,
                 float_buffer: bool = False) -> dict:
    """新建空白图像。"""
    return call("create_image", name=name, width=width, height=height, color=color, alpha=alpha, float_buffer=float_buffer)


@mcp.tool()
def bake_texture(object: str, bake_type: str, image: str | None = None, size: int = 1024, output_path: str | None = None,
                 margin: int = 16, selected_to_active: bool = False, cage_extrusion: float = 0.0, samples: int = 16) -> dict:
    """Cycles 烘焙到贴图。bake_type: DIFFUSE/NORMAL/AO/ROUGHNESS/EMIT/COMBINED/…；无 UV 自动 smart project；output_path 保存 PNG。"""
    return call("bake_texture", timeout=LONG, object=object, bake_type=bake_type, image=image, size=size, output_path=output_path,
                margin=margin, selected_to_active=selected_to_active, cage_extrusion=cage_extrusion, samples=samples)


@mcp.tool()
def save_image(image: str, path: str, format: str | None = None) -> dict:
    """把 Blender 内的图像保存到磁盘。"""
    return call("save_image", image=image, path=path, format=format)


@mcp.tool()
def list_images() -> list[dict]:
    """列出图像数据块。"""
    return call("list_images")
