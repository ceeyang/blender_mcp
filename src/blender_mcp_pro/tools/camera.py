"""Camera — create, aim and frame cameras."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, READ_ONLY, UPDATE, Location, Objects, Rotation


@mcp.tool(annotations=READ_ONLY)
def list_cameras() -> list[dict]:
    """List every camera with its transform, lens, clipping, depth of field, and which one is the scene's active camera.

    Only the active camera is what render_image sees — check `is_active` before rendering.
    """
    return call("list_cameras")


@mcp.tool(annotations=READ_ONLY)
def get_camera_info(
    name: Annotated[str, Field(description="Camera object name.")],
) -> dict:
    """Get one camera's full settings: focal length, horizontal FOV in degrees, sensor size, projection type, clip range, lens shift, depth of field, and whether it is active.

    `type` is the object type ('CAMERA'); `projection` is PERSP or ORTHO. `fov_deg` is the
    horizontal field of view, useful for working out how far back to place the camera.
    """
    return call("get_camera_info", name=name)


@mcp.tool(annotations=CREATE)
def create_camera(
    name: Annotated[str | None, Field(description="Name for the new camera. Defaults to 'Camera' with Blender's numbering.")] = None,
    location: Location = None,
    rotation: Annotated[list[float] | None, Field(description="Euler XYZ in RADIANS. A camera with zero rotation looks straight DOWN (-Z), not forward — so either set this deliberately or leave it and use point_camera_at / frame_objects afterwards.")] = None,
    lens: Annotated[float | None, Field(description="Focal length in mm on a 36 mm sensor: 18-24 wide angle, 35-50 natural, 85+ telephoto/compressed. Default 50.")] = None,
    type: Annotated[str | None, Field(description="PERSP (default, normal perspective) or ORTHO (parallel projection, sized by ortho_scale — used for isometric and technical views).")] = None,
    sensor_width: Annotated[float | None, Field(description="Sensor width in mm, default 36 (full frame). Together with `lens` this determines the field of view.")] = None,
    clip_start: Annotated[float | None, Field(description="Near clip distance in meters; geometry closer than this is invisible. Default 0.1.")] = None,
    clip_end: Annotated[float | None, Field(description="Far clip distance in meters; geometry beyond this is invisible. Default 1000 — raise it for very large scenes.")] = None,
    set_active: Annotated[bool, Field(description="true (default) makes this the camera that renders. false creates it without disturbing the current active camera.")] = True,
) -> dict:
    """Create a camera and, by default, make it the one that renders.

    A new camera points straight down until you aim it, so the usual sequence is:
    create_camera at a position, then point_camera_at your subject (or frame_objects to
    also pull back far enough to fit everything).
    """
    return call("create_camera", name=name, location=location, rotation=rotation, lens=lens, type=type,
                sensor_width=sensor_width, clip_start=clip_start, clip_end=clip_end, set_active=set_active)


@mcp.tool(annotations=UPDATE)
def set_camera(
    name: Annotated[str, Field(description="Camera to modify.")],
    lens: Annotated[float | None, Field(description="Focal length in mm. Lower widens the view and exaggerates perspective; higher flattens it.")] = None,
    type: Annotated[str | None, Field(description="PERSP or ORTHO.")] = None,
    ortho_scale: Annotated[float | None, Field(description="For ORTHO cameras, how many meters the longer image edge spans. This replaces focal length as the way to zoom.")] = None,
    clip_start: Annotated[float | None, Field(description="Near clip in meters.")] = None,
    clip_end: Annotated[float | None, Field(description="Far clip in meters.")] = None,
    shift_x: Annotated[float | None, Field(description="Horizontal lens shift in sensor widths. Shifts the framing without rotating the camera, so vertical lines stay parallel (architectural correction).")] = None,
    shift_y: Annotated[float | None, Field(description="Vertical lens shift in sensor widths.")] = None,
    dof: Annotated[dict | None, Field(description="Depth of field as a dict: {'enabled': true, 'focus_object': 'Hero', 'fstop': 1.8} focuses on an object, or {'enabled': true, 'focus_distance': 6.0, 'fstop': 2.8} on a distance in meters. Lower fstop means shallower focus and more background blur.")] = None,
) -> dict:
    """Change lens, projection, clipping, lens shift or depth of field on an existing camera.

    Only the arguments you pass are touched. Use point_camera_at or set_transform to
    change where it is and where it looks; this tool only adjusts the optics.
    """
    return call("set_camera", name=name, lens=lens, type=type, ortho_scale=ortho_scale, clip_start=clip_start,
                clip_end=clip_end, shift_x=shift_x, shift_y=shift_y, dof=dof)


@mcp.tool(annotations=UPDATE)
def set_active_camera(
    name: Annotated[str, Field(description="Camera to render through.")],
) -> dict:
    """Choose which camera the scene renders through.

    render_image and render_animation always use the active camera, so switching between
    set-up shots is a single call.
    """
    return call("set_active_camera", name=name)


@mcp.tool(annotations=UPDATE)
def point_camera_at(
    camera: Annotated[str, Field(description="Camera to aim. Its position is unchanged; only rotation is set.")],
    target: Annotated[str | list[float], Field(description="An object name (aims at its origin, which may not be its visual center) or a world coordinate [x, y, z].")],
    use_constraint: Annotated[bool, Field(description="false (default) sets the rotation once. true adds a Track To constraint so the camera keeps following the target as it moves — right for animation, and it overrides manual rotation until removed.")] = False,
) -> dict:
    """Rotate a camera to look at an object or a point, leaving its position alone.

    The complement to frame_objects: this only aims, that also moves the camera back far
    enough to fit the subject. Aiming at an object uses its ORIGIN, so for an object whose
    origin sits at its feet, pass an explicit coordinate raised to eye level instead.
    """
    return call("point_camera_at", camera=camera, target=target, use_constraint=use_constraint)


@mcp.tool(annotations=UPDATE)
def frame_objects(
    camera: Annotated[str, Field(description="Camera to move and aim.")],
    objects: Objects,
    margin: Annotated[float, Field(description="Padding multiplier on the computed distance: 1.0 fits the bounding sphere exactly, 1.1 (default) leaves ~10% breathing room, below 1.0 crops in.")] = 1.1,
) -> dict:
    """Move a camera back along its current direction from the subject until the objects fit in frame, then aim it at them.

    It keeps the side you placed the camera on and only changes distance and rotation, so
    position the camera roughly first, then call this. Distance comes from the subject's
    bounding SPHERE and the shorter edge of the frame, which is deliberately conservative:
    a wide, flat scene (a landscape, a row of props) yields a sphere much bigger than what
    you see, so the camera can end up further away than you want. When that happens, place
    the camera by hand with set_transform and aim it with point_camera_at.
    """
    return call("frame_objects", camera=camera, objects=objects, margin=margin)
