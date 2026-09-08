"""Scene Utilities — arbitrary code, API docs, undo, measurement and mesh diagnostics."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import DESTRUCTIVE, READ_ONLY, UPDATE, Objects


@mcp.tool(annotations=DESTRUCTIVE)
def execute_code(
    code: Annotated[str, Field(description="Python source executed inside Blender. bpy, bmesh, mathutils, Vector and math are already imported. Multi-line is fine; it runs as a module body, so assign to a variable rather than using `return`.")],
    return_var: Annotated[str | None, Field(description="Name of a variable defined by `code` to send back, JSON-serialised. Without this you only get stdout, so assign your answer to a variable and name it here.")] = None,
) -> dict:
    """Run arbitrary Python inside Blender — the escape hatch when no other tool fits.

    Prefer a purpose-built tool whenever one exists: they validate arguments and return
    useful errors. Use this for one-off queries, bmesh work, and APIs this server doesn't
    wrap. It can do anything Blender can, including deleting the scene, and the call runs
    on the main thread, so a long loop freezes the UI until it finishes.
    """
    return call("execute_code", timeout=300.0, code=code, return_var=return_var)


@mcp.tool(annotations=READ_ONLY)
def get_blender_info() -> dict:
    """Report the Blender build and this add-on's state: version, Python, binary path, current .blend, enabled add-ons, MCP server status, and whether a Sketchfab token is configured.

    Use it to confirm a feature is available before relying on it — for example that
    Rigify is enabled, or whether Blender is running headless (`background`: true), which
    disables viewport_screenshot and `undo`.
    """
    return call("get_blender_info")


@mcp.tool(annotations=READ_ONLY)
def get_api_docs(
    path: Annotated[str, Field(description="A bpy path in one of three shapes: a type ('bpy.types.Object'), one member of a type ('bpy.types.Object.rotation_mode'), or an operator ('bpy.ops.mesh.primitive_cube_add'). Wrong names come back with close matches.")],
) -> dict:
    """Look up Blender's own API documentation from the running build — descriptions, types, enum values, defaults and ranges.

    Entirely local and always matches this exact Blender version, so it beats recalling
    the API from memory when you are unsure of a property name or the valid values of an
    enum. Pair it with execute_code, set_modifier or set_node_property, whose `settings`
    take raw bpy attribute names.
    """
    return call("get_api_docs", path=path)


@mcp.tool(annotations=UPDATE)
def undo() -> dict:
    """Undo the last operation, exactly like Ctrl+Z in the UI.

    Every mutating tool in this server pushes one undo step, so a single call reverts one
    tool call. Requires the Blender GUI — there is no undo stack when Blender runs
    headless, and the call fails with a clear message there.
    """
    return call("undo")


@mcp.tool(annotations=UPDATE)
def redo() -> dict:
    """Redo the step that `undo` just reverted, exactly like Ctrl+Shift+Z in the UI.

    Only meaningful straight after an `undo` — any new mutating tool call discards the
    redo stack. Requires the Blender GUI, like undo.
    """
    return call("redo")


@mcp.tool(annotations=DESTRUCTIVE)
def purge_orphans() -> dict:
    """Permanently delete datablocks with zero users — meshes, materials, images and node groups left behind by deletions.

    Blender keeps unused data in the file until it is saved without it; this cleans it out
    immediately and reports how many were removed. Anything you created but have not yet
    assigned to an object counts as an orphan and will be destroyed, so purge after
    deleting, not before assigning.
    """
    return call("purge_orphans")


@mcp.tool(annotations=UPDATE)
def set_units(
    system: Annotated[str | None, Field(description="METRIC, IMPERIAL or NONE (raw Blender units with no unit suffix).")] = None,
    scale_length: Annotated[float | None, Field(description="Metres per Blender unit. 1.0 means 1 unit = 1 m; 0.01 makes a unit a centimetre. Changing it rescales how existing sizes are displayed, not the geometry.")] = None,
    length_unit: Annotated[str | None, Field(description="Display unit: METERS, CENTIMETERS, MILLIMETERS, KILOMETERS, or ADAPTIVE.")] = None,
    rotation_unit: Annotated[str | None, Field(description="DEGREES or RADIANS — affects only how the UI displays angles. This server's tools always take radians regardless.")] = None,
) -> dict:
    """Set the scene's unit system and display units.

    Cosmetic for the most part: it changes how numbers are shown in the UI, not the
    underlying values, and this server's parameters stay in meters and radians either way.
    Worth setting to match a target engine before exporting.
    """
    return call("set_units", system=system, scale_length=scale_length, length_unit=length_unit,
                rotation_unit=rotation_unit)


@mcp.tool(annotations=UPDATE)
def set_cursor(
    location: Annotated[list[float] | None, Field(description="World [x, y, z] in meters to place the 3D cursor at.")] = None,
    rotation: Annotated[list[float] | None, Field(description="Cursor orientation as Euler XYZ in radians.")] = None,
) -> dict:
    """Move Blender's 3D cursor, the reference point several operations snap to.

    Its main use here is set_origin with type='CURSOR': put the cursor where you want the
    pivot, then move the origin to it. New objects created via create_primitive are placed
    by their `location` argument and ignore the cursor.
    """
    return call("set_cursor", location=location, rotation=rotation)


@mcp.tool(annotations=READ_ONLY)
def measure_distance(
    a: Annotated[str | list[float], Field(description="An object name (its world origin is used) or a world coordinate [x, y, z].")],
    b: Annotated[str | list[float], Field(description="The other endpoint, same forms as `a`.")],
) -> dict:
    """Measure the straight-line distance between two objects or points, also returning the per-axis delta.

    Distances are between object ORIGINS, not surfaces — an object whose origin sits off
    its geometry will read differently than you expect. Use get_bounding_box for extents
    and ray_cast for a distance to an actual surface.
    """
    return call("measure_distance", a=a, b=b)


@mcp.tool(annotations=READ_ONLY)
def get_bounding_box(
    objects: Objects,
    world: Annotated[bool, Field(description="true (default) gives world-space extents including each object's transform. false gives local-space extents ignoring position, rotation and scale.")] = True,
) -> dict:
    """Get the combined bounding box of one or more objects: min, max, center and size.

    The go-to tool for 'how big is this and where is it' — sizing a ground plane to a
    scene, stacking one object exactly on another, or checking something fits. The box is
    axis-aligned, so a rotated object reports a box larger than the object itself.
    """
    return call("get_bounding_box", objects=objects, world=world)


@mcp.tool(annotations=READ_ONLY)
def ray_cast(
    origin: Annotated[list[float], Field(description="World-space start point [x, y, z] of the ray.")],
    direction: Annotated[list[float], Field(description="Direction vector [x, y, z]; it is normalised for you, so [0, 0, -1] means straight down.")],
    distance: Annotated[float, Field(description="How far to search along the ray, in meters.")] = 1000.0,
) -> dict:
    """Fire a ray into the scene and report the first surface it hits: object, hit point, surface normal and face index.

    This is how you place something exactly ON a surface rather than guessing a Z value —
    cast down from above and use the returned location. Respects modifiers and hidden
    state as evaluated. Returns {"hit": false} when nothing is in the way.
    """
    return call("ray_cast", origin=origin, direction=direction, distance=distance)


@mcp.tool(annotations=READ_ONLY)
def check_mesh(
    name: Annotated[str, Field(description="Mesh object to inspect. Fails on non-mesh objects.")],
) -> dict:
    """Diagnose one mesh: vertex/edge/face counts, triangle count, quads vs n-gons, non-manifold edges, loose vertices and edges, and duplicate vertices.

    Run it before exporting, before a BOOLEAN modifier, or when a modifier produces
    strange results — non-manifold geometry and doubles are the usual cause. It only
    reports; mesh_cleanup is what fixes the problems it finds.
    """
    return call("check_mesh", name=name)


@mcp.tool(annotations=DESTRUCTIVE)
def mesh_cleanup(
    name: Annotated[str, Field(description="Mesh object to clean up.")],
    recalc_normals: Annotated[bool, Field(description="Recompute face normals to point consistently outward. Fixes surfaces that render black or inside-out.")] = False,
    inside: Annotated[bool, Field(description="Flip the recalculated normals to point inward instead. Only meaningful with recalc_normals=true.")] = False,
    merge_by_distance: Annotated[bool, Field(description="Weld vertices closer together than `threshold`. Removes the duplicates that check_mesh reports and closes invisible seams.")] = False,
    threshold: Annotated[float, Field(description="Distance in meters below which vertices are merged. Raise it for coarse cleanup; too high collapses real detail.")] = 0.0001,
    shade_smooth: Annotated[bool | None, Field(description="true sets every face to smooth shading, false to flat. Omit to leave shading alone.")] = None,
    auto_smooth_angle: Annotated[float | None, Field(description="Smooth only across edges whose angle is under this, in RADIANS (0.52 = 30 deg, 1.05 = 60 deg). Gives smooth curves while keeping hard edges crisp.")] = None,
    dissolve_degenerate: Annotated[bool, Field(description="Remove zero-area faces and zero-length edges, which break booleans and exports.")] = False,
) -> dict:
    """Repair and tidy a mesh: recalculate normals, weld doubles, dissolve degenerate geometry, and set smooth shading.

    Operations apply in one pass in the order listed above. This edits the mesh data
    permanently (undoable, but not by re-running with the flags off), and merging vertices
    can destroy UVs and shape keys, so run check_mesh first to see what actually needs
    fixing rather than enabling everything.
    """
    return call("mesh_cleanup", name=name, recalc_normals=recalc_normals, inside=inside,
                merge_by_distance=merge_by_distance, threshold=threshold, shade_smooth=shade_smooth,
                auto_smooth_angle=auto_smooth_angle, dissolve_degenerate=dissolve_degenerate)
