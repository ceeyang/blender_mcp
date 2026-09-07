"""Assets：Poly Haven / Sketchfab（联网，只在 server 进程）+ 本地资产库。"""
from __future__ import annotations

import os
import zipfile

from ..assets import polyhaven, sketchfab
from ..assets.cache import cache_path
from ..server import mcp
from ._base import LONG, call


@mcp.tool()
def polyhaven_categories(asset_type: str = "hdris") -> dict:
    """Poly Haven 分类及数量。asset_type: hdris/textures/models。"""
    return polyhaven.categories(asset_type)


@mcp.tool()
def polyhaven_search(asset_type: str = "hdris", categories: list[str] | None = None, query: str | None = None, limit: int = 20) -> list[dict]:
    """搜索 Poly Haven 资产（按分类/关键词），按下载量排序。"""
    return polyhaven.search(asset_type, categories, query, limit)


@mcp.tool()
def polyhaven_download(asset_id: str, asset_type: str, resolution: str = "1k", file_format: str | None = None) -> dict:
    """下载 Poly Haven 资产并导入：HDRI→世界光；纹理→PBR 材质；模型→导入场景。resolution: 1k/2k/4k/8k。"""
    info = polyhaven.download_asset(asset_id, asset_type, resolution, file_format)
    files = info["files"]
    if info["type"] == "hdris":
        info["result"] = call("set_world_lighting", hdri_path=files["hdri"])
    elif info["type"] == "textures":
        info["result"] = call("create_pbr_material", name=asset_id, base_color=files.get("base_color"), roughness=files.get("roughness"),
                              metallic=files.get("metallic"), normal=files.get("normal"), height=files.get("height"), ao=files.get("ao"))
    else:
        info["result"] = call("import_file", timeout=LONG, path=files["model"])
    return info


@mcp.tool()
def sketchfab_search(query: str, categories: list[str] | None = None, count: int = 20, downloadable: bool = True) -> list[dict]:
    """搜索 Sketchfab 模型。"""
    return sketchfab.search(query, categories, count, downloadable)


@mcp.tool()
def sketchfab_download(uid: str) -> dict:
    """下载 Sketchfab 模型（glb）并导入。需要在插件偏好里填 Sketchfab API token（或环境变量 SKETCHFAB_API_TOKEN）。"""
    token = call("get_secret", key="sketchfab_token") or os.environ.get("SKETCHFAB_API_TOKEN")
    if not token:
        raise ValueError("缺少 Sketchfab API token：Blender ▸ Preferences ▸ Add-ons ▸ Blender MCP Pro 里填写，或设置 SKETCHFAB_API_TOKEN")
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


@mcp.tool()
def list_asset_libraries() -> list[dict]:
    """Blender 偏好里配置的本地资产库。"""
    return call("list_asset_libraries")


@mcp.tool()
def search_local_assets(library: str | None = None, type: str | None = None, query: str | None = None, assets_only: bool = True) -> list[dict]:
    """搜索本地资产库里的数据块。type: objects/materials/node_groups/worlds/collections/meshes/actions。"""
    return call("search_local_assets", timeout=LONG, library=library, type=type, query=query, assets_only=assets_only)


@mcp.tool()
def import_local_asset(library: str, name: str, type: str = "objects", link: bool = False, file: str | None = None) -> dict:
    """从本地资产库导入数据块（file 可指定库内 .blend 相对路径）。"""
    return call("import_local_asset", timeout=LONG, library=library, name=name, type=type, link=link, file=file)
