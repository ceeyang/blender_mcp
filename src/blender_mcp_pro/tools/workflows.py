"""Workflows — multi-step recipes that compose the lower-level tools."""
from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import Image
from pydantic import Field

from ..server import mcp
from ._base import LONG, call, image_result
from ._types import CREATE, DESTRUCTIVE, WRITES_FILE, Objects


@mcp.tool(annotations=CREATE)
def setup_three_point_lighting(
    target: Annotated[str, Field(description="Object to light. The three lamps are positioned around it and aimed at its origin.")],
    distance: Annotated[float, Field(description="How far the lights sit from the target, in meters. Scale this with your subject — 6 suits a 2 m object, a 10 m building needs 15-20.")] = 6.0,
    height: Annotated[float, Field(description="Height of the key light above the target in meters. Roughly half the distance gives a natural 30-45 degree angle.")] = 3.0,
    key_energy: Annotated[float, Field(description="Power of the main light in watts. Because falloff is quadratic, doubling `distance` needs roughly four times this — a few hundred watts at 6 m, tens of thousands at 20 m.")] = 1000.0,
    fill_ratio: Annotated[float, Field(description="Fill light power as a fraction of the key. 0.4 (default) leaves visible but readable shadows; lower is more dramatic, 1.0 is flat.")] = 0.4,
    rim_ratio: Annotated[float, Field(description="Rim (back) light power as a fraction of the key. This is what separates the subject from the background with a bright edge.")] = 0.8,
    color_temp: Annotated[float | None, Field(description="Colour temperature in KELVIN applied to all three lights: 3200 tungsten/warm, 5600 daylight, 7000+ cool blue. Omit for pure white.")] = None,
) -> dict:
    """Build a complete three-point lighting rig — key, fill and rim — around an object, aimed and balanced.

    The standard setup for making anything look presentable, and far quicker than placing
    lamps one at a time with create_light. Energy is the parameter to tune: if the render
    comes out black or blown out, adjust `key_energy` against `distance` rather than
    rebuilding. Creates three new AREA lights without removing existing ones, so delete
    the scene's default light first.
    """
    return call("setup_three_point_lighting", target=target, distance=distance, height=height, key_energy=key_energy,
                fill_ratio=fill_ratio, rim_ratio=rim_ratio, color_temp=color_temp)


@mcp.tool(annotations=CREATE)
def setup_studio_scene(
    subject: Annotated[str | None, Field(description="Object to build the studio around; used to size and place the backdrop and aim the camera. Omit to build a generic studio at the origin.")] = None,
    backdrop: Annotated[bool, Field(description="true (default) adds a curved cyclorama wall that sweeps into the floor, removing the horizon line — the seamless white background of product photography.")] = True,
    ground: Annotated[bool, Field(description="true (default) adds a ground plane.")] = True,
    hdri_path: Annotated[str | None, Field(description="Absolute path to an HDRI for environment lighting instead of flat world colour. polyhaven_download can fetch one.")] = None,
    camera: Annotated[bool, Field(description="true (default) also creates and frames a camera on the subject.")] = True,
) -> dict:
    """Build a product-photography studio: backdrop, ground, lighting and a framed camera in one call.

    Gets you from a bare object to a renderable presentation shot immediately. Combine
    with setup_three_point_lighting for the lights and quick_product_render to shoot it.
    """
    return call("setup_studio_scene", subject=subject, backdrop=backdrop, ground=ground, hdri_path=hdri_path,
                camera=camera)


@mcp.tool(annotations=CREATE)
def turntable_animation(
    object: Annotated[str, Field(description="Object to spin. It is parented to a rotating empty, so the object's own transform is preserved.")],
    frames: Annotated[int, Field(description="Length of the animation in frames. At 24 fps, 120 frames is a 5-second rotation.")] = 120,
    revolutions: Annotated[float, Field(description="How many full turns over that span. 1.0 (default) gives a single clean loop.")] = 1.0,
    camera: Annotated[str | None, Field(description="Existing camera to use. Omit to create one and frame the subject.")] = None,
) -> dict:
    """Set up a looping turntable: the object rotates a full turn with linear interpolation and a cycling F-curve.

    The standard way to show a model from every side. Interpolation is set to LINEAR
    deliberately — Blender's default Bezier easing would make the spin visibly slow down
    and speed up at each end. Render it with render_animation.
    """
    return call("turntable_animation", object=object, frames=frames, revolutions=revolutions, camera=camera)


@mcp.tool(annotations=WRITES_FILE)
def quick_product_render(
    object: Annotated[str, Field(description="Object to photograph.")],
    output_path: Annotated[str, Field(description="Absolute path for the rendered PNG.")],
    resolution: Annotated[list[int] | None, Field(description="[width, height] in pixels. Defaults to the scene's current setting.")] = None,
    samples: Annotated[int, Field(description="Render samples. 64 is a good EEVEE default; raise for CYCLES, at proportional cost in time.")] = 64,
    engine: Annotated[str, Field(description="'BLENDER_EEVEE' (default, seconds) or 'CYCLES' (minutes, more accurate reflections and shadows).")] = "BLENDER_EEVEE",
) -> dict | Image:
    """Light, frame and render one object in a single call, returning the image to look at.

    The fastest path from 'I made a thing' to seeing whether it looks right — it sets up
    lighting and camera framing for you. It changes the scene's lights and camera, so use
    the individual tools when you have a lighting setup worth keeping. Allows up to 10
    minutes for the render.
    """
    return image_result(call("quick_product_render", timeout=LONG, object=object, output_path=output_path,
                             resolution=resolution, samples=samples, engine=engine))


@mcp.tool(annotations=CREATE)
def material_from_texture_folder(
    folder: Annotated[str, Field(description="Absolute path to a folder of texture images. Files are classified by keywords in their names: basecolor/albedo/diffuse/col, roughness/rough, metallic/metal, normal/nor, height/disp/displacement, ao/ambient.")],
    name: Annotated[str | None, Field(description="Name for the material. Defaults to the folder's name.")] = None,
    assign_to: Annotated[str | None, Field(description="Object to assign the finished material to.")] = None,
) -> dict:
    """Scan a folder of PBR textures, work out what each map is from its filename, and wire them into one material.

    Built for downloaded texture sets, which follow those naming conventions. Files that
    match nothing are ignored, so check the response to see which maps were actually
    found. Use create_pbr_material when you want to name each file path explicitly.
    """
    return call("material_from_texture_folder", folder=folder, name=name, assign_to=assign_to)


@mcp.tool(annotations=CREATE)
def scatter_objects(
    source: Annotated[str, Field(description="Object to scatter copies of, e.g. a rock or a tuft of grass.")],
    surface: Annotated[str, Field(description="Mesh object to scatter across — its faces define where instances can land.")],
    count: Annotated[int, Field(description="Approximate number of instances. With GEOMETRY_NODES this drives point density over the surface area, so it is a target rather than an exact count.")] = 100,
    seed: Annotated[int, Field(description="Random seed; the same seed reproduces the same arrangement exactly.")] = 0,
    scale_range: Annotated[list[float] | None, Field(description="[min, max] random scale multiplier per instance, e.g. [0.7, 1.3]. Size variation is what stops a scatter looking obviously copy-pasted.")] = None,
    align_to_normal: Annotated[bool, Field(description="true (default) tilts instances to follow the surface, so they sit flat on slopes. false keeps them all upright.")] = True,
    method: Annotated[str, Field(description="'GEOMETRY_NODES' (default) builds a live, non-destructive node setup you can tweak afterwards and which stays cheap at high counts. 'COLLECTION_INSTANCES' creates real duplicate objects, heavier but individually editable.")] = "GEOMETRY_NODES",
) -> dict:
    """Scatter many instances of one object across the surface of another — grass, rocks, debris.

    Instances are cheap: 10,000 geometry-node instances cost far less than 10,000 real
    objects. Use distribute_objects for exact geometric arrangements instead, and
    randomize_transform for jittering objects that already exist.
    """
    return call("scatter_objects", source=source, surface=surface, count=count, seed=seed, scale_range=scale_range,
                align_to_normal=align_to_normal, method=method)


@mcp.tool(annotations=WRITES_FILE)
def export_for_game(
    objects: Objects,
    path: Annotated[str, Field(description="Absolute destination file path.")],
    format: Annotated[str, Field(description="'GLB' (default, single self-contained file, the web and modern-engine standard) or 'FBX' (widely supported by Unity and Unreal).")] = "GLB",
    apply_modifiers: Annotated[bool, Field(description="true (default) bakes modifiers into real geometry, which game engines require since they cannot evaluate Blender's modifier stack.")] = True,
    triangulate: Annotated[bool, Field(description="true (default) converts quads and n-gons to triangles, matching what engines do anyway — doing it here means you see the actual result.")] = True,
    scale: Annotated[float, Field(description="Uniform scale factor applied on export. Use 100 when the target engine works in centimeters and your scene is in meters.")] = 1.0,
    forward: Annotated[str, Field(description="Which Blender axis becomes the target's forward: '-Z', 'Z', 'X', '-X', 'Y', '-Y'. Blender is Z-up while most engines are Y-up, which is why imported models arrive lying on their side.")] = "-Z",
    up: Annotated[str, Field(description="Which Blender axis becomes the target's up. 'Y' matches Unity, Unreal and glTF.")] = "Y",
) -> dict:
    """Export objects game-ready: modifiers applied, triangulated, scaled and axis-converted.

    Preferable to raw export_file for anything heading into a game engine, since it
    handles the three things that usually go wrong — unapplied modifiers, n-gons, and
    Blender's Z-up axis convention. Works on temporary copies, so your scene is left
    untouched.
    """
    return call("export_for_game", objects=objects, path=path, format=format, apply_modifiers=apply_modifiers,
                triangulate=triangulate, scale=scale, forward=forward, up=up)
