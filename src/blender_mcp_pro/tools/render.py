"""Render — engine settings, colour management, stills, sequences and viewport grabs."""
from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import Image
from pydantic import Field

from ..server import mcp
from ._base import LONG, call, image_result
from ._types import READ_ONLY, UPDATE, WRITES_FILE


@mcp.tool(annotations=READ_ONLY)
def get_render_settings() -> dict:
    """Read the current render configuration: engine, resolution and percentage, fps, frame range, output path and format, samples for both EEVEE and Cycles, denoising, colour management and the active camera.

    Worth checking before a render — the returned `samples` shows both engines' values, so
    you can see which one actually applies to the engine in use.
    """
    return call("get_render_settings")


@mcp.tool(annotations=READ_ONLY)
def list_render_engines() -> list[str]:
    """List the render engines available in this Blender build, including any from add-ons.

    Usually BLENDER_EEVEE (fast, real-time), CYCLES (path-traced, slow but physically
    accurate) and BLENDER_WORKBENCH (flat preview shading, fastest of all).
    """
    return call("list_render_engines")


@mcp.tool(annotations=UPDATE)
def set_render_settings(
    engine: Annotated[str | None, Field(description="BLENDER_EEVEE (fast raster, seconds), CYCLES (path tracing, minutes, needed for true caustics and accurate GI) or BLENDER_WORKBENCH (flat shading, near-instant, ignores materials and lights).")] = None,
    resolution: Annotated[list[int] | None, Field(description="Output size in pixels as [width, height], e.g. [1920, 1080]. Multiplied by `percentage`.")] = None,
    percentage: Annotated[int | None, Field(description="Scale factor on resolution, 1-100. Set 50 for quick previews at half size without changing the real resolution.")] = None,
    samples: Annotated[int | None, Field(description="Anti-aliasing / path samples. Routed to the active engine: EEVEE 16-64 is usually plenty, Cycles needs 128+ for clean output (with denoising, 32-64 can do). More samples means proportionally longer renders.")] = None,
    fps: Annotated[int | None, Field(description="Frames per second for animation output.")] = None,
    file_format: Annotated[str | None, Field(description="PNG (default, lossless with alpha), JPEG, OPEN_EXR (32-bit float, for compositing), TIFF, WEBP, or FFMPEG for video.")] = None,
    color_mode: Annotated[str | None, Field(description="BW, RGB, or RGBA to keep an alpha channel (pair with film_transparent=true for cut-outs).")] = None,
    output_path: Annotated[str | None, Field(description="Default output directory or file prefix used by render_animation. render_image takes its own path argument.")] = None,
    film_transparent: Annotated[bool | None, Field(description="true renders the world/background as transparent instead of sky, giving an alpha channel. Needs color_mode='RGBA' and a format that stores alpha.")] = None,
    motion_blur: Annotated[bool | None, Field(description="true blurs fast-moving objects across the shutter interval. Costs render time and only matters for animation.")] = None,
    denoise: Annotated[bool | None, Field(description="true runs a denoiser over the result. Essentially required for Cycles at low sample counts.")] = None,
    engine_settings: Annotated[dict | None, Field(description="Engine-specific properties passed straight through to scene.eevee or scene.cycles, e.g. {'use_raytracing': true} or {'max_bounces': 8}. Use get_api_docs('bpy.types.SceneEEVEE') or ('bpy.types.CyclesRenderSettings') for the names.")] = None,
) -> dict:
    """Configure the renderer: engine, resolution, sampling, output format and quality options.

    Only the arguments you pass change. Set the engine first when changing several things,
    since `samples` and `engine_settings` are routed to whichever engine is active. For a
    quick look use BLENDER_WORKBENCH or low `percentage`; save CYCLES for final output.
    """
    return call("set_render_settings", engine=engine, resolution=resolution, percentage=percentage, samples=samples,
                fps=fps, file_format=file_format, color_mode=color_mode, output_path=output_path,
                film_transparent=film_transparent, motion_blur=motion_blur, denoise=denoise,
                engine_settings=engine_settings)


@mcp.tool(annotations=UPDATE)
def set_color_management(
    view_transform: Annotated[str | None, Field(description="Tone mapping applied to the render: 'AgX' (Blender 4+ default, rolls off highlights, desaturates bright areas), 'Filmic' (older cinematic look), 'Standard' (none — colours come out exactly as authored), 'Khronos PBR Neutral'.")] = None,
    look: Annotated[str | None, Field(description="Contrast preset layered on the view transform, e.g. 'None', 'AgX - Punchy', 'AgX - Medium High Contrast'.")] = None,
    exposure: Annotated[float | None, Field(description="Exposure in stops: +1 doubles brightness, -1 halves it. Faster to adjust than every light in the scene.")] = None,
    gamma: Annotated[float | None, Field(description="Gamma correction, 1.0 being neutral.")] = None,
) -> dict:
    """Set tone mapping and exposure for renders.

    This is why a material set to pure white can render grey: the default AgX transform
    deliberately compresses highlights. Switch view_transform to 'Standard' when you need
    colours to come out exactly as authored (texture bakes, UI assets, flat-colour work).
    """
    return call("set_color_management", view_transform=view_transform, look=look, exposure=exposure, gamma=gamma)


@mcp.tool(annotations=WRITES_FILE)
def render_image(
    output_path: Annotated[str | None, Field(description="Absolute file path to write, e.g. '/tmp/shot.png'. Defaults to ~/.cache/blender-mcp-pro/renders/. An existing file is overwritten.")] = None,
    frame: Annotated[int | None, Field(description="Frame number to render. Defaults to the current frame; setting this also moves the scene's current frame.")] = None,
    return_image: Annotated[bool, Field(description="true (default) also sends back a downscaled preview so you can SEE the result and judge it. false returns only the path, which is cheaper for batches you don't need to inspect.")] = True,
    max_preview_size: Annotated[int, Field(description="Longest edge in pixels of the returned preview. Only affects the preview; the file on disk is always full resolution.")] = 512,
) -> Image | dict:
    """Render one frame through the active camera, write it to disk, and optionally return a preview image to look at.

    This is the way to actually check your work — geometry, materials and lighting all
    look different rendered than described. Render time depends entirely on engine and
    samples: WORKBENCH is instant, EEVEE takes seconds, CYCLES can take minutes (the call
    allows up to 10). Requires an active camera; set one with set_active_camera.
    """
    return image_result(call("render_image", timeout=LONG, output_path=output_path, frame=frame,
                             return_image=return_image, max_preview_size=max_preview_size))


@mcp.tool(annotations=WRITES_FILE)
def render_animation(
    output_path: Annotated[str, Field(description="Output path. Use #### as a frame-number placeholder for image sequences ('/tmp/out/frame_####.png'); without it Blender appends numbers itself. For FFMPEG output give a single video file path.")],
    frame_start: Annotated[int | None, Field(description="First frame. Defaults to the scene's frame_start.")] = None,
    frame_end: Annotated[int | None, Field(description="Last frame, inclusive. Defaults to the scene's frame_end.")] = None,
) -> dict:
    """Render a range of frames to an image sequence or video file.

    Cost is per frame: a 250-frame range at 10 s/frame is 40 minutes, and this call gives
    up 10 minutes in. Render one frame with render_image first to check the look, then
    narrow the range or drop samples/resolution before committing to the full sequence.
    """
    return call("render_animation", timeout=LONG, output_path=output_path, frame_start=frame_start, frame_end=frame_end)


@mcp.tool(annotations=WRITES_FILE)
def viewport_screenshot(
    output_path: Annotated[str | None, Field(description="Absolute path for the PNG. Defaults to the render cache directory.")] = None,
    return_image: Annotated[bool, Field(description="true (default) returns the image so you can see the viewport; false returns just the path.")] = True,
) -> Image | dict:
    """Grab what the user is currently looking at in the 3D viewport, including their view angle, overlays and gizmos.

    Different from render_image: this is the working view, not the camera, and it needs no
    lights or camera setup — handy for checking layout and whether objects are where you
    think. Requires the Blender GUI; it fails with a clear message when Blender runs
    headless.
    """
    return image_result(call("viewport_screenshot", output_path=output_path, return_image=return_image))
