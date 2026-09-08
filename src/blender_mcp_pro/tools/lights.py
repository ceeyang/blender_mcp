"""Lights — point/sun/spot/area lamps and the world background."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, READ_ONLY, UPDATE, Location, Rotation


@mcp.tool(annotations=READ_ONLY)
def list_lights() -> list[dict]:
    """List every light with its type, position, energy, colour and shape parameters.

    Start here when a render is too dark or blown out — energy is in watts and scales with
    the square of distance, so the numbers that work depend entirely on how far the lights
    are from the subject.
    """
    return call("list_lights")


@mcp.tool(annotations=READ_ONLY)
def get_light_info(
    name: Annotated[str, Field(description="Light object name.")],
) -> dict:
    """Get one light's full settings, including the parameters specific to its type (spot cone, area size, sun angle).

    `type` is the object type ('LIGHT'); `light_type` is POINT/SUN/SPOT/AREA.
    """
    return call("get_light_info", name=name)


@mcp.tool(annotations=CREATE)
def create_light(
    type: Annotated[str, Field(description="POINT (omnidirectional bulb), SUN (parallel rays, infinitely far — position is irrelevant, only rotation matters), SPOT (cone), or AREA (soft rectangular panel, the most natural-looking for interiors and product shots).")],
    name: Annotated[str | None, Field(description="Name for the new light. Defaults to the capitalised type.")] = None,
    location: Location = None,
    rotation: Annotated[list[float] | None, Field(description="Euler XYZ in RADIANS. Only matters for SUN, SPOT and AREA (POINT emits in all directions). Easier to leave unset and use `target` instead.")] = None,
    energy: Annotated[float | None, Field(description="Power in watts. POINT/SPOT/AREA typically need 100-1000 W at a few meters, and much more at 15+ m since intensity falls off with distance squared. SUN is different: it uses irradiance, where 1-5 is daylight.")] = None,
    color: Annotated[list[float] | None, Field(description="Light colour as linear RGB, each 0-1. Warm light is roughly [1, 0.85, 0.7], cool daylight [0.9, 0.95, 1].")] = None,
    radius: Annotated[float | None, Field(description="Emitter radius in meters for POINT and SPOT. Larger means softer shadow edges; 0 gives razor-sharp shadows that read as artificial.")] = None,
    size: Annotated[float | None, Field(description="Edge length in meters of an AREA light. This is the main softness control for area lights — a big panel wraps light around the subject.")] = None,
    spot_size: Annotated[float | None, Field(description="Full cone angle of a SPOT in RADIANS (0.785 = 45 deg, 1.047 = 60 deg).")] = None,
    spot_blend: Annotated[float | None, Field(description="Softness of the spot's edge, 0 (hard cut) to 1 (fully feathered).")] = None,
    target: Annotated[str | list[float] | None, Field(description="Object name or [x, y, z] to aim the light at immediately, saving a point_light_at call. Ignored for POINT lights, which have no direction.")] = None,
) -> dict:
    """Create a light and optionally aim it at something in the same call.

    Shadow softness comes from emitter size, not from a shadow setting: bump `radius` or
    `size` to soften. For a complete lighting setup in one call, use
    setup_three_point_lighting instead of placing lamps individually.
    """
    return call("create_light", type=type, name=name, location=location, rotation=rotation, energy=energy, color=color,
                radius=radius, size=size, spot_size=spot_size, spot_blend=spot_blend, target=target)


@mcp.tool(annotations=UPDATE)
def set_light(
    name: Annotated[str, Field(description="Light to modify.")],
    energy: Annotated[float | None, Field(description="Power in watts (irradiance for SUN).")] = None,
    color: Annotated[list[float] | None, Field(description="Linear RGB 0-1.")] = None,
    radius: Annotated[float | None, Field(description="Emitter radius in meters, controlling shadow softness for POINT/SPOT.")] = None,
    size: Annotated[float | None, Field(description="AREA light size in meters. Ignored by other light types.")] = None,
    shape: Annotated[str | None, Field(description="AREA light shape: SQUARE, RECTANGLE, DISK or ELLIPSE. Ignored by other types.")] = None,
    spot_size: Annotated[float | None, Field(description="SPOT cone angle in radians. Ignored by other types.")] = None,
    spot_blend: Annotated[float | None, Field(description="SPOT edge softness, 0-1. Ignored by other types.")] = None,
    use_shadow: Annotated[bool | None, Field(description="false makes the light cast no shadows, useful for a fill light that should only lift the dark side without adding a second shadow.")] = None,
    angle: Annotated[float | None, Field(description="SUN angular diameter in RADIANS, controlling shadow softness. 0.526 deg (0.00918 rad) matches the real sun; larger reads as overcast.")] = None,
) -> dict:
    """Adjust an existing light's intensity, colour, softness and type-specific parameters.

    Only the arguments you pass change, and parameters that don't apply to the light's
    type are silently ignored — so `size` does nothing on a POINT light. Use
    point_light_at or set_transform to move or aim it.
    """
    return call("set_light", name=name, energy=energy, color=color, radius=radius, size=size, shape=shape,
                spot_size=spot_size, spot_blend=spot_blend, use_shadow=use_shadow, angle=angle)


@mcp.tool(annotations=UPDATE)
def point_light_at(
    light: Annotated[str, Field(description="Light to aim. Its position is unchanged.")],
    target: Annotated[str | list[float], Field(description="Object name (aims at its origin) or a world coordinate [x, y, z].")],
    use_constraint: Annotated[bool, Field(description="false (default) sets rotation once. true adds a Track To constraint so the light keeps following the target as it moves; when the target is a coordinate, an Empty is created to track.")] = False,
) -> dict:
    """Rotate a light to point at an object or a coordinate.

    Meaningless for POINT lights, which emit in every direction. For SUN lights this is
    the only thing that matters, since position has no effect on a light that is
    conceptually infinitely far away.
    """
    return call("point_light_at", light=light, target=target, use_constraint=use_constraint)


@mcp.tool(annotations=UPDATE)
def set_world_lighting(
    color: Annotated[list[float] | None, Field(description="Flat background colour as linear RGB 0-1. Overridden visually once an HDRI is loaded.")] = None,
    strength: Annotated[float | None, Field(description="World light intensity. 0 kills ambient light entirely (harsh, black shadows); 0.5-1 is a normal sky contribution; above 2 washes the scene out.")] = None,
    hdri_path: Annotated[str | None, Field(description="Absolute path to an .hdr or .exr environment map. Sets up the Environment Texture + Mapping + Texture Coordinate nodes for you. polyhaven_download fetches free ones and calls this automatically.")] = None,
    rotation: Annotated[list[float] | None, Field(description="Euler XYZ in RADIANS to spin the HDRI, mainly the Z component to move where the sun sits. Requires an HDRI to be loaded first.")] = None,
) -> dict:
    """Set the world background: a flat colour, or an HDRI environment map that lights the whole scene.

    The world is what fills your shadows — with no world light, unlit sides go pure black.
    An HDRI is the fastest route to believable lighting since it supplies both the
    background and realistic ambient light from every direction.
    """
    return call("set_world_lighting", color=color, strength=strength, hdri_path=hdri_path, rotation=rotation)
