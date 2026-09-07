from __future__ import annotations

import os
import pathlib

import httpx

CACHE_DIR = pathlib.Path(os.environ.get("BLENDER_MCP_CACHE", pathlib.Path.home() / ".cache" / "blender-mcp-pro"))
UA = {"User-Agent": "blender-mcp-pro/0.1 (local)"}


def cache_path(*parts: str) -> pathlib.Path:
    p = CACHE_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def client(timeout: float = 60.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=UA)


def download(url: str, dest: pathlib.Path, c: httpx.Client | None = None, headers: dict | None = None) -> pathlib.Path:
    """流式下载到 dest；已存在且非空则直接复用。"""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    own = c is None
    c = c or client(timeout=120.0)
    try:
        with c.stream("GET", url, headers=headers or {}) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    f.write(chunk)
    finally:
        if own:
            c.close()
    tmp.replace(dest)
    return dest
