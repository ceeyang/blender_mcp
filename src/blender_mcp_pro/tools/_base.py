from __future__ import annotations

import base64
from typing import Any

from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

from ..connection import get_connection
from ..errors import BlenderError, BlenderTimeout, BlenderUnavailable

LONG = 600.0


def call(tool: str, timeout: float = 60.0, **params: Any) -> Any:
    """转发到插件。mcp 2.x 会把普通异常吞成 "Error executing tool"，只有 ToolError 的消息会原样透传给模型。"""
    clean = {k: v for k, v in params.items() if v is not None}
    try:
        return get_connection().call(tool, clean, timeout=timeout)
    except BlenderError as e:
        raise ToolError(f"{e.type}: {e.message}") from e
    except (BlenderUnavailable, BlenderTimeout) as e:
        raise ToolError(str(e)) from e


def surface_errors(fn):
    """给不走 call() 的工具（资产联网）用：把任何异常消息透传给模型。"""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except ToolError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"{type(e).__name__}: {e}") from e
    return wrapper


def image_result(result: Any) -> Any:
    """handler 返回 {"image_base64", "mime", ...} 时转成 MCP Image；否则原样返回。"""
    if isinstance(result, dict) and result.get("image_base64"):
        fmt = "png" if result.get("mime", "image/png").endswith("png") else "jpeg"
        return Image(data=base64.b64decode(result["image_base64"]), format=fmt)
    return result
