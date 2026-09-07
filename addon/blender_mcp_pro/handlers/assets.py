"""Assets（插件侧 3 个本地工具；联网部分在 server）。"""
from __future__ import annotations

import os

import bpy

from ..registry import command
from ..utils import ToolError
from .io import append_from_blend

_TYPES = ("objects", "materials", "node_groups", "worlds", "collections", "meshes", "actions", "images", "lights", "cameras")


def _libs():
    return [(lib.name, os.path.abspath(bpy.path.abspath(lib.path))) for lib in bpy.context.preferences.filepaths.asset_libraries]


def _lib(name: str):
    for n, p in _libs():
        if n == name:
            return n, p
    raise ToolError(f"asset library '{name}' not found. Available: {', '.join(n for n, _ in _libs())}")


def _blends(root: str):
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".blend"):
                yield os.path.join(r, f)


@command("list_asset_libraries", mutates=False)
def list_asset_libraries():
    out = []
    for n, p in _libs():
        exists = os.path.isdir(p)
        out.append({"name": n, "path": p, "exists": exists, "blend_files": sum(1 for _ in _blends(p)) if exists else 0})
    return out


@command("search_local_assets", mutates=False)
def search_local_assets(library: str | None = None, type: str | None = None, query: str | None = None, assets_only: bool = True):
    libs = [_lib(library)] if library else _libs()
    types = [type] if type else list(_TYPES)
    for t in types:
        if t not in _TYPES:
            raise ToolError(f"unknown type '{t}'. Options: {', '.join(_TYPES)}")
    q = (query or "").lower()
    out = []
    for lname, root in libs:
        if not os.path.isdir(root):
            continue
        for blend in _blends(root):
            try:
                with bpy.data.libraries.load(blend, assets_only=assets_only) as (src, _):
                    found = {t: list(getattr(src, t)) for t in types}
            except Exception as e:  # noqa: BLE001
                out.append({"library": lname, "file": os.path.relpath(blend, root), "error": str(e)})
                continue
            for t, names in found.items():
                for n in names:
                    if q and q not in n.lower():
                        continue
                    out.append({"library": lname, "file": os.path.relpath(blend, root), "type": t, "name": n})
    return out


@command("import_local_asset")
def import_local_asset(library: str, name: str, type: str = "objects", link: bool = False, file: str | None = None):
    lname, root = _lib(library)
    if type not in _TYPES:
        raise ToolError(f"unknown type '{type}'. Options: {', '.join(_TYPES)}")
    if file:
        candidates = [os.path.join(root, file)]
    else:
        candidates = []
        for blend in _blends(root):
            with bpy.data.libraries.load(blend, assets_only=False) as (src, _):
                if name in getattr(src, type):
                    candidates.append(blend)
    if not candidates:
        raise ToolError(f"{type} '{name}' not found in library '{lname}'")
    r = append_from_blend(candidates[0], type, name, link)
    r["library"] = lname
    return r
