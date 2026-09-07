"""Poly Haven 公开 API（无需密钥）。"""
from __future__ import annotations

from .cache import cache_path, client, download

API = "https://api.polyhaven.com"
_TYPES = {"hdri": "hdris", "hdris": "hdris", "texture": "textures", "textures": "textures", "model": "models", "models": "models"}
_TEXTURE_MAPS = {"Diffuse": "base_color", "Rough": "roughness", "nor_gl": "normal", "Displacement": "height", "AO": "ao",
                 "Metal": "metallic"}


def norm_type(asset_type: str) -> str:
    t = _TYPES.get(asset_type.lower())
    if t is None:
        raise ValueError(f"asset_type must be hdris/textures/models, got '{asset_type}'")
    return t


def categories(asset_type: str = "hdris") -> dict:
    with client() as c:
        r = c.get(f"{API}/categories/{norm_type(asset_type)}")
        r.raise_for_status()
        return r.json()


def search(asset_type: str = "hdris", categories: list[str] | None = None, query: str | None = None, limit: int = 20) -> list[dict]:
    params = {"t": norm_type(asset_type)}
    if categories:
        params["c"] = ",".join(categories)
    with client() as c:
        r = c.get(f"{API}/assets", params=params)
        r.raise_for_status()
        data = r.json()
    out = []
    q = (query or "").lower()
    for aid, info in data.items():
        hay = " ".join([aid, info.get("name", ""), " ".join(info.get("tags", [])), " ".join(info.get("categories", []))]).lower()
        if q and q not in hay:
            continue
        out.append({"id": aid, "name": info.get("name"), "categories": info.get("categories", []), "tags": info.get("tags", [])[:12],
                    "download_count": info.get("download_count", 0), "authors": list(info.get("authors", {}).keys())})
    out.sort(key=lambda d: -d["download_count"])
    return out[:limit]


def files(asset_id: str) -> dict:
    with client() as c:
        r = c.get(f"{API}/files/{asset_id}")
        r.raise_for_status()
        return r.json()


def pick_files(asset_id: str, files_json: dict, asset_type: str, resolution: str = "1k", file_format: str | None = None) -> list[dict]:
    """纯函数：从 /files 响应里挑出要下载的项 → [{url, relpath, role}]。"""
    t = norm_type(asset_type)
    if t == "hdris":
        node = files_json.get("hdri", {})
        if resolution not in node:
            raise ValueError(f"resolution '{resolution}' not available; options: {', '.join(node)}")
        fmts = node[resolution]
        fmt = file_format or ("hdr" if "hdr" in fmts else next(iter(fmts)))
        if fmt not in fmts:
            raise ValueError(f"format '{fmt}' not available; options: {', '.join(fmts)}")
        return [{"url": fmts[fmt]["url"], "relpath": f"hdris/{asset_id}_{resolution}.{fmt}", "role": "hdri"}]
    if t == "textures":
        out = []
        for key, role in _TEXTURE_MAPS.items():
            node = files_json.get(key)
            if not node or resolution not in node:
                continue
            fmts = node[resolution]
            for fmt in ([file_format] if file_format else []) + ["jpg", "png", "exr"]:
                if fmt in fmts:
                    out.append({"url": fmts[fmt]["url"], "relpath": f"textures/{asset_id}/{asset_id}_{resolution}_{role}.{fmt}", "role": role})
                    break
        if not out:
            raise ValueError(f"no texture maps at resolution '{resolution}'; available: {sorted(k for k in files_json if k in _TEXTURE_MAPS)}")
        return out
    node = files_json.get("gltf", {})
    if resolution not in node:
        raise ValueError(f"resolution '{resolution}' not available for model; options: {', '.join(node)}")
    main = node[resolution]["gltf"]
    out = [{"url": main["url"], "relpath": f"models/{asset_id}/{asset_id}.gltf", "role": "model"}]
    for rel, inc in (main.get("include") or {}).items():
        out.append({"url": inc["url"], "relpath": f"models/{asset_id}/{rel}", "role": "include"})
    return out


def download_asset(asset_id: str, asset_type: str, resolution: str = "1k", file_format: str | None = None) -> dict:
    items = pick_files(asset_id, files(asset_id), asset_type, resolution, file_format)
    paths = {}
    with client(timeout=120.0) as c:
        for it in items:
            p = download(it["url"], cache_path(*it["relpath"].split("/")), c)
            paths.setdefault(it["role"], str(p))
    return {"asset": asset_id, "type": norm_type(asset_type), "resolution": resolution, "files": paths, "count": len(items)}
