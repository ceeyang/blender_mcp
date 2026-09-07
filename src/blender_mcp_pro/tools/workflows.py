"""Workflows。"""
from __future__ import annotations

from mcp.server.mcpserver import Image

from ..server import mcp
from ._base import LONG, call, image_result

Objects = list[str] | dict | str


@mcp.tool()
def setup_three_point_lighting(target: str, distance: float = 6.0, height: float = 3.0, key_energy: float = 1000.0,
                               fill_ratio: float = 0.4, rim_ratio: float = 0.8, color_temp: float | None = None) -> dict:
    """围绕目标布 Key/Fill/Rim 三盏面光并对准它；color_temp 为开尔文色温。"""
    return call("setup_three_point_lighting", target=target, distance=distance, height=height, key_energy=key_energy,
                fill_ratio=fill_ratio, rim_ratio=rim_ratio, color_temp=color_temp)


@mcp.tool()
def setup_studio_scene(subject: str | None = None, backdrop: bool = True, ground: bool = True, hdri_path: str | None = None,
                       camera: bool = True) -> dict:
    """一键摄影棚：弧形背景板（或地面）、世界光/HDRI、三点光、相机取景。"""
    return call("setup_studio_scene", subject=subject, backdrop=backdrop, ground=ground, hdri_path=hdri_path, camera=camera)


@mcp.tool()
def turntable_animation(object: str, frames: int = 120, revolutions: float = 1.0, camera: str | None = None) -> dict:
    """给对象做旋转展示动画（父级空物体绕 Z 线性旋转 + 循环），并让相机取景。"""
    return call("turntable_animation", object=object, frames=frames, revolutions=revolutions, camera=camera)


@mcp.tool()
def quick_product_render(object: str, output_path: str, resolution: list[int] | None = None, samples: int = 64,
                         engine: str = "BLENDER_EEVEE") -> Image | dict:
    """三点光 + 相机取景 + 透明背景，一步渲染产品图。"""
    return image_result(call("quick_product_render", timeout=LONG, object=object, output_path=output_path, resolution=resolution,
                             samples=samples, engine=engine))


@mcp.tool()
def material_from_texture_folder(folder: str, name: str | None = None, assign_to: str | None = None) -> dict:
    """扫描文件夹，按文件名识别 basecolor/roughness/metallic/normal/height/ao 贴图并建 PBR 材质。"""
    return call("material_from_texture_folder", folder=folder, name=name, assign_to=assign_to)


@mcp.tool()
def scatter_objects(source: str, surface: str, count: int = 100, seed: int = 0, scale_range: list[float] | None = None,
                    align_to_normal: bool = True, method: str = "GEOMETRY_NODES") -> dict:
    """把 source 散布到 surface 表面。method: GEOMETRY_NODES（非破坏实例）或 COPIES（真实副本）。"""
    return call("scatter_objects", timeout=LONG, source=source, surface=surface, count=count, seed=seed, scale_range=scale_range,
                align_to_normal=align_to_normal, method=method)


@mcp.tool()
def export_for_game(objects: Objects, path: str, format: str = "GLB", apply_modifiers: bool = True, triangulate: bool = True,
                    scale: float = 1.0, forward: str = "-Z", up: str = "Y") -> dict:
    """游戏资产导出：复制→应用修改器→三角化→缩放→导出 GLB/GLTF/FBX/OBJ，原对象不动。"""
    return call("export_for_game", timeout=LONG, objects=objects, path=path, format=format, apply_modifiers=apply_modifiers,
                triangulate=triangulate, scale=scale, forward=forward, up=up)
