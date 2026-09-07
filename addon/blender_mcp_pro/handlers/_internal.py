"""内部命令：不暴露为 MCP 工具。"""
import bpy

from .. import ADDON_VERSION
from ..registry import command


@command("ping", internal=True, mutates=False)
def ping():
    return {"blender": bpy.app.version_string, "addon": ADDON_VERSION, "background": bpy.app.background}


@command("reset_scene", internal=True, mutates=False)
def reset_scene():
    if bpy.context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    bpy.ops.wm.read_factory_settings()
    return {"objects": [o.name for o in bpy.data.objects]}


@command("shutdown", internal=True, mutates=False)
def shutdown():
    from .. import server
    srv = server._server
    if srv is not None:
        srv.stopped = True
    return {"stopping": True}


@command("get_secret", internal=True, mutates=False)
def get_secret(key: str):
    from ..server import _prefs
    p = _prefs()
    if p is None:
        return None
    return getattr(p, key, None) or None
