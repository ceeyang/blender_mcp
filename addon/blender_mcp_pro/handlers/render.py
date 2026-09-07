"""Render（7）。"""
from __future__ import annotations

import base64
import glob
import os

import bpy

from ..registry import command
from ..utils import ToolError, abs_path, enum_check, no_viewport, serialize, set_props

_RENDER_DIR = os.path.join(os.path.expanduser("~"), ".cache", "blender-mcp-pro", "renders")


@command("get_render_settings", mutates=False)
def get_render_settings():
    sc = bpy.context.scene
    r = sc.render
    vs = sc.view_settings
    return serialize({
        "engine": r.engine, "resolution": [r.resolution_x, r.resolution_y], "percentage": r.resolution_percentage,
        "fps": r.fps, "frame_start": sc.frame_start, "frame_end": sc.frame_end,
        "file_format": r.image_settings.file_format, "color_mode": r.image_settings.color_mode,
        "output_path": r.filepath, "film_transparent": r.film_transparent, "motion_blur": r.use_motion_blur,
        "samples": {"eevee": sc.eevee.taa_render_samples, "cycles": sc.cycles.samples},
        "denoise": sc.cycles.use_denoising, "cycles_device": sc.cycles.device,
        "color_management": {"view_transform": vs.view_transform, "look": vs.look, "exposure": vs.exposure, "gamma": vs.gamma},
        "active_camera": sc.camera.name if sc.camera else None,
    })


@command("list_render_engines", mutates=False)
def list_render_engines():
    out = ["BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"]
    for cls in bpy.types.RenderEngine.__subclasses__():
        ident = getattr(cls, "bl_idname", None)
        if ident and ident not in out:
            out.append(ident)
    return out


@command("set_render_settings")
def set_render_settings(engine=None, resolution=None, percentage=None, samples=None, fps=None, file_format=None,
                        color_mode=None, output_path=None, film_transparent=None, motion_blur=None, denoise=None,
                        engine_settings: dict | None = None):
    sc = bpy.context.scene
    r = sc.render
    if engine is not None:
        r.engine = enum_check(engine, list_render_engines(), "engine")
    if resolution is not None:
        r.resolution_x, r.resolution_y = int(resolution[0]), int(resolution[1])
    if percentage is not None:
        r.resolution_percentage = int(percentage)
    if fps is not None:
        r.fps = int(fps)
    if file_format is not None:
        r.image_settings.file_format = file_format.upper()
    if color_mode is not None:
        r.image_settings.color_mode = color_mode.upper()
    if output_path is not None:
        r.filepath = abs_path(output_path) if not output_path.startswith("//") else output_path
    if film_transparent is not None:
        r.film_transparent = film_transparent
    if motion_blur is not None:
        r.use_motion_blur = motion_blur
    if denoise is not None:
        sc.cycles.use_denoising = denoise
    if samples is not None:
        if r.engine.startswith("BLENDER_EEVEE"):
            sc.eevee.taa_render_samples = int(samples)
        elif r.engine == "CYCLES":
            sc.cycles.samples = int(samples)
        else:
            sc.eevee.taa_render_samples = int(samples)
            sc.cycles.samples = int(samples)
    if engine_settings:
        target = sc.cycles if r.engine == "CYCLES" else sc.eevee
        set_props(target, engine_settings, tool_hint=f"{r.engine}: ")
    return get_render_settings()


@command("set_color_management")
def set_color_management(view_transform=None, look=None, exposure=None, gamma=None):
    vs = bpy.context.scene.view_settings
    for key, val in (("view_transform", view_transform), ("look", look)):
        if val is None:
            continue
        try:
            setattr(vs, key, val)
        except TypeError as e:
            opts = [e.identifier for e in vs.bl_rna.properties[key].enum_items]
            raise ToolError(f"invalid {key} '{val}'. Options: {', '.join(opts) or '(engine reports none in background mode)'}") from e
    if exposure is not None:
        vs.exposure = exposure
    if gamma is not None:
        vs.gamma = gamma
    return serialize({"view_transform": vs.view_transform, "look": vs.look, "exposure": vs.exposure, "gamma": vs.gamma})


def _preview_b64(path: str, max_size: int) -> str:
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        scale = min(1.0, max_size / max(w, h, 1))
        if scale < 1:
            img.scale(max(1, int(w * scale)), max(1, int(h * scale)))
        tmp = path + ".preview.png"
        img.filepath_raw = tmp
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)
    with open(tmp, "rb") as f:
        data = f.read()
    os.remove(tmp)
    return base64.b64encode(data).decode("ascii")


@command("render_image")
def render_image(output_path: str | None = None, frame: int | None = None, return_image: bool = True, max_preview_size: int = 512):
    sc = bpy.context.scene
    if sc.camera is None:
        raise ToolError("scene has no active camera; create_camera or set_active_camera first")
    if frame is not None:
        sc.frame_set(frame)
    r = sc.render
    if output_path:
        path = abs_path(output_path)
    else:
        os.makedirs(_RENDER_DIR, exist_ok=True)
        path = os.path.join(_RENDER_DIR, f"render_{sc.frame_current:04d}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prev_path, prev_fmt = r.filepath, r.image_settings.file_format
    ext = os.path.splitext(path)[1].lower()
    fmt_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR", ".tif": "TIFF", ".tiff": "TIFF", ".bmp": "BMP"}
    if ext in fmt_map:
        r.image_settings.file_format = fmt_map[ext]
    r.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        r.filepath, r.image_settings.file_format = prev_path, prev_fmt
    if not os.path.exists(path):
        raise ToolError(f"render finished but no file at {path}")
    out = {"path": path, "frame": sc.frame_current, "engine": r.engine,
           "resolution": [int(r.resolution_x * r.resolution_percentage / 100), int(r.resolution_y * r.resolution_percentage / 100)],
           "size_bytes": os.path.getsize(path)}
    if return_image:
        out["image_base64"] = _preview_b64(path, max_preview_size)
        out["mime"] = "image/png"
    return out


@command("render_animation")
def render_animation(output_path: str, frame_start: int | None = None, frame_end: int | None = None):
    sc = bpy.context.scene
    if sc.camera is None:
        raise ToolError("scene has no active camera")
    r = sc.render
    path = abs_path(output_path) if not output_path.startswith("//") else output_path
    os.makedirs(os.path.dirname(abs_path(path)) if not path.endswith(os.sep) else abs_path(path), exist_ok=True)
    prev = (r.filepath, sc.frame_start, sc.frame_end)
    r.filepath = path
    if frame_start is not None:
        sc.frame_start = frame_start
    if frame_end is not None:
        sc.frame_end = frame_end
    fs, fe = sc.frame_start, sc.frame_end
    try:
        bpy.ops.render.render(animation=True)
    finally:
        r.filepath, sc.frame_start, sc.frame_end = prev
    base = abs_path(path)
    pattern = base.replace("#", "?") if "#" in base else (base + "*")
    files = sorted(glob.glob(pattern))
    return {"output_path": base, "frames": [fs, fe], "count": fe - fs + 1, "files": files[:200]}


@command("viewport_screenshot")
def viewport_screenshot(output_path: str | None = None, return_image: bool = True):
    if bpy.app.background:
        no_viewport()
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                region = next((rg for rg in area.regions if rg.type == "WINDOW"), None)
                if region is None:
                    continue
                if output_path:
                    path = abs_path(output_path)
                else:
                    os.makedirs(_RENDER_DIR, exist_ok=True)
                    path = os.path.join(_RENDER_DIR, "viewport.png")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.screen.screenshot_area(filepath=path)
                out = {"path": path, "size_bytes": os.path.getsize(path)}
                if return_image:
                    out["image_base64"] = _preview_b64(path, 1024)
                    out["mime"] = "image/png"
                return out
    no_viewport()
