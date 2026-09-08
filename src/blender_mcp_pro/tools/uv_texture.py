"""UV & Texture — unwrapping, seams, image datablocks and texture baking."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import LONG, call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE, WRITES_FILE


@mcp.tool(annotations=READ_ONLY)
def list_uv_maps(
    object: Annotated[str, Field(description="Mesh object to inspect.")],
) -> list[dict]:
    """List a mesh's UV maps and which one is active.

    A mesh can carry several UV layouts — one for textures, another for lightmap baking.
    The active one is what materials sample and what bake_texture writes into.
    """
    return call("list_uv_maps", object=object)


@mcp.tool(annotations=CREATE)
def add_uv_map(
    object: Annotated[str, Field(description="Mesh object to add a UV layer to.")],
    name: Annotated[str | None, Field(description="Name for the new UV map, e.g. 'UVMap' or 'Lightmap'. Defaults to Blender's numbering.")] = None,
    set_active: Annotated[bool, Field(description="true (default) makes the new map active, so subsequent unwrapping and baking target it. false adds it without changing what materials currently sample.")] = True,
) -> dict:
    """Add an empty UV map to a mesh.

    The new map starts unwrapped-but-degenerate, so follow it with unwrap_uv to actually
    lay out the coordinates. Most meshes need only one; add a second when you want a
    separate non-overlapping layout for lightmaps or baking.
    """
    return call("add_uv_map", object=object, name=name, set_active=set_active)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_uv_map(
    object: Annotated[str, Field(description="Mesh object.")],
    name: Annotated[str, Field(description="UV map to delete.")],
) -> dict:
    """Delete a UV map from a mesh, discarding its layout.

    Materials sampling that map fall back to the next one, which usually shows as textures
    suddenly landing in the wrong place.
    """
    return call("remove_uv_map", object=object, name=name)


@mcp.tool(annotations=UPDATE)
def unwrap_uv(
    object: Annotated[str, Field(description="Mesh object to unwrap. All faces are selected and unwrapped.")],
    method: Annotated[str, Field(description="'ANGLE_BASED' (default, general purpose, respects seams), 'CONFORMAL' (faster, less even), 'SMART_PROJECT' (automatic — splits by face angle and needs no seams, the pragmatic choice for props), 'CUBE'/'CYLINDER'/'SPHERE' (projections for matching shapes), 'LIGHTMAP' (packs non-overlapping islands for baking).")] = "ANGLE_BASED",
    margin: Annotated[float, Field(description="Gap between UV islands, 0-1 of UV space. Larger prevents texture bleeding between islands when the texture is filtered or mipmapped.")] = 0.001,
    angle_limit: Annotated[float | None, Field(description="For SMART_PROJECT only: the angle in RADIANS above which faces are split into separate islands (1.15 = 66 deg, Blender's default). Lower makes more, flatter islands.")] = None,
    uv_map: Annotated[str | None, Field(description="Which UV map to write into. Defaults to the active one.")] = None,
) -> dict:
    """Compute UV coordinates for a mesh so textures can be applied to it.

    ANGLE_BASED and CONFORMAL follow the seams you set with mark_seams and give poor
    results without them; SMART_PROJECT ignores seams and works out its own splits, which
    is usually what you want for props and hard-surface models. Primitives from
    create_primitive already have usable UVs, so you only need this for meshes you have
    heavily modified, or joined, or for lightmaps.
    """
    return call("unwrap_uv", object=object, method=method, margin=margin, angle_limit=angle_limit, uv_map=uv_map)


@mcp.tool(annotations=UPDATE)
def pack_uv_islands(
    object: Annotated[str, Field(description="Mesh object whose UV islands to repack.")],
    margin: Annotated[float, Field(description="Gap between islands in UV space. Raise it if baked textures bleed across island edges.")] = 0.001,
    rotate: Annotated[bool, Field(description="true (default) lets islands rotate to pack tighter. false keeps their orientation, which matters when the texture has a direction (wood grain, text).")] = True,
) -> dict:
    """Rearrange existing UV islands to use the 0-1 UV square more efficiently.

    Does not change the unwrap itself, only where the pieces sit — more texture resolution
    for the same image size. Run it after unwrapping or after joining objects, whose UVs
    end up overlapping.
    """
    return call("pack_uv_islands", object=object, margin=margin, rotate=rotate)


@mcp.tool(annotations=UPDATE)
def mark_seams(
    object: Annotated[str, Field(description="Mesh object.")],
    edges: Annotated[list[int] | None, Field(description="Edge indices to mark, from check_mesh or your own inspection. Omit when using from_sharp.")] = None,
    from_sharp: Annotated[bool, Field(description="true marks seams automatically along edges flagged sharp — a decent starting point on hard-surface models with no manual work.")] = False,
    clear: Annotated[bool, Field(description="true REMOVES seams on the given edges (or all of them when `edges` is omitted) instead of adding them.")] = False,
) -> dict:
    """Mark or clear UV seams — the edges along which unwrapping cuts the mesh open.

    Only affects the ANGLE_BASED and CONFORMAL unwrap methods; SMART_PROJECT ignores
    seams entirely. Think of them as where you would cut a paper model to flatten it.
    """
    return call("mark_seams", object=object, edges=edges, from_sharp=from_sharp, clear=clear)


@mcp.tool(annotations=CREATE)
def create_image(
    name: Annotated[str, Field(description="Name for the new image datablock.")],
    width: Annotated[int, Field(description="Width in pixels. Powers of two (512, 1024, 2048) are the norm for textures.")] = 1024,
    height: Annotated[int, Field(description="Height in pixels.")] = 1024,
    color: Annotated[list[float] | None, Field(description="Fill colour as [r, g, b, a], each 0-1. Defaults to opaque black.")] = None,
    alpha: Annotated[bool, Field(description="true (default) gives the image an alpha channel.")] = True,
    float_buffer: Annotated[bool, Field(description="true stores 32-bit float per channel, needed for HDR data and high-quality normal or displacement bakes. false is 8-bit, smaller and enough for colour.")] = False,
) -> dict:
    """Create a blank in-memory image datablock to bake or paint into.

    It exists only in the .blend until save_image writes it to disk. bake_texture can
    create its own image, so you mainly need this to control size, bit depth or fill
    colour up front.
    """
    return call("create_image", name=name, width=width, height=height, color=color, alpha=alpha,
                float_buffer=float_buffer)


@mcp.tool(annotations=CREATE)
def bake_texture(
    object: Annotated[str, Field(description="Mesh object to bake. It must have UVs (unwrap_uv) and at least one material, or the bake fails.")],
    bake_type: Annotated[str, Field(description="What to capture: 'DIFFUSE' (base colour without lighting), 'NORMAL' (surface detail as a tangent-space normal map), 'AO' (ambient occlusion), 'ROUGHNESS', 'EMIT' (emission only — the cheapest way to bake flat colour), 'COMBINED' (full lighting result, the slowest).")],
    image: Annotated[str | None, Field(description="Existing image datablock to bake into. Omit to create one sized by `size`.")] = None,
    size: Annotated[int, Field(description="Pixel size of the auto-created image (square). 1024 is a reasonable default; 2048+ costs bake time proportionally.")] = 1024,
    output_path: Annotated[str | None, Field(description="Absolute path to also write the result as a PNG. Without it the bake lives only in the .blend.")] = None,
    margin: Annotated[int, Field(description="Pixels of bleed painted outside each UV island, preventing seams from showing when the texture is mipmapped.")] = 16,
    selected_to_active: Annotated[bool, Field(description="true bakes detail from other selected objects ONTO this one — the high-poly-to-low-poly workflow that puts sculpted detail into a normal map.")] = False,
    cage_extrusion: Annotated[float, Field(description="How far, in meters, rays are pushed out from the low-poly surface when selected_to_active is on. Raise it if the bake shows gaps or artefacts.")] = 0.0,
    samples: Annotated[int, Field(description="Cycles samples per pixel. 16 (default) is fine for AO and normals; raise for COMBINED and DIFFUSE with complex lighting. Bake time scales with this.")] = 16,
) -> dict:
    """Bake surface detail or lighting into a texture image, temporarily switching the renderer to Cycles.

    Baking is how procedural materials and high-poly detail become plain image textures a
    game engine can use. It is slow — minutes for a large image with many samples, and
    this call allows up to 10 — and it silently produces garbage if the mesh has
    overlapping UVs, so unwrap (or LIGHTMAP-unwrap) first.
    """
    return call("bake_texture", timeout=LONG, object=object, bake_type=bake_type, image=image, size=size,
                output_path=output_path, margin=margin, selected_to_active=selected_to_active,
                cage_extrusion=cage_extrusion, samples=samples)


@mcp.tool(annotations=WRITES_FILE)
def save_image(
    image: Annotated[str, Field(description="Name of the image datablock to write.")],
    path: Annotated[str, Field(description="Absolute destination path. An existing file is overwritten.")],
    format: Annotated[str | None, Field(description="'PNG', 'JPEG', 'OPEN_EXR', 'TIFF' or 'WEBP'. Inferred from the extension when omitted. Use OPEN_EXR for float images — PNG would clip their range.")] = None,
) -> dict:
    """Write an image datablock to a file on disk.

    Baked and generated images live only in memory until this is called, so a bake you
    never save is lost when the file closes (unless you also save the .blend).
    """
    return call("save_image", image=image, path=path, format=format)


@mcp.tool(annotations=READ_ONLY)
def list_images() -> list[dict]:
    """List every image datablock in the file with its size, source path and user count.

    Shows both images loaded from disk and generated ones from baking. Images with zero
    users are orphans that purge_orphans would delete.
    """
    return call("list_images")
