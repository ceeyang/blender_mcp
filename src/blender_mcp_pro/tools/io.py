"""Import/Export。"""
from __future__ import annotations

from ..server import mcp
from ._base import LONG, call


@mcp.tool()
def import_file(path: str, format: str | None = None, options: dict | None = None, collection: str | None = None) -> dict:
    """导入文件（obj/fbx/gltf/glb/usd/usda/usdc/stl/ply/abc/blend，按后缀识别）。options 透传给导入算子。返回新增对象名。"""
    return call("import_file", timeout=LONG, path=path, format=format, options=options, collection=collection)


@mcp.tool()
def export_file(path: str, format: str | None = None, objects: list[str] | dict | str | None = None, options: dict | None = None) -> dict:
    """导出到文件（同上格式）。objects 省略则导出全部。"""
    return call("export_file", timeout=LONG, path=path, format=format, objects=objects, options=options)


@mcp.tool()
def append_from_blend(path: str, datablock: str, name: str, link: bool = False) -> dict:
    """从 .blend 追加/链接一个数据块（objects/materials/collections/node_groups/actions/…）。"""
    return call("append_from_blend", path=path, datablock=datablock, name=name, link=link)


@mcp.tool()
def save_blend(path: str | None = None, compress: bool = False) -> dict:
    """保存当前文件（给 path 即另存为）。"""
    return call("save_blend", path=path, compress=compress)


@mcp.tool()
def open_blend(path: str, load_ui: bool = False) -> dict:
    """打开 .blend 文件。"""
    return call("open_blend", timeout=LONG, path=path, load_ui=load_ui)
