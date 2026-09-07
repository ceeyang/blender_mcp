"""Sketchfab v3 API。搜索无需密钥，下载需要 API token（插件偏好或 SKETCHFAB_API_TOKEN）。"""
from __future__ import annotations

from .cache import cache_path, client, download

API = "https://api.sketchfab.com/v3"


def search(query: str, categories: list[str] | None = None, count: int = 20, downloadable: bool = True) -> list[dict]:
    params = {"type": "models", "q": query, "count": min(max(int(count), 1), 24), "downloadable": str(bool(downloadable)).lower()}
    if categories:
        params["categories"] = ",".join(categories)
    with client() as c:
        r = c.get(f"{API}/search", params=params)
        r.raise_for_status()
        data = r.json()
    out = []
    for m in data.get("results", []):
        thumbs = (m.get("thumbnails") or {}).get("images") or []
        out.append({"uid": m.get("uid"), "name": m.get("name"), "user": (m.get("user") or {}).get("displayName"),
                    "license": (m.get("license") or {}).get("label"), "face_count": m.get("faceCount"),
                    "vertex_count": m.get("vertexCount"), "is_downloadable": m.get("isDownloadable"),
                    "thumbnail": thumbs[0]["url"] if thumbs else None, "url": m.get("viewerUrl")})
    return out


def download_model(uid: str, token: str) -> dict:
    headers = {"Authorization": f"Token {token}"}
    with client() as c:
        r = c.get(f"{API}/models/{uid}/download", headers=headers)
        if r.status_code in (401, 403):
            raise PermissionError("Sketchfab rejected the API token (or the model is not downloadable)")
        r.raise_for_status()
        info = r.json()
    if "glb" in info:
        url, ext = info["glb"]["url"], "glb"
    elif "gltf" in info:
        url, ext = info["gltf"]["url"], "zip"
    else:
        raise ValueError(f"no downloadable format for {uid}: {list(info)}")
    path = download(url, cache_path("sketchfab", f"{uid}.{ext}"))
    return {"uid": uid, "path": str(path), "format": ext}
