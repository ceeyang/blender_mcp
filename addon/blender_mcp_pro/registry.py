"""工具注册表。handler 签名：fn(**params) -> JSON 可序列化对象。"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Callable

import bpy


@dataclass
class Handler:
    name: str
    fn: Callable[..., Any]
    internal: bool = False
    mutates: bool = True


HANDLERS: dict[str, Handler] = {}


def command(name: str, *, internal: bool = False, mutates: bool = True):
    def deco(fn):
        if name in HANDLERS:
            raise RuntimeError(f"duplicate handler: {name}")
        HANDLERS[name] = Handler(name, fn, internal, mutates)
        return fn
    return deco


def public_names() -> set[str]:
    return {n for n, h in HANDLERS.items() if not h.internal}


def dispatch(tool: str, params: dict) -> dict:
    """在主线程调用。返回响应体（不含 id）。"""
    h = HANDLERS.get(tool)
    if h is None:
        return {"ok": False, "error": {"type": "UnknownTool", "message": f"unknown tool '{tool}'", "traceback": ""}}
    try:
        result = h.fn(**(params or {}))
        if h.mutates:
            try:
                bpy.ops.ed.undo_push(message=f"mcp: {tool}")
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "result": result}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }}
