from __future__ import annotations

import base64
from typing import Any

from mcp.server.mcpserver import Image

from ..connection import get_connection

LONG = 600.0


def call(tool: str, timeout: float = 60.0, **params: Any) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    return get_connection().call(tool, clean, timeout=timeout)


def image_result(result: Any) -> Any:
    """handler 返回 {"image_base64", "mime", ...} 时转成 MCP Image；否则原样返回。"""
    if isinstance(result, dict) and result.get("image_base64"):
        fmt = "png" if result.get("mime", "image/png").endswith("png") else "jpeg"
        return Image(data=base64.b64decode(result["image_base64"]), format=fmt)
    return result
