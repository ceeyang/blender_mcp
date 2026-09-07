"""Render。"""
from __future__ import annotations

from mcp.server.mcpserver import Image

from ..server import mcp
from ._base import LONG, call, image_result


@mcp.tool()
def get_render_settings() -> dict:
    """当前渲染设置（引擎、分辨率、采样、输出、色彩管理）。"""
    return call("get_render_settings")


@mcp.tool()
def list_render_engines() -> list[str]:
    """可用渲染引擎。"""
    return call("list_render_engines")


@mcp.tool()
def set_render_settings(engine: str | None = None, resolution: list[int] | None = None, percentage: int | None = None,
                        samples: int | None = None, fps: int | None = None, file_format: str | None = None, color_mode: str | None = None,
                        output_path: str | None = None, film_transparent: bool | None = None, motion_blur: bool | None = None,
                        denoise: bool | None = None, engine_settings: dict | None = None) -> dict:
    """渲染设置。engine: BLENDER_EEVEE/CYCLES/BLENDER_WORKBENCH；engine_settings 透传到 scene.eevee / scene.cycles 属性。"""
    return call("set_render_settings", engine=engine, resolution=resolution, percentage=percentage, samples=samples, fps=fps,
                file_format=file_format, color_mode=color_mode, output_path=output_path, film_transparent=film_transparent,
                motion_blur=motion_blur, denoise=denoise, engine_settings=engine_settings)


@mcp.tool()
def set_color_management(view_transform: str | None = None, look: str | None = None, exposure: float | None = None,
                         gamma: float | None = None) -> dict:
    """色彩管理：view_transform (AgX/Filmic/Standard…)、look、曝光、gamma。"""
    return call("set_color_management", view_transform=view_transform, look=look, exposure=exposure, gamma=gamma)


@mcp.tool()
def render_image(output_path: str | None = None, frame: int | None = None, return_image: bool = True,
                 max_preview_size: int = 512) -> Image | dict:
    """渲染当前帧到文件（默认 ~/.cache/blender-mcp-pro/renders/），return_image 时回传缩略图。"""
    return image_result(call("render_image", timeout=LONG, output_path=output_path, frame=frame, return_image=return_image,
                             max_preview_size=max_preview_size))


@mcp.tool()
def render_animation(output_path: str, frame_start: int | None = None, frame_end: int | None = None) -> dict:
    """渲染帧序列。output_path 可含 #### 帧号占位（如 /tmp/out/frame_####.png）。"""
    return call("render_animation", timeout=LONG, output_path=output_path, frame_start=frame_start, frame_end=frame_end)


@mcp.tool()
def viewport_screenshot(output_path: str | None = None, return_image: bool = True) -> Image | dict:
    """截取 3D 视口（需要 Blender GUI）。"""
    return image_result(call("viewport_screenshot", output_path=output_path, return_image=return_image))
