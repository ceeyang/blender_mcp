"""Materials — create Principled BSDF materials, assign them, wire up texture maps."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE, Color

_TARGET_DOC = (
    "Which Principled input the texture drives: 'Base Color' (albedo), 'Roughness', 'Metallic', 'Alpha', "
    "'Emission Color', 'Specular IOR Level', or 'Normal' / 'Height' / 'AO', which are wired through the extra node "
    "each needs (Normal Map, Displacement, and a multiply into Base Color respectively)."
)


@mcp.tool(annotations=READ_ONLY)
def list_materials(
    used_only: Annotated[bool, Field(description="true lists only materials with at least one user. false (default) also lists orphans, which purge_orphans would delete.")] = False,
) -> list[dict]:
    """List every material in the file with its node count and which objects use it.

    Materials are shared datablocks, so one material can be on many objects and editing it
    changes all of them at once — the `objects` field tells you the blast radius before
    you change anything.
    """
    return call("list_materials", used_only=used_only)


@mcp.tool(annotations=READ_ONLY)
def get_material_info(
    name: Annotated[str, Field(description="Material name.")],
) -> dict:
    """Inspect one material: the main Principled BSDF input values, image textures with their file paths, node count, render settings, and which objects use it.

    `principled` is null when the material's surface is not a Principled BSDF (a custom
    node tree, glass shader, etc.) — use list_shader_nodes to see those in full.
    """
    return call("get_material_info", name=name)


@mcp.tool(annotations=CREATE)
def create_material(
    name: Annotated[str, Field(description="Name for the new material. Blender appends .001 if taken — it does NOT reuse an existing material of the same name.")],
    base_color: Annotated[list[float] | None, Field(description="Albedo as linear RGB or RGBA, each 0-1 (not 0-255, and not sRGB hex). Note renders apply the AgX view transform by default, so a value of 1.0 looks light grey rather than pure white.")] = None,
    metallic: Annotated[float | None, Field(description="0 for non-metals (default), 1 for bare metal. Intermediate values are physically meaningless — use 0 or 1. Metals take their colour from base_color and have no diffuse.")] = None,
    roughness: Annotated[float | None, Field(description="0 = mirror-sharp reflections, 1 = fully diffuse. Default 0.5. Polished surfaces sit near 0.1-0.2, plastic 0.4, concrete and cloth 0.8-1.")] = None,
    emission_color: Annotated[list[float] | None, Field(description="Colour of emitted light, 0-1 RGB. Has no visible effect until emission_strength is above 0.")] = None,
    emission_strength: Annotated[float | None, Field(description="Emission intensity; 0 (default) is off. Above ~1 the surface acts as a light source and, in Cycles, illuminates nearby geometry.")] = None,
    alpha: Annotated[float | None, Field(description="Opacity: 1 opaque (default), 0 invisible. Any value below 1 automatically switches the material's render method to BLENDED so transparency shows.")] = None,
    ior: Annotated[float | None, Field(description="Index of refraction, default 1.45. Glass 1.5, water 1.33, diamond 2.4. Affects the strength of specular reflection.")] = None,
    assign_to: Annotated[str | None, Field(description="Object to put this material on straight away (slot 0). Saves a separate assign_material call.")] = None,
) -> dict:
    """Create a Principled BSDF material from plain colour and surface values.

    The fast path for solid-colour materials — no node wiring needed. For textured
    materials use create_pbr_material (several image maps at once) or add_image_texture
    (one map onto an existing material). Creating a material with a name that already
    exists gives you a second one, so check list_materials first if you mean to reuse.
    """
    return call("create_material", name=name, base_color=base_color, metallic=metallic, roughness=roughness,
                emission_color=emission_color, emission_strength=emission_strength, alpha=alpha, ior=ior,
                assign_to=assign_to)


@mcp.tool(annotations=UPDATE)
def assign_material(
    object: Annotated[str, Field(description="Object to receive the material. Must be able to hold materials — meshes, curves and text can; cameras, lights and empties cannot.")],
    material: Annotated[str, Field(description="Name of an existing material. Create it first with create_material.")],
    slot: Annotated[int | None, Field(description="0-based material slot, default 0. Empty slots are added as needed to reach this index. Slot 1+ only shows on faces explicitly assigned to it, so on a plain mesh everything renders with slot 0.")] = None,
) -> dict:
    """Put an existing material into one object's material slot, replacing whatever was there.

    The material is shared, not copied. Use batch_apply_material for many objects at once.
    Returns the object's full slot list so you can see the result.
    """
    return call("assign_material", object=object, material=material, slot=slot)


@mcp.tool(annotations=UPDATE)
def set_principled_inputs(
    material: Annotated[str, Field(description="Material to modify. Its Principled BSDF node is created if missing.")],
    inputs: Annotated[dict, Field(description="Socket names mapped to values, using Blender 5.2 naming: 'Base Color', 'Metallic', 'Roughness', 'IOR', 'Alpha', 'Emission Color', 'Emission Strength', 'Specular IOR Level', 'Specular Tint', 'Subsurface Weight', 'Transmission Weight', 'Coat Weight', 'Coat Roughness', 'Sheen Weight', 'Anisotropic', 'Normal'. Colours take [r,g,b] or [r,g,b,a] 0-1, the rest take floats. A wrong name fails with the full socket list — note that plain 'Specular' and 'Subsurface' were renamed and no longer exist.")],
) -> dict:
    """Set several Principled BSDF inputs on an existing material in one call.

    Use this to adjust a material after creation; create_material makes one from scratch.
    A socket that already has a texture linked into it keeps the texture — the value you
    set sits underneath and has no visible effect until you unlink it.
    """
    return call("set_principled_inputs", material=material, inputs=inputs)


@mcp.tool(annotations=UPDATE)
def set_material_settings(
    material: Annotated[str, Field(description="Material to modify.")],
    surface_render_method: Annotated[str | None, Field(description="'DITHERED' (default, fast, handles most cases) or 'BLENDED' (proper alpha blending, needed for glass and fades, but sorts badly when transparent surfaces overlap). Blender 5.x replaces the old blend_method with this.")] = None,
    backface_culling: Annotated[bool | None, Field(description="true hides polygon back faces, matching how most game engines render. Useful for spotting flipped normals.")] = None,
    displacement_method: Annotated[str | None, Field(description="'BUMP' (default, shading trick, no real geometry), 'DISPLACEMENT' (real displaced geometry, Cycles with adaptive subdivision only) or 'BOTH'.")] = None,
    pass_index: Annotated[int | None, Field(description="Integer ID for this material in render passes, used to mask it in compositing.")] = None,
) -> dict:
    """Set how a material is rendered: transparency method, backface culling, displacement mode and pass index.

    Distinct from the surface's look — these are engine-level flags, not shader values.
    create_material already switches to BLENDED when you pass alpha below 1, so you rarely
    need to set that by hand.
    """
    return call("set_material_settings", material=material, surface_render_method=surface_render_method,
                backface_culling=backface_culling, displacement_method=displacement_method, pass_index=pass_index)


@mcp.tool(annotations=CREATE)
def add_image_texture(
    material: Annotated[str, Field(description="Existing material to add the texture node to.")],
    image_path: Annotated[str, Field(description="Absolute path to an image file (png, jpg, exr, tif). It is loaded into the .blend as a linked image, so the file must stay where it is.")],
    target: Annotated[str, Field(description=_TARGET_DOC)] = "Base Color",
    colorspace: Annotated[str | None, Field(description="Override the colour space, e.g. 'sRGB' or 'Non-Color'. By default colour maps get sRGB and data maps (roughness, metallic, normal, height) get Non-Color — getting this wrong on a data map visibly skews the result.")] = None,
    projection: Annotated[str | None, Field(description="'FLAT' (default, uses the object's UVs), 'BOX' (triplanar, needs no UVs — good for rock and terrain), 'SPHERE' or 'TUBE'.")] = None,
) -> dict:
    """Load an image and wire it into one Principled BSDF input, adding whatever helper node that input needs.

    Normal maps get a Normal Map node, height maps a Displacement node into the material
    output, AO a multiply into Base Color — you don't wire those yourself. FLAT projection
    needs UVs on the mesh (unwrap_uv), which primitives from create_primitive already
    have. Use create_pbr_material to attach a whole texture set at once.
    """
    return call("add_image_texture", material=material, image_path=image_path, target=target, colorspace=colorspace,
                projection=projection)


@mcp.tool(annotations=CREATE)
def create_pbr_material(
    name: Annotated[str, Field(description="Name for the new material.")],
    base_color: Annotated[str | None, Field(description="Absolute path to the albedo / diffuse / base colour map.")] = None,
    roughness: Annotated[str | None, Field(description="Absolute path to the roughness map (loaded as Non-Color).")] = None,
    metallic: Annotated[str | None, Field(description="Absolute path to the metallic map (Non-Color).")] = None,
    normal: Annotated[str | None, Field(description="Absolute path to a tangent-space normal map; a Normal Map node is inserted automatically.")] = None,
    height: Annotated[str | None, Field(description="Absolute path to a height/displacement map; wired through a Displacement node to the material output.")] = None,
    ao: Annotated[str | None, Field(description="Absolute path to an ambient occlusion map; multiplied into Base Color.")] = None,
    assign_to: Annotated[str | None, Field(description="Object to assign the finished material to.")] = None,
) -> dict:
    """Build a full PBR material from a set of texture files in one call, wiring each map to the right input.

    Pass only the maps you have; every argument is optional. When your textures are all in
    one folder with conventional names, material_from_texture_folder finds and classifies
    them for you instead of you naming each path here.
    """
    return call("create_pbr_material", name=name, base_color=base_color, roughness=roughness, metallic=metallic,
                normal=normal, height=height, ao=ao, assign_to=assign_to)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_material(
    name: Annotated[str, Field(description="Material to remove.")],
    unlink_only: Annotated[bool, Field(description="true detaches it from every object but keeps the material in the file (as an orphan, recoverable). false (default) deletes the datablock outright.")] = False,
) -> dict:
    """Remove a material from every object that uses it and delete it from the file.

    The response lists which objects were affected — check it, since a material can be on
    more objects than you expect. Their slots are left empty, so they render with
    Blender's default grey.
    """
    return call("delete_material", name=name, unlink_only=unlink_only)
