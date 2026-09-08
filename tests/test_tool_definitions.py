"""工具定义本身的质量与正确性检查（不需要 Blender）。

TDQS（Glama 的 Tool Definition Quality Score）里能被确定性计算的那部分：参数描述覆盖率、
annotations、描述长度、tautology。加上一条静态检查，防止改描述时把函数体里的调用改错——
联网工具的测试默认 skip，这类错误跑测试是发现不了的。
"""
from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import pathlib

import pytest

from blender_mcp_pro import tools  # noqa: F401  注册全部工具
from blender_mcp_pro.server import mcp

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "blender_mcp_pro" / "tools"


def _listed():
    return asyncio.run(mcp.list_tools())


def test_every_tool_declares_annotations():
    """annotations 是 MCP 客户端判断只读/破坏性的唯一结构化信号，也是 TDQS 的确定性输入。"""
    missing = [t.name for t in _listed() if t.annotations is None]
    assert not missing, f"缺少 annotations: {missing}"


def test_annotations_are_self_consistent():
    """只读工具不能同时标成破坏性。"""
    bad = [t.name for t in _listed()
           if t.annotations and t.annotations.read_only_hint and t.annotations.destructive_hint]
    assert not bad, f"同时标了 read_only 和 destructive: {bad}"


def test_every_parameter_is_documented():
    """TDQS 的 Parameter Semantics：覆盖率低于 50% 直接判 1-2 分。"""
    bad = []
    for t in _listed():
        props = (t.input_schema or {}).get("properties", {}) or {}
        undocumented = [k for k, v in props.items() if not (v.get("description") or "").strip()]
        if undocumented:
            bad.append(f"{t.name}: {undocumented}")
    assert not bad, "参数缺描述:\n" + "\n".join(bad)


def test_descriptions_are_substantial():
    """短到只是复述工具名的描述会被判 tautology，Purpose Clarity 被 cap 在 2 分。"""
    thin = [(t.name, len(t.description or "")) for t in _listed() if len((t.description or "").strip()) < 80]
    assert not thin, f"描述过短: {thin}"


def test_descriptions_are_not_tautological():
    bad = [t.name for t in _listed()
           if (t.description or "").strip().lower().rstrip(".") == t.name.replace("_", " ")]
    assert not bad, f"描述只是复述工具名: {bad}"


def _module_level_imports(tree: ast.Module) -> set[str]:
    """`from ..assets import polyhaven` → {"polyhaven"}；`import os` → {"os"}。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


@pytest.mark.parametrize("path", sorted(TOOLS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_calls_into_imported_modules_resolve(path: pathlib.Path):
    """静态检查 `module.attr(...)`：属性存在，且实参个数能绑定到它的签名。

    抓得住：属性名写错、参数个数对不上。
    **抓不住**：名字存在、参数个数也一样，只是语义不同——真发生过一次，把
    polyhaven.download_asset(asset_id, asset_type, resolution, file_format) 写成
    polyhaven.download(url, dest, c, headers)，两个都是 4 参数，静态绑得上。
    那一类由 test_assets_download.py 的 mock 调用链兜住。
    """
    tree = ast.parse(path.read_text())
    imported = _module_level_imports(tree)
    mod = importlib.import_module(f"blender_mcp_pro.tools.{path.stem}")
    problems = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        owner = node.func.value
        if not (isinstance(owner, ast.Name) and owner.id in imported):
            continue
        target = getattr(mod, owner.id, None)
        if not inspect.ismodule(target):
            continue
        fn = getattr(target, node.func.attr, None)
        if fn is None:
            problems.append(f"line {node.lineno}: {owner.id}.{node.func.attr} 不存在")
            continue
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            continue  # *args / **kwargs 展开，静态绑不了
        try:
            sig.bind(*[object()] * len(node.args), **{k.arg: object() for k in node.keywords})
        except TypeError as e:
            problems.append(f"line {node.lineno}: {owner.id}.{node.func.attr}{sig} 绑不上实参 — {e}")
    assert not problems, f"{path.name}:\n  " + "\n  ".join(problems)
