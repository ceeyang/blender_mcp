"""blender-mcp-pro 命令行：serve / install-addon / uninstall-addon / dump-tools"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDON_SRC = ROOT / "addon" / "blender_mcp_pro"
EXT_DIR = pathlib.Path.home() / "Library" / "Application Support" / "Blender" / "5.2" / "extensions" / "user_default"
BLENDER = os.environ.get("BLENDER_MCP_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
MODULE = "bl_ext.user_default.blender_mcp_pro"


def _blender_python(expr: str) -> int:
    return subprocess.call([BLENDER, "-b", "--python-expr", expr])


def install_addon(copy: bool) -> int:
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    dst = EXT_DIR / "blender_mcp_pro"
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    if copy:
        shutil.copytree(ADDON_SRC, dst, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        dst.symlink_to(ADDON_SRC, target_is_directory=True)
    print(f"{'copied' if copy else 'linked'} {ADDON_SRC} -> {dst}")
    return _blender_python(
        "import bpy;"
        "bpy.ops.extensions.repo_refresh_all();"
        f"bpy.ops.preferences.addon_enable(module='{MODULE}');"
        "bpy.ops.wm.save_userpref();"
        f"print('enabled:', '{MODULE}' in bpy.context.preferences.addons)"
    )


def uninstall_addon() -> int:
    _blender_python(
        "import bpy;"
        f"('{MODULE}' in bpy.context.preferences.addons) and bpy.ops.preferences.addon_disable(module='{MODULE}');"
        "bpy.ops.wm.save_userpref()"
    )
    dst = EXT_DIR / "blender_mcp_pro"
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    print(f"removed {dst}")
    return 0


def dump_tools() -> int:
    from . import tools  # noqa: F401
    from .server import mcp
    listed = sorted(asyncio.run(mcp.list_tools()), key=lambda t: t.name)
    lines = ["# 工具清单", "", f"共 {len(listed)} 个。由 `uv run blender-mcp-pro dump-tools > docs/tools.md` 生成，不要手改。", ""]
    for t in listed:
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", {}) or {}
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        params = ", ".join(f"{k}{'' if k in req else '?'}" for k in props)
        desc = (t.description or "").strip().splitlines()[0] if t.description else ""
        lines.append(f"- **{t.name}**({params}) — {desc}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="blender-mcp-pro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="以 stdio 运行 MCP server")
    ia = sub.add_parser("install-addon", help="把 addon 软链进 Blender 5.2 extensions 并启用")
    ia.add_argument("--copy", action="store_true", help="复制而非软链")
    sub.add_parser("uninstall-addon")
    sub.add_parser("dump-tools", help="输出工具清单 markdown")
    args = ap.parse_args(argv)
    if args.cmd == "serve":
        from .server import main as serve
        serve()
        return 0
    if args.cmd == "install-addon":
        return install_addon(args.copy)
    if args.cmd == "uninstall-addon":
        return uninstall_addon()
    if args.cmd == "dump-tools":
        return dump_tools()
    return 1


if __name__ == "__main__":
    sys.exit(main())
