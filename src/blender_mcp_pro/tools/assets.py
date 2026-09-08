"""Assets — Poly Haven and Sketchfab downloads, plus local Blender asset libraries."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

import os
import zipfile

from ..assets import polyhaven, sketchfab
from ..assets.cache import cache_path
from ..server import mcp
from ._base import LONG, call, surface_errors
from ._types import CREATE, NET_READ, NET_WRITE, READ_ONLY

_ASSET_TYPE_DOC = (
    "'hdris' (environment maps that light the whole scene), 'textures' (PBR map sets) or 'models' (ready-made 3D "
    "objects)."
)


@mcp.tool(annotations=NET_READ)
@surface_errors
def polyhaven_categories(
    asset_type: Annotated[str, Field(description=_ASSET_TYPE_DOC)] = "hdris",
) -> dict:
    """List Poly Haven's categories for one asset type, with how many assets each holds.

    Poly Haven is a free CC0 library, so anything here can be used without attribution.
    Use the category names to narrow polyhaven_search. Requires internet access.
    """
    return polyhaven.categories(asset_type)


@mcp.tool(annotations=NET_READ)
@surface_errors
def polyhaven_search(
    asset_type: Annotated[str, Field(description=_ASSET_TYPE_DOC)] = "hdris",
    categories: Annotated[list[str] | None, Field(description="Category names to filter by, e.g. ['outdoor'], ['sunrise'], ['wood']. Get valid names from polyhaven_categories.")] = None,
    query: Annotated[str | None, Field(description="Case-insensitive substring matched against asset ids and names.")] = None,
    limit: Annotated[int, Field(description="Maximum results to return.")] = 20,
) -> list[dict]:
    """Search Poly Haven's free CC0 asset library, returning asset ids you can pass to polyhaven_download.

    The fastest route to realistic lighting or materials without making them by hand:
    search 'hdris' for an environment, 'textures' for a PBR set. Requires internet access.
    """
    return polyhaven.search(asset_type, categories, query, limit)


@mcp.tool(annotations=NET_WRITE)
@surface_errors
def polyhaven_download(
    asset_id: Annotated[str, Field(description="Asset id from polyhaven_search, e.g. 'kloofendal_48d_partly_cloudy_puresky'.")],
    asset_type: Annotated[str, Field(description=_ASSET_TYPE_DOC)],
    resolution: Annotated[str, Field(description="'1k' (default, fast, fine for previews and background), '2k', '4k' or '8k'. Higher resolutions are large downloads and slow to load — 4k HDRIs run to tens of megabytes.")] = "1k",
    file_format: Annotated[str | None, Field(description="Override the default file format ('hdr' or 'exr' for HDRIs, 'jpg' or 'png' for textures, 'gltf' for models).")] = None,
) -> dict:
    """Download a Poly Haven asset and install it into the scene: HDRIs become the world lighting, textures become a PBR material, models are imported as objects.

    Not just a download — it wires the result up for you, so one call takes you from
    'no lighting' to a lit scene. Files are cached in ~/.cache/blender-mcp-pro/, so
    re-downloading the same asset is instant. Needs internet; the call allows up to 10
    minutes for large files.
    """
    info = polyhaven.download_asset(asset_id, asset_type, resolution, file_format)
    files = info["files"]
    if info["type"] == "hdris":
        info["result"] = call("set_world_lighting", hdri_path=files["hdri"])
    elif info["type"] == "textures":
        info["result"] = call("create_pbr_material", name=asset_id, base_color=files.get("base_color"),
                              roughness=files.get("roughness"), metallic=files.get("metallic"),
                              normal=files.get("normal"), height=files.get("height"), ao=files.get("ao"))
    else:
        info["result"] = call("import_file", timeout=LONG, path=files["model"])
    return info


@mcp.tool(annotations=NET_READ)
@surface_errors
def sketchfab_search(
    query: Annotated[str, Field(description="Search terms, e.g. 'wooden chair', 'sci-fi crate'.")],
    categories: Annotated[list[str] | None, Field(description="Sketchfab category slugs to narrow the search.")] = None,
    count: Annotated[int, Field(description="Maximum results to return.")] = 20,
    downloadable: Annotated[bool, Field(description="true (default) restricts results to models you can actually download. Most Sketchfab models are view-only, so leaving this on avoids results you cannot use.")] = True,
) -> list[dict]:
    """Search Sketchfab for 3D models, returning uids for sketchfab_download.

    Requires a Sketchfab API token configured in the add-on preferences (Blender ▸ Edit ▸
    Preferences ▸ Add-ons ▸ Blender MCP Pro); get_blender_info reports whether one is set.
    Licences vary per model, unlike Poly Haven's blanket CC0 — check before using
    commercially.
    """
    return sketchfab.search(query, categories, count, downloadable)


@mcp.tool(annotations=NET_WRITE)
@surface_errors
def sketchfab_download(
    uid: Annotated[str, Field(description="Model uid from sketchfab_search.")],
) -> dict:
    """Download a Sketchfab model as GLB and import it into the current scene.

    Needs a configured Sketchfab API token and a model whose owner allows downloading.
    Imported models arrive at their author's scale and orientation, which is often wrong
    for your scene — check with get_bounding_box and fix with set_transform.
    """
    token = call("get_secret", key="sketchfab_token") or os.environ.get("SKETCHFAB_API_TOKEN")
    if not token:
        raise ValueError("Missing Sketchfab API token: set it in Blender > Preferences > Add-ons > "
                         "Blender MCP Pro, or via the SKETCHFAB_API_TOKEN environment variable")
    info = sketchfab.download_model(uid, token)
    path = info["path"]
    if info["format"] == "zip":
        folder = cache_path("sketchfab", uid)
        with zipfile.ZipFile(path) as z:
            z.extractall(folder)
        gltfs = [os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs if f.endswith((".gltf", ".glb"))]
        if not gltfs:
            raise ValueError("archive contains no glTF")
        path = gltfs[0]
    info["result"] = call("import_file", timeout=LONG, path=path)
    return info


@mcp.tool(annotations=READ_ONLY)
def list_asset_libraries() -> list[dict]:
    """List the asset libraries configured in this Blender's preferences, with their names and folder paths.

    Entirely local, no network. These are the user's own asset folders; if the list is
    empty, none have been set up in Blender's Preferences ▸ File Paths.
    """
    return call("list_asset_libraries")


@mcp.tool(annotations=READ_ONLY)
def search_local_assets(
    library: Annotated[str | None, Field(description="Library name from list_asset_libraries. Omit to search all of them.")] = None,
    type: Annotated[str | None, Field(description="Datablock category: 'objects', 'materials', 'node_groups', 'worlds', 'collections'.")] = None,
    query: Annotated[str | None, Field(description="Case-insensitive substring matched against datablock names.")] = None,
    assets_only: Annotated[bool, Field(description="true (default) returns only datablocks explicitly marked as assets in Blender. false also lists everything else in those .blend files.")] = True,
) -> list[dict]:
    """Search the user's local asset libraries for objects, materials or node groups to reuse.

    Local and offline — this is the equivalent of Poly Haven for the user's own saved
    work. Returns the library, file and datablock name that import_local_asset needs.
    """
    return call("search_local_assets", library=library, type=type, query=query, assets_only=assets_only)


@mcp.tool(annotations=CREATE)
def import_local_asset(
    library: Annotated[str, Field(description="Library name containing the asset.")],
    name: Annotated[str, Field(description="Exact datablock name from search_local_assets.")],
    type: Annotated[str, Field(description="Datablock category: 'objects', 'materials', 'node_groups', 'worlds', 'collections'.")] = "objects",
    link: Annotated[bool, Field(description="false (default) appends an independent copy. true links it, keeping it owned by the source file — updates propagate but the asset is read-only here and breaks if the source moves.")] = False,
    file: Annotated[str | None, Field(description="Specific .blend file within the library, when the same name appears in several. search_local_assets reports which file each result came from.")] = None,
) -> dict:
    """Bring an object, material or node group from a local asset library into the current scene.

    The offline counterpart to polyhaven_download. Appending copies the data in;
    dependencies (meshes, materials, textures) come along with it.
    """
    return call("import_local_asset", library=library, name=name, type=type, link=link, file=file)
