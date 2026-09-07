"""server 工具集合 == 插件非 internal 的 HANDLERS 集合；每个工具有描述。"""
import asyncio
import importlib
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _fake_bpy_modules() -> dict:
    """假 bpy/mathutils/bmesh，只够 handler 模块顶层 import 与类定义。"""
    def _any(*a, **k):
        return None

    class _Ns(types.SimpleNamespace):
        def __getattr__(self, name):  # 任何未知属性都给一个占位类型
            return type(name, (), {})

    bpy = types.ModuleType("bpy")
    bpy.ops = _Ns(ed=types.SimpleNamespace(undo_push=_any))
    bpy.app = types.SimpleNamespace(background=True, version_string="test",
                                    timers=types.SimpleNamespace(is_registered=lambda f: False))
    bpy.types = _Ns()
    bpy.data = types.SimpleNamespace()
    bpy.context = types.SimpleNamespace()
    bpy.props = _Ns(StringProperty=_any, IntProperty=_any, BoolProperty=_any, FloatProperty=_any)
    bpy.utils = types.SimpleNamespace(register_class=_any, unregister_class=_any)
    bpy.path = types.SimpleNamespace(abspath=lambda p: p)
    mathutils = types.ModuleType("mathutils")
    for n in ("Vector", "Euler", "Color", "Quaternion", "Matrix"):
        setattr(mathutils, n, type(n, (), {}))
    bmesh = types.ModuleType("bmesh")
    bmesh.ops = types.SimpleNamespace()
    bpy_extras = types.ModuleType("bpy_extras")
    bpy_extras.object_utils = types.SimpleNamespace()
    return {"bpy": bpy, "mathutils": mathutils, "bmesh": bmesh, "bpy_extras": bpy_extras,
            "bpy_extras.object_utils": bpy_extras.object_utils}


def addon_public_names() -> set[str]:
    fakes = _fake_bpy_modules()
    saved = {k: sys.modules.get(k) for k in fakes}
    sys.modules.update(fakes)
    try:
        spec = importlib.util.spec_from_file_location(
            "addon_pkg", ROOT / "addon" / "blender_mcp_pro" / "__init__.py",
            submodule_search_locations=[str(ROOT / "addon" / "blender_mcp_pro")])
        addon = importlib.util.module_from_spec(spec)
        sys.modules["addon_pkg"] = addon
        spec.loader.exec_module(addon)
        importlib.import_module("addon_pkg.handlers")
        registry = importlib.import_module("addon_pkg.registry")
        return set(registry.public_names())
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        for k in [k for k in sys.modules if k.startswith("addon_pkg")]:
            sys.modules.pop(k)


def test_server_tools_match_addon_handlers():
    from blender_mcp_pro import tools
    server_names = tools.tool_names()
    addon_names = addon_public_names()
    assert server_names == addon_names, (
        f"only in server: {sorted(server_names - addon_names)}\nonly in addon: {sorted(addon_names - server_names)}")


def test_every_tool_has_description():
    from blender_mcp_pro import tools  # noqa: F401
    from blender_mcp_pro.server import mcp
    missing = [t.name for t in asyncio.run(mcp.list_tools()) if not (t.description or "").strip()]
    assert not missing, missing
