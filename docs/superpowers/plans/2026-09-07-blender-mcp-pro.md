# blender-mcp-pro（本地自研版）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本机复刻 blender-mcp-pro 的 17 类 159 个工具，让 Claude Code 通过 MCP 驱动本地 Blender 5.2 LTS。

**Architecture:** 「胖 addon + 薄 server」。Blender 5.2 extension 内含全部 bpy 逻辑，监听 `127.0.0.1:9877`（长度前缀 JSON 帧），请求在主线程串行执行；Python MCP server（FastMCP，stdio）每个工具只做「类型化签名 → JSON 转发」。集成测试用 `Blender -b` 无头拉起插件跑真实 socket。

**Tech Stack:** Python 3.11（uv 管理，server 侧）/ Python 3.13（Blender 内置，addon 侧）；`mcp[cli]`、`httpx`、`pytest`；Blender 5.2.1 LTS `/Applications/Blender.app/Contents/MacOS/Blender`。

规格：`docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md`（下称 spec）。

## Global Constraints

- 只支持 Blender 5.2 LTS；`blender_manifest.toml` 中 `blender_version_min = "5.2.0"`。不写 4.x 兼容分支。
- 插件进程零联网；联网只允许出现在 `src/blender_mcp_pro/assets/`。
- 帧格式：4 字节大端无符号长度 + UTF-8 JSON；单帧上限 64 MiB。
- 请求 `{"id","tool","params"}`；响应 `{"id","ok":true,"result"}` 或 `{"id","ok":false,"error":{"type","message","traceback"}}`。
- 内部命令 `ping / reset_scene / shutdown / get_secret` 用 `internal=True` 注册，不暴露为 MCP 工具，不计入对账。
- 位置/旋转/缩放 `[x,y,z]`，旋转为弧度；颜色 `[r,g,b]` 或 `[r,g,b,a]`，0–1。
- 凡接受 `objects` 的工具：`list[str]` 或 `{"pattern"}` / `{"collection"}` / `{"type"}` / `{"selected": true}` 之一，统一走 `utils.resolve_objects`。
- 写操作 handler 执行后 `bpy.ops.ed.undo_push(message="mcp: <tool>")`（由 registry 按 `mutates` 标志统一做）。
- server 侧默认超时 60 s；`render_image / render_animation / bake_texture / bake_animation / generate_rigify_rig / polyhaven_download / sketchfab_download` 600 s。
- **无头模式下 `bpy.app.timers` 不触发**（已实测）：GUI 用 timer 驱动 `drain_once()`，测试 boot 脚本自己在主线程循环调用。
- 5.2 新材质默认 `use_nodes=True` 且自带 `Principled BSDF` + `Material Output`；不要再写 `use_nodes = True`（6.0 移除，5.2 打 DeprecationWarning）。
- Principled BSDF 插槽名用 5.2 的：`Base Color, Metallic, Roughness, IOR, Alpha, Normal, Subsurface Weight, Specular IOR Level, Specular Tint, Transmission Weight, Coat Weight, Sheen Weight, Emission Color, Emission Strength`。
- Git：一个任务完成、测试绿即 `git add <具体文件>` + commit；永不 `git add -A`；永不 push；commit message 不带署名。
- 临时产物放项目 `tmp/`（已 gitignore）。
- 提交前跑 `uv run pytest -q`（集成测试自动拉起无头 Blender，约 10 s 启动）。

## 文件结构

```
pyproject.toml
src/blender_mcp_pro/
  __init__.py            版本号
  connection.py          BlenderConnection + get_connection()（Task 2）
  errors.py              BlenderError / BlenderUnavailable / BlenderTimeout（Task 2）
  server.py              mcp = FastMCP(...)；main()（Task 5）
  cli.py                 serve / install-addon / uninstall-addon / dump-tools（Task 6）
  tools/__init__.py      import 全部类目；tool_names()（Task 5）
  tools/_base.py         call() / LONG / image_result()（Task 5）
  tools/<类目>.py        Task 7–23
  assets/cache.py polyhaven.py sketchfab.py（Task 22）
addon/blender_mcp_pro/
  blender_manifest.toml  （Task 1）
  __init__.py            register/unregister、Preferences、N 面板（Task 1 骨架，Task 6 完善）
  protocol.py            帧编解码（Task 2）
  registry.py            command 装饰器、HANDLERS（Task 3）
  utils.py               查找/序列化/mode/set_props/rna_props（Task 3）
  server.py              BlenderTCPServer、start/stop/drain_once（Task 3）
  nodes_common.py        节点树共用操作（Task 10）
  handlers/__init__.py   import 全部类目（Task 3）
  handlers/_internal.py  ping/reset_scene/shutdown/get_secret（Task 3）
  handlers/<类目>.py     Task 7–23
tests/
  conftest.py addon_boot.py（Task 4）
  test_protocol.py（Task 2） test_harness.py（Task 4） test_parity.py（Task 5）
  test_<类目>.py（Task 7–23）
docs/README.md docs/tools.md（Task 24）
.claude/MAINTENANCE.md（Task 24）
```

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`, `src/blender_mcp_pro/__init__.py`, `addon/blender_mcp_pro/blender_manifest.toml`, `addon/blender_mcp_pro/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Produces: 包 `blender_mcp_pro`（server 侧）可 import；`ADDON_VERSION = "0.1.0"` 在两侧一致。

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "blender-mcp-pro"
version = "0.1.0"
description = "Local MCP server + Blender 5.2 extension, blender-mcp-pro feature parity"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]>=1.2",
    "httpx>=0.27",
]

[project.scripts]
blender-mcp-pro = "blender_mcp_pro.cli:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/blender_mcp_pro"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 写包入口与插件骨架**

`src/blender_mcp_pro/__init__.py`:
```python
__version__ = "0.1.0"
```

`addon/blender_mcp_pro/blender_manifest.toml`:
```toml
schema_version = "1.0.0"
id = "blender_mcp_pro"
version = "0.1.0"
name = "Blender MCP Pro (local)"
tagline = "Drive Blender from Claude Code over local MCP"
maintainer = "panda"
type = "add-on"
blender_version_min = "5.2.0"
license = ["SPDX:MIT"]
tags = ["Pipeline"]
```

`addon/blender_mcp_pro/__init__.py`（骨架，Task 6 补偏好与面板）:
```python
"""Blender MCP Pro (local) — extension entry."""
ADDON_VERSION = "0.1.0"


def register():
    from . import handlers  # noqa: F401  触发 HANDLERS 注册
    from . import server
    server.autostart_if_configured()


def unregister():
    from . import server
    server.stop()
```

`tests/__init__.py` 空文件。

- [ ] **Step 3: uv sync 并验证 import**

Run: `uv sync && uv run python -c "import blender_mcp_pro, mcp.server.fastmcp; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/blender_mcp_pro/__init__.py addon/blender_mcp_pro/blender_manifest.toml addon/blender_mcp_pro/__init__.py tests/__init__.py
git commit -m "chore: 项目脚手架（uv 包 + extension manifest）"
```

---

### Task 2: 帧协议与 server 侧连接

**Files:**
- Create: `addon/blender_mcp_pro/protocol.py`, `src/blender_mcp_pro/errors.py`, `src/blender_mcp_pro/connection.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Produces（addon）: `protocol.encode(obj: dict) -> bytes`；`protocol.read_frame(sock) -> dict | None`（对端关闭返回 None）；`protocol.MAX_FRAME = 64 * 1024 * 1024`
- Produces（server）: `BlenderConnection(host, port).call(tool: str, params: dict, timeout: float = 60.0) -> Any`；`get_connection() -> BlenderConnection`（读 `BLENDER_MCP_HOST/PORT`，默认 `127.0.0.1:9877`）；异常 `BlenderError(type, message, traceback)`、`BlenderUnavailable`、`BlenderTimeout`。

- [ ] **Step 1: 写失败测试**

`tests/test_protocol.py`:
```python
import json
import socket
import struct
import threading

import pytest

from blender_mcp_pro import connection as conn_mod
from blender_mcp_pro.errors import BlenderError, BlenderTimeout, BlenderUnavailable


def _frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack(">I", len(data)) + data


def _read_frame(sock):
    head = sock.recv(4)
    (n,) = struct.unpack(">I", head)
    buf = b""
    while len(buf) < n:
        buf += sock.recv(n - len(buf))
    return json.loads(buf)


@pytest.fixture
def fake_blender():
    """一个只回一条响应的假 Blender。responder(request_dict) -> response_dict | None(不回)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    state = {"responder": None, "received": []}

    def run():
        c, _ = srv.accept()
        with c:
            req = _read_frame(c)
            state["received"].append(req)
            resp = state["responder"](req)
            if resp is not None:
                c.sendall(_frame(resp))
            else:
                threading.Event().wait(2)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    yield port, state
    srv.close()


def test_call_roundtrip(fake_blender):
    port, state = fake_blender
    state["responder"] = lambda req: {"id": req["id"], "ok": True, "result": {"x": 1}}
    c = conn_mod.BlenderConnection("127.0.0.1", port)
    assert c.call("ping", {"a": 1}) == {"x": 1}
    assert state["received"][0]["tool"] == "ping"
    assert state["received"][0]["params"] == {"a": 1}
    c.close()


def test_error_response_raises(fake_blender):
    port, state = fake_blender
    state["responder"] = lambda req: {
        "id": req["id"], "ok": False,
        "error": {"type": "KeyError", "message": "Object 'Cub' not found. Did you mean: Cube", "traceback": "tb"},
    }
    c = conn_mod.BlenderConnection("127.0.0.1", port)
    with pytest.raises(BlenderError) as ei:
        c.call("get_object_info", {"name": "Cub"})
    assert "KeyError" in str(ei.value) and "Cube" in str(ei.value)


def test_timeout(fake_blender):
    port, state = fake_blender
    state["responder"] = lambda req: None
    c = conn_mod.BlenderConnection("127.0.0.1", port)
    with pytest.raises(BlenderTimeout):
        c.call("slow", {}, timeout=0.2)


def test_unavailable():
    c = conn_mod.BlenderConnection("127.0.0.1", 1)  # 没人监听
    with pytest.raises(BlenderUnavailable):
        c.call("ping", {})


def test_addon_protocol_matches():
    """addon 侧的编解码与 server 侧互通。"""
    import importlib.util, pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "addon" / "blender_mcp_pro" / "protocol.py"
    spec = importlib.util.spec_from_file_location("addon_protocol", p)
    proto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proto)
    a, b = socket.socketpair()
    b.sendall(proto.encode({"id": "1", "ok": True, "result": [1, 2]}))
    assert _read_frame(a) == {"id": "1", "ok": True, "result": [1, 2]}
    a.sendall(_frame({"id": "2", "tool": "ping", "params": {}}))
    assert proto.read_frame(b) == {"id": "2", "tool": "ping", "params": {}}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_protocol.py -q`
Expected: ImportError（`blender_mcp_pro.connection` 不存在）

- [ ] **Step 3: 实现 addon/protocol.py**

```python
"""长度前缀 JSON 帧。与 src/blender_mcp_pro/connection.py 镜像，两边不共享代码。"""
import json
import socket
import struct

MAX_FRAME = 64 * 1024 * 1024
_HEAD = struct.Struct(">I")


def encode(obj) -> bytes:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ValueError(f"frame too large: {len(data)} bytes")
    return _HEAD.pack(len(data)) + data


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def read_frame(sock: socket.socket):
    head = _recv_exact(sock, _HEAD.size)
    if head is None:
        return None
    (n,) = _HEAD.unpack(head)
    if n > MAX_FRAME:
        raise ValueError(f"frame too large: {n} bytes")
    body = _recv_exact(sock, n)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))
```

- [ ] **Step 4: 实现 server 侧 errors.py 与 connection.py**

`src/blender_mcp_pro/errors.py`:
```python
class BlenderError(Exception):
    """Blender 插件侧 handler 抛出的异常，带类型与 traceback。"""

    def __init__(self, type_: str, message: str, traceback: str = ""):
        self.type = type_
        self.message = message
        self.traceback = traceback
        super().__init__(f"{type_}: {message}")


class BlenderUnavailable(Exception):
    """连不上插件 server。"""


class BlenderTimeout(Exception):
    """插件在超时时间内没回结果。"""
```

`src/blender_mcp_pro/connection.py`:
```python
"""TCP 客户端：懒连接、断线重连一次、长度前缀 JSON 帧。"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import uuid
from typing import Any

from .errors import BlenderError, BlenderTimeout, BlenderUnavailable

MAX_FRAME = 64 * 1024 * 1024
_HEAD = struct.Struct(">I")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877

HINT = ("Blender 未运行，或插件未启动 server"
        "（Blender ▸ Edit ▸ Preferences ▸ Add-ons ▸ Blender MCP Pro，或 N 面板 MCP Pro ▸ Start）")


def _encode(obj: Any) -> bytes:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ValueError(f"frame too large: {len(data)} bytes")
    return _HEAD.pack(len(data)) + data


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def _read_frame(sock: socket.socket) -> Any:
    head = _recv_exact(sock, _HEAD.size)
    if head is None:
        return None
    (n,) = _HEAD.unpack(head)
    if n > MAX_FRAME:
        raise ValueError(f"frame too large: {n} bytes")
    body = _recv_exact(sock, n)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


class BlenderConnection:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def _connect(self) -> socket.socket:
        try:
            s = socket.create_connection((self.host, self.port), timeout=3.0)
        except OSError as e:
            raise BlenderUnavailable(f"{HINT} [{self.host}:{self.port}: {e}]") from e
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return s

    def _ensure(self) -> socket.socket:
        if self._sock is None:
            self._sock = self._connect()
        return self._sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _once(self, request: dict, timeout: float) -> Any:
        sock = self._ensure()
        sock.settimeout(timeout)
        sock.sendall(_encode(request))
        resp = _read_frame(sock)
        if resp is None:
            raise ConnectionResetError("connection closed by Blender")
        return resp

    def call(self, tool: str, params: dict | None = None, timeout: float = 60.0) -> Any:
        request = {"id": uuid.uuid4().hex, "tool": tool, "params": params or {}}
        with self._lock:
            try:
                resp = self._once(request, timeout)
            except socket.timeout as e:
                self.close()
                raise BlenderTimeout(f"'{tool}' 超过 {timeout:.0f}s 未返回；Blender 可能正在渲染/烘焙，或已卡死") from e
            except (ConnectionError, OSError):
                # 断线重连一次
                self.close()
                try:
                    resp = self._once(request, timeout)
                except socket.timeout as e:
                    self.close()
                    raise BlenderTimeout(f"'{tool}' 超过 {timeout:.0f}s 未返回") from e
                except BlenderUnavailable:
                    raise
                except (ConnectionError, OSError) as e:
                    self.close()
                    raise BlenderUnavailable(f"{HINT} [{e}]") from e
        if resp.get("id") != request["id"]:
            self.close()
            raise BlenderError("ProtocolError", f"response id mismatch for '{tool}'")
        if resp.get("ok"):
            return resp.get("result")
        err = resp.get("error") or {}
        raise BlenderError(err.get("type", "Error"), err.get("message", "unknown error"), err.get("traceback", ""))


_conn: BlenderConnection | None = None


def get_connection() -> BlenderConnection:
    global _conn
    if _conn is None:
        host = os.environ.get("BLENDER_MCP_HOST", DEFAULT_HOST)
        port = int(os.environ.get("BLENDER_MCP_PORT", DEFAULT_PORT))
        _conn = BlenderConnection(host, port)
    return _conn
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_protocol.py -q`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add addon/blender_mcp_pro/protocol.py src/blender_mcp_pro/errors.py src/blender_mcp_pro/connection.py tests/test_protocol.py
git commit -m "feat: 长度前缀 JSON 帧协议与 server 侧连接"
```

---

### Task 3: 插件侧 registry / utils / TCP server / 内部命令

**Files:**
- Create: `addon/blender_mcp_pro/registry.py`, `addon/blender_mcp_pro/utils.py`, `addon/blender_mcp_pro/server.py`, `addon/blender_mcp_pro/handlers/__init__.py`, `addon/blender_mcp_pro/handlers/_internal.py`

**Interfaces:**
- Produces: `registry.command(name, *, internal=False, mutates=True)` 装饰器；`registry.HANDLERS: dict[str, Handler]`，`Handler(name, fn, internal, mutates)`；`registry.dispatch(tool, params) -> Any`（统一异常包装 + undo_push）
- Produces: `server.start(host, port) -> BlenderTCPServer`；`server.stop()`；`server.drain_once() -> int`；`server.autostart_if_configured()`；`server.is_running() -> bool`；`server.status() -> dict`
- Produces（utils，后续所有 handler 依赖）:
  - `class ToolError(Exception)`
  - `find_object(name, obj_type=None) -> Object`；`find_material(name)`；`find_node_group(name)`；`find_image(name)`；`find_action(name)`；`find_collection(name)`；`find_camera(name)`；`find_light(name)`；`find_armature(name)`
  - `resolve_objects(objects) -> list[Object]`
  - `vec(v) -> list[float]`；`serialize(value) -> Any`；`obj_brief(obj) -> dict`；`mat_brief(mat) -> dict`
  - `mode(obj, target: str)` 上下文管理器；`select_only(objs, active=None)`；
  - `set_props(target, settings: dict, tool_hint="") -> list[str]`（RNA 校验，返回改过的键）；`rna_props(target) -> dict`
  - `enum_check(value, options, what)`；`no_viewport()` 抛 `NoViewportError`

- [ ] **Step 1: registry.py**

```python
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
            except Exception:
                pass
        return {"ok": True, "result": result}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }}
```

- [ ] **Step 2: utils.py**

```python
"""handler 共用：查找、序列化、模式切换、RNA 属性写入。"""
from __future__ import annotations

import fnmatch
from contextlib import contextmanager
from typing import Any, Iterable

import bpy
import mathutils


class ToolError(Exception):
    """参数/查找错误，信息面向 LLM 可读。"""


class NoViewportError(ToolError):
    """需要 3D 视图（GUI），无头模式不可用。"""


def no_viewport():
    raise NoViewportError("此工具需要 Blender GUI 的 3D 视图，无头（-b）模式不可用")


# ---------- 查找 ----------

def _not_found(kind: str, name: str, candidates: Iterable[str]) -> ToolError:
    cands = sorted(candidates)
    close = [c for c in cands if name.lower() in c.lower() or c.lower() in name.lower()] or cands
    hint = ", ".join(close[:10])
    return ToolError(f"{kind} '{name}' not found. Available: {hint}" if hint else f"{kind} '{name}' not found (none exist)")


def find_object(name: str, obj_type: str | None = None) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        pool = [o.name for o in bpy.data.objects if obj_type is None or o.type == obj_type]
        raise _not_found("Object", name, pool)
    if obj_type and obj.type != obj_type:
        raise ToolError(f"Object '{name}' is {obj.type}, expected {obj_type}")
    return obj


def find_material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m is None:
        raise _not_found("Material", name, (x.name for x in bpy.data.materials))
    return m


def find_node_group(name: str) -> bpy.types.NodeTree:
    g = bpy.data.node_groups.get(name)
    if g is None:
        raise _not_found("NodeGroup", name, (x.name for x in bpy.data.node_groups))
    return g


def find_image(name: str) -> bpy.types.Image:
    i = bpy.data.images.get(name)
    if i is None:
        raise _not_found("Image", name, (x.name for x in bpy.data.images))
    return i


def find_action(name: str) -> bpy.types.Action:
    a = bpy.data.actions.get(name)
    if a is None:
        raise _not_found("Action", name, (x.name for x in bpy.data.actions))
    return a


def find_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c is None:
        raise _not_found("Collection", name, (x.name for x in bpy.data.collections))
    return c


def find_camera(name: str) -> bpy.types.Object:
    return find_object(name, "CAMERA")


def find_light(name: str) -> bpy.types.Object:
    return find_object(name, "LIGHT")


def find_armature(name: str) -> bpy.types.Object:
    return find_object(name, "ARMATURE")


def resolve_objects(objects) -> list[bpy.types.Object]:
    """list[str] | str | {"pattern"|"collection"|"type"|"selected"} → 对象列表。"""
    if objects is None:
        raise ToolError("'objects' is required")
    if isinstance(objects, str):
        return [find_object(objects)]
    if isinstance(objects, list):
        return [find_object(n) for n in objects]
    if isinstance(objects, dict):
        if "pattern" in objects:
            res = [o for o in bpy.data.objects if fnmatch.fnmatchcase(o.name, objects["pattern"])]
        elif "collection" in objects:
            res = list(find_collection(objects["collection"]).all_objects)
        elif "type" in objects:
            res = [o for o in bpy.data.objects if o.type == objects["type"].upper()]
        elif objects.get("selected"):
            res = list(bpy.context.selected_objects)
        else:
            raise ToolError("objects filter must be one of pattern / collection / type / selected")
        if not res:
            raise ToolError(f"no objects matched {objects}")
        return res
    raise ToolError(f"unsupported objects spec: {objects!r}")


# ---------- 序列化 ----------

def vec(v) -> list[float]:
    return [round(float(x), 6) for x in v]


def serialize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (mathutils.Vector, mathutils.Euler, mathutils.Color, mathutils.Quaternion)):
        return vec(value)
    if isinstance(value, mathutils.Matrix):
        return [vec(row) for row in value]
    if isinstance(value, bpy.types.ID):
        return {"name": value.name, "type": type(value).__name__}
    if isinstance(value, (list, tuple)):
        return [serialize(x) for x in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
        try:
            return [serialize(x) for x in value]
        except Exception:  # noqa: BLE001
            pass
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def obj_brief(o: bpy.types.Object) -> dict:
    return {
        "name": o.name,
        "type": o.type,
        "location": vec(o.location),
        "rotation": vec(o.rotation_euler),
        "scale": vec(o.scale),
        "dimensions": vec(o.dimensions),
        "collections": [c.name for c in o.users_collection],
        "visible": not o.hide_viewport,
        "parent": o.parent.name if o.parent else None,
    }


def mat_brief(m: bpy.types.Material) -> dict:
    return {"name": m.name, "users": m.users, "nodes": len(m.node_tree.nodes) if m.node_tree else 0}


# ---------- 选择与模式 ----------

def select_only(objs: Iterable[bpy.types.Object], active: bpy.types.Object | None = None):
    objs = list(objs)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


@contextmanager
def mode(obj: bpy.types.Object, target: str = "EDIT"):
    """把 obj 设为活动并切到 target 模式，退出时恢复。"""
    prev_active = bpy.context.view_layer.objects.active
    prev_selected = list(bpy.context.selected_objects)
    prev_mode = obj.mode
    select_only([obj], obj)
    if obj.mode != target:
        bpy.ops.object.mode_set(mode=target)
    try:
        yield obj
    finally:
        if obj.mode != prev_mode:
            bpy.ops.object.mode_set(mode=prev_mode)
        select_only(prev_selected, prev_active if prev_active and prev_active.name in bpy.data.objects else None)


# ---------- RNA 属性 ----------

_POINTER_LOOKUP = {
    "Object": lambda n: find_object(n),
    "Material": lambda n: find_material(n),
    "NodeTree": lambda n: find_node_group(n),
    "GeometryNodeTree": lambda n: find_node_group(n),
    "Image": lambda n: find_image(n),
    "Collection": lambda n: find_collection(n),
    "Texture": lambda n: bpy.data.textures.get(n) or (_ for _ in ()).throw(_not_found("Texture", n, (t.name for t in bpy.data.textures))),
    "Action": lambda n: find_action(n),
    "Curve": lambda n: bpy.data.curves.get(n) or (_ for _ in ()).throw(_not_found("Curve", n, (c.name for c in bpy.data.curves))),
}


def rna_props(target) -> dict:
    """可写属性表：name → {type, subtype, enum, default, description}。"""
    out = {}
    for p in target.bl_rna.properties:
        if p.identifier in ("rna_type",) or p.is_readonly:
            continue
        d: dict[str, Any] = {"type": p.type, "description": p.description}
        if p.type == "ENUM":
            d["enum"] = [e.identifier for e in p.enum_items]
        elif p.type in ("INT", "FLOAT") and getattr(p, "array_length", 0) > 1:
            d["array_length"] = p.array_length
        elif p.type == "POINTER":
            d["pointer_type"] = p.fixed_type.identifier
        if p.type in ("INT", "FLOAT", "BOOLEAN", "STRING") and getattr(p, "array_length", 0) <= 1:
            d["default"] = serialize(getattr(p, "default", None))
        out[p.identifier] = d
    return out


def set_props(target, settings: dict | None, tool_hint: str = "") -> list[str]:
    """按 RNA 校验写入属性；指针属性接受名字；枚举校验；未知键报错并列出可用键。"""
    if not settings:
        return []
    props = {p.identifier: p for p in target.bl_rna.properties if not p.is_readonly}
    changed = []
    for key, value in settings.items():
        p = props.get(key)
        if p is None:
            raise ToolError(f"{tool_hint}unknown property '{key}' for {type(target).__name__}. Available: {', '.join(sorted(props))}")
        if p.type == "POINTER":
            if value is None:
                setattr(target, key, None)
            else:
                kind = p.fixed_type.identifier
                lookup = _POINTER_LOOKUP.get(kind)
                if lookup is None:
                    raise ToolError(f"cannot set pointer property '{key}' (type {kind}) by name")
                setattr(target, key, lookup(value))
        elif p.type == "ENUM":
            opts = [e.identifier for e in p.enum_items]
            if p.is_enum_flag:
                setattr(target, key, set(enum_check(v, opts, key) for v in (value if isinstance(value, list) else [value])))
            else:
                setattr(target, key, enum_check(value, opts, key))
        else:
            setattr(target, key, value)
        changed.append(key)
    return changed


def enum_check(value, options, what: str):
    if isinstance(value, str):
        v = value.upper() if value.upper() in options else value
        if v in options:
            return v
    raise ToolError(f"invalid {what} '{value}'. Options: {', '.join(options)}")


def color4(c, default_alpha: float = 1.0) -> tuple:
    if c is None:
        raise ToolError("color is required")
    c = list(c)
    if len(c) == 3:
        c.append(default_alpha)
    if len(c) != 4:
        raise ToolError("color must be [r,g,b] or [r,g,b,a]")
    return tuple(float(x) for x in c)


def link_to_scene(obj: bpy.types.Object, collection: str | None = None):
    coll = find_collection(collection) if collection else bpy.context.scene.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)
```

- [ ] **Step 3: server.py（监听线程 + 队列 + drain）**

```python
"""插件侧 TCP server。accept/读写在守护线程；handler 在主线程（drain_once）执行。"""
from __future__ import annotations

import queue
import socket
import threading
import time

import bpy

from . import protocol, registry

_server: "BlenderTCPServer | None" = None
_TIMER_INTERVAL = 0.05
_MAX_PER_DRAIN = 20


class _Pending:
    __slots__ = ("request", "event", "response")

    def __init__(self, request):
        self.request = request
        self.event = threading.Event()
        self.response = None


class BlenderTCPServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.stopped = False
        self._queue: "queue.Queue[_Pending]" = queue.Queue()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.listen(4)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="mcp-accept")
        self._thread.start()
        self.started_at = time.time()
        self.handled = 0

    # ---- 网络线程 ----
    def _accept_loop(self):
        while not self.stopped:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True, name="mcp-client").start()

    def _client_loop(self, conn: socket.socket):
        with conn:
            conn.settimeout(None)
            while not self.stopped:
                try:
                    req = protocol.read_frame(conn)
                except (OSError, ValueError):
                    break
                if req is None:
                    break
                pending = _Pending(req)
                self._queue.put(pending)
                pending.event.wait()
                try:
                    conn.sendall(protocol.encode(pending.response))
                except OSError:
                    break

    # ---- 主线程 ----
    def drain_once(self) -> int:
        n = 0
        while n < _MAX_PER_DRAIN:
            try:
                p = self._queue.get_nowait()
            except queue.Empty:
                break
            req = p.request
            body = registry.dispatch(req.get("tool", ""), req.get("params") or {})
            p.response = {"id": req.get("id"), **body}
            p.event.set()
            n += 1
            self.handled += 1
        return n

    def close(self):
        self.stopped = True
        try:
            self._sock.close()
        except OSError:
            pass
        while True:
            try:
                p = self._queue.get_nowait()
            except queue.Empty:
                break
            p.response = {"id": p.request.get("id"), "ok": False,
                          "error": {"type": "ServerStopped", "message": "server stopped", "traceback": ""}}
            p.event.set()


def _timer():
    if _server is None or _server.stopped:
        return None
    _server.drain_once()
    return _TIMER_INTERVAL


def start(host: str = "127.0.0.1", port: int = 9877) -> BlenderTCPServer:
    global _server
    if _server is not None and not _server.stopped:
        return _server
    _server = BlenderTCPServer(host, port)
    if not bpy.app.background and not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=_TIMER_INTERVAL, persistent=True)
    print(f"[blender_mcp_pro] server listening on {host}:{port}")
    return _server


def stop():
    global _server
    if _server is not None:
        _server.close()
        _server = None
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)


def drain_once() -> int:
    return _server.drain_once() if _server else 0


def is_running() -> bool:
    return _server is not None and not _server.stopped


def status() -> dict:
    if not is_running():
        return {"running": False}
    return {"running": True, "host": _server.host, "port": _server.port,
            "handled": _server.handled, "uptime": round(time.time() - _server.started_at, 1)}


def _prefs():
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None


def autostart_if_configured():
    p = _prefs()
    if p is not None and p.autostart and not bpy.app.background:
        start(p.host, p.port)
```

- [ ] **Step 4: handlers/__init__.py 与 _internal.py**

`handlers/__init__.py`（每个类目任务在此追加一行 import）:
```python
from . import _internal  # noqa: F401
```

`handlers/_internal.py`:
```python
"""内部命令：不暴露为 MCP 工具。"""
import bpy

from .. import ADDON_VERSION
from ..registry import command


@command("ping", internal=True, mutates=False)
def ping():
    return {"blender": bpy.app.version_string, "addon": ADDON_VERSION, "background": bpy.app.background}


@command("reset_scene", internal=True, mutates=False)
def reset_scene():
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
    val = getattr(p, key, None)
    return val or None
```

- [ ] **Step 5: 用无头 Blender 冒烟一次**

Run:
```bash
cat > tmp/smoke_task3.py <<'EOF'
import sys, os, time, socket, json, struct, threading
sys.path.insert(0, os.path.abspath("addon"))
import blender_mcp_pro
from blender_mcp_pro import server, registry
import blender_mcp_pro.handlers  # noqa
srv = server.start("127.0.0.1", 9911)
def client():
    time.sleep(0.2)
    s = socket.create_connection(("127.0.0.1", 9911))
    body = json.dumps({"id": "1", "tool": "ping", "params": {}}).encode()
    s.sendall(struct.pack(">I", len(body)) + body)
    n, = struct.unpack(">I", s.recv(4)); print("RESP", json.loads(s.recv(n)))
    body = json.dumps({"id": "2", "tool": "shutdown", "params": {}}).encode()
    s.sendall(struct.pack(">I", len(body)) + body)
    n, = struct.unpack(">I", s.recv(4)); s.recv(n)
threading.Thread(target=client, daemon=True).start()
while not srv.stopped:
    srv.drain_once(); time.sleep(0.005)
print("HANDLERS", sorted(registry.HANDLERS))
EOF
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tmp/smoke_task3.py 2>&1 | grep -E "RESP|HANDLERS"
```
Expected: `RESP {'id': '1', 'ok': True, 'result': {'blender': '5.2.1 LTS', 'addon': '0.1.0', 'background': True}}` 与 `HANDLERS ['get_secret', 'ping', 'reset_scene', 'shutdown']`

- [ ] **Step 6: Commit**

```bash
git add addon/blender_mcp_pro/registry.py addon/blender_mcp_pro/utils.py addon/blender_mcp_pro/server.py addon/blender_mcp_pro/handlers/__init__.py addon/blender_mcp_pro/handlers/_internal.py
git commit -m "feat(addon): registry、utils、TCP server 与内部命令"
```

---

### Task 4: 无头 Blender 测试夹具

**Files:**
- Create: `tests/addon_boot.py`, `tests/conftest.py`, `tests/test_harness.py`

**Interfaces:**
- Produces: pytest fixture `blender`（session 级，`BlenderConnection`）；autouse fixture `fresh_scene`（每个测试前 `reset_scene`）；helper `tests/conftest.py::call(blender, tool, **params)`；环境变量 `BLENDER_MCP_BLENDER` 覆盖 Blender 路径。

- [ ] **Step 1: addon_boot.py（在 Blender 内运行）**

```python
"""blender -b --factory-startup --python tests/addon_boot.py -- --port N
从源码目录加载插件、起 server，并在主线程循环 drain（无头模式 timers 不触发）。"""
import os
import sys
import time

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 9877

root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon"))
sys.path.insert(0, root)

import blender_mcp_pro  # noqa: E402
import blender_mcp_pro.handlers  # noqa: E402,F401
from blender_mcp_pro import server  # noqa: E402

srv = server.start("127.0.0.1", port)
print(f"[addon_boot] ready on {port}", flush=True)
try:
    while not srv.stopped:
        if srv.drain_once() == 0:
            time.sleep(0.003)
finally:
    server.stop()
    print("[addon_boot] stopped", flush=True)
```

- [ ] **Step 2: conftest.py**

```python
import os
import pathlib
import socket
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_mcp_pro.connection import BlenderConnection  # noqa: E402
from blender_mcp_pro.errors import BlenderUnavailable, BlenderTimeout  # noqa: E402

BLENDER = os.environ.get("BLENDER_MCP_BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def blender():
    if not os.path.exists(BLENDER):
        pytest.skip(f"Blender not found at {BLENDER}")
    port = _free_port()
    log = open(ROOT / "tmp" / "blender_test.log", "w")
    proc = subprocess.Popen(
        [BLENDER, "-b", "--factory-startup", "--python", str(ROOT / "tests" / "addon_boot.py"), "--", "--port", str(port)],
        stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT),
    )
    conn = BlenderConnection("127.0.0.1", port)
    deadline = time.time() + 40
    while True:
        try:
            conn.call("ping", {}, timeout=5)
            break
        except (BlenderUnavailable, BlenderTimeout):
            if proc.poll() is not None or time.time() > deadline:
                log.close()
                raise RuntimeError(f"Blender failed to start; see {ROOT / 'tmp' / 'blender_test.log'}")
            time.sleep(0.3)
    yield conn
    try:
        conn.call("shutdown", {}, timeout=5)
    except Exception:  # noqa: BLE001
        pass
    conn.close()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture(autouse=True)
def fresh_scene(request, blender_or_none):
    if blender_or_none is not None:
        blender_or_none.call("reset_scene", {}, timeout=30)


@pytest.fixture
def blender_or_none(request):
    """只有用到 blender 夹具的测试才拉起 Blender。"""
    if "blender" in request.fixturenames:
        return request.getfixturevalue("blender")
    return None


def call(blender, tool, timeout=60.0, **params):
    return blender.call(tool, {k: v for k, v in params.items() if v is not None}, timeout=timeout)
```

- [ ] **Step 3: test_harness.py（失败测试先跑）**

```python
import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call


def test_ping(blender):
    r = call(blender, "ping")
    assert r["blender"].startswith("5.2") and r["background"] is True


def test_reset_scene_gives_factory_objects(blender):
    r = call(blender, "reset_scene")
    assert sorted(r["objects"]) == ["Camera", "Cube", "Light"]


def test_unknown_tool_error(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "no_such_tool")
    assert ei.value.type == "UnknownTool"


def test_error_carries_traceback(blender):
    # get_secret 缺参数 → TypeError，带 traceback
    with pytest.raises(BlenderError) as ei:
        call(blender, "get_secret")
    assert ei.value.type == "TypeError" and "Traceback" in ei.value.traceback
```

Run: `uv run pytest tests/test_harness.py -q`
Expected: 4 passed（第一次运行前 `conftest.py` 已就位，所以直接绿；若 Blender 启动失败看 `tmp/blender_test.log`）

- [ ] **Step 4: Commit**

```bash
git add tests/addon_boot.py tests/conftest.py tests/test_harness.py
git commit -m "test: 无头 Blender 集成测试夹具"
```

---

### Task 5: MCP server 骨架与对账测试

**Files:**
- Create: `src/blender_mcp_pro/server.py`, `src/blender_mcp_pro/tools/__init__.py`, `src/blender_mcp_pro/tools/_base.py`
- Test: `tests/test_parity.py`

**Interfaces:**
- Produces: `server.mcp: FastMCP`；`server.main()`（stdio）；`tools.tool_names() -> set[str]`；`_base.call(tool, timeout=60.0, **params) -> Any`（丢弃 None 参数）；`_base.LONG = 600.0`；`_base.image_result(result: dict) -> Image | dict`
- 每个类目文件形如：
  ```python
  from ..server import mcp
  from ._base import call
  @mcp.tool()
  def get_scene_info() -> dict:
      """一句话描述。"""
      return call("get_scene_info")
  ```

- [ ] **Step 1: server.py / _base.py / tools/__init__.py**

`src/blender_mcp_pro/server.py`:
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "blender-mcp-pro",
    instructions=(
        "本地 Blender 5.2 控制器。所有位置/旋转/缩放为 [x,y,z]，旋转用弧度；颜色 0–1。"
        "先 get_scene_info 了解场景，再操作；找不到对象时报错会列出候选名。"
        "写操作可在 Blender 里 Ctrl+Z 撤销，也可用 undo 工具。"
    ),
)


def main():
    from . import tools  # noqa: F401  注册全部工具
    mcp.run(transport="stdio")
```

`src/blender_mcp_pro/tools/_base.py`:
```python
from __future__ import annotations

import base64
from typing import Any

from mcp.server.fastmcp import Image

from ..connection import get_connection

LONG = 600.0


def call(tool: str, timeout: float = 60.0, **params: Any) -> Any:
    clean = {k: v for k, v in params.items() if v is not None}
    return get_connection().call(tool, clean, timeout=timeout)


def image_result(result: dict) -> Image | dict:
    """handler 返回 {"image_base64", "mime", ...} 时转成 MCP Image；否则原样返回。"""
    if isinstance(result, dict) and result.get("image_base64"):
        fmt = "png" if result.get("mime", "image/png").endswith("png") else "jpeg"
        return Image(data=base64.b64decode(result["image_base64"]), format=fmt)
    return result
```

`src/blender_mcp_pro/tools/__init__.py`（各类目任务追加一行）:
```python
import asyncio

from ..server import mcp

# 类目模块（每个 Task 追加一行）


def tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}
```

- [ ] **Step 2: 对账测试**

`tests/test_parity.py`:
```python
"""server 工具集合 == 插件非 internal 的 HANDLERS 集合；每个工具有描述。"""
import asyncio
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _addon_public_names() -> set[str]:
    """在测试进程里加载插件的 registry + handlers，用假 bpy 替身避免依赖 Blender。"""
    fake_bpy = types.ModuleType("bpy")
    fake_bpy.ops = types.SimpleNamespace(ed=types.SimpleNamespace(undo_push=lambda **k: None))
    fake_bpy.app = types.SimpleNamespace(background=True, version_string="test", timers=types.SimpleNamespace(is_registered=lambda f: False))
    fake_bpy.types = types.SimpleNamespace(ID=type("ID", (), {}), Object=type("Object", (), {}), Operator=type("Operator", (), {}), Panel=type("Panel", (), {}), AddonPreferences=type("AddonPreferences", (), {}))
    fake_bpy.data = types.SimpleNamespace()
    fake_bpy.context = types.SimpleNamespace()
    fake_bpy.props = types.SimpleNamespace(StringProperty=lambda **k: None, IntProperty=lambda **k: None, BoolProperty=lambda **k: None)
    fake_bpy.utils = types.SimpleNamespace(register_class=lambda c: None, unregister_class=lambda c: None)
    fake_mathutils = types.ModuleType("mathutils")
    for n in ("Vector", "Euler", "Color", "Quaternion", "Matrix"):
        setattr(fake_mathutils, n, type(n, (), {}))
    fake_bmesh = types.ModuleType("bmesh")
    fake_bmesh.ops = types.SimpleNamespace()
    saved = {k: sys.modules.get(k) for k in ("bpy", "mathutils", "bmesh")}
    sys.modules.update({"bpy": fake_bpy, "mathutils": fake_mathutils, "bmesh": fake_bmesh})
    sys.path.insert(0, str(ROOT / "addon"))
    try:
        for m in [k for k in sys.modules if k.startswith("blender_mcp_pro")]:
            if not m.startswith("blender_mcp_pro.tools") and m != "blender_mcp_pro" or sys.modules[m].__file__ and "addon" in sys.modules[m].__file__:
                pass
        import importlib
        pkg = importlib.import_module("blender_mcp_pro_addon_shim") if False else None  # noqa
        spec = importlib.util.spec_from_file_location(
            "addon_pkg", ROOT / "addon" / "blender_mcp_pro" / "__init__.py",
            submodule_search_locations=[str(ROOT / "addon" / "blender_mcp_pro")])
        addon = importlib.util.module_from_spec(spec)
        sys.modules["addon_pkg"] = addon
        spec.loader.exec_module(addon)
        importlib.import_module("addon_pkg.handlers")
        registry = importlib.import_module("addon_pkg.registry")
        return registry.public_names()
    finally:
        sys.path.remove(str(ROOT / "addon"))
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
    addon_names = _addon_public_names()
    assert server_names == addon_names, (
        f"only in server: {sorted(server_names - addon_names)}\nonly in addon: {sorted(addon_names - server_names)}")


def test_every_tool_has_description():
    from blender_mcp_pro import tools  # noqa: F401
    from blender_mcp_pro.server import mcp
    missing = [t.name for t in asyncio.run(mcp.list_tools()) if not (t.description or "").strip()]
    assert not missing, missing
```

> 说明：`_addon_public_names` 用假 `bpy` 把插件包按 `addon_pkg` 名字加载，只为读 `HANDLERS`。handler 模块顶层不能执行任何 bpy 调用（只能在函数体里用），这是后续所有类目任务的硬约束。

- [ ] **Step 3: 跑对账测试**

Run: `uv run pytest tests/test_parity.py -q`
Expected: 2 passed（此时两边都为空集）

- [ ] **Step 4: Commit**

```bash
git add src/blender_mcp_pro/server.py src/blender_mcp_pro/tools/__init__.py src/blender_mcp_pro/tools/_base.py tests/test_parity.py
git commit -m "feat(server): FastMCP 骨架与工具对账测试"
```

---

### Task 6: CLI、插件偏好与 N 面板

**Files:**
- Create: `src/blender_mcp_pro/cli.py`
- Modify: `addon/blender_mcp_pro/__init__.py`

**Interfaces:**
- Produces: `blender-mcp-pro serve|install-addon [--copy]|uninstall-addon|dump-tools`
- Produces（addon）: `Preferences(host, port, autostart, sketchfab_token)`；操作符 `mcp_pro.start_server` / `mcp_pro.stop_server`；面板 `VIEW3D_PT_mcp_pro`（N 面板 "MCP Pro" 页）

- [ ] **Step 1: 完善 addon/__init__.py**

```python
"""Blender MCP Pro (local) — extension entry."""
import bpy

ADDON_VERSION = "0.1.0"


class Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    host: bpy.props.StringProperty(name="Host", default="127.0.0.1")
    port: bpy.props.IntProperty(name="Port", default=9877, min=1024, max=65535)
    autostart: bpy.props.BoolProperty(name="Auto start server", default=True)
    sketchfab_token: bpy.props.StringProperty(name="Sketchfab API token", default="", subtype="PASSWORD")

    def draw(self, context):
        from . import server
        col = self.layout.column()
        col.prop(self, "host")
        col.prop(self, "port")
        col.prop(self, "autostart")
        col.prop(self, "sketchfab_token")
        st = server.status()
        col.label(text=f"Status: {'running on %s:%s' % (st['host'], st['port']) if st['running'] else 'stopped'}")


class MCP_OT_start(bpy.types.Operator):
    bl_idname = "mcp_pro.start_server"
    bl_label = "Start MCP server"

    def execute(self, context):
        from . import server
        p = context.preferences.addons[__package__].preferences
        server.start(p.host, p.port)
        return {"FINISHED"}


class MCP_OT_stop(bpy.types.Operator):
    bl_idname = "mcp_pro.stop_server"
    bl_label = "Stop MCP server"

    def execute(self, context):
        from . import server
        server.stop()
        return {"FINISHED"}


class VIEW3D_PT_mcp_pro(bpy.types.Panel):
    bl_label = "MCP Pro"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP Pro"

    def draw(self, context):
        from . import server
        st = server.status()
        col = self.layout.column()
        if st["running"]:
            col.label(text=f"Running {st['host']}:{st['port']}", icon="CHECKMARK")
            col.label(text=f"handled {st['handled']} · {st['uptime']}s")
            col.operator("mcp_pro.stop_server", icon="PAUSE")
        else:
            col.label(text="Stopped", icon="X")
            col.operator("mcp_pro.start_server", icon="PLAY")


_classes = (Preferences, MCP_OT_start, MCP_OT_stop, VIEW3D_PT_mcp_pro)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    from . import handlers  # noqa: F401
    from . import server
    server.autostart_if_configured()


def unregister():
    from . import server
    server.stop()
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
```

> 注意：`addon_boot.py` 直接 import 包而不调用 `register()`，所以无头测试不受 `bpy.types.AddonPreferences` 影响；但对账测试的假 bpy 已提供 `AddonPreferences/Operator/Panel/props`，模块顶层才能过。

- [ ] **Step 2: cli.py**

```python
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
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    if copy:
        shutil.copytree(ADDON_SRC, dst)
    else:
        dst.symlink_to(ADDON_SRC, target_is_directory=True)
    print(f"{'copied' if copy else 'linked'} {ADDON_SRC} -> {dst}")
    rc = _blender_python(
        "import bpy;"
        "bpy.ops.extensions.repo_refresh_all();"
        f"bpy.ops.preferences.addon_enable(module='{MODULE}');"
        "bpy.ops.wm.save_userpref();"
        f"print('enabled', '{MODULE}' in bpy.context.preferences.addons)"
    )
    return rc


def uninstall_addon() -> int:
    _blender_python(
        "import bpy;"
        f"bpy.ops.preferences.addon_disable(module='{MODULE}') if '{MODULE}' in bpy.context.preferences.addons else None;"
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
    lines = ["# 工具清单", "", "由 `uv run blender-mcp-pro dump-tools > docs/tools.md` 生成，不要手改。", ""]
    for t in sorted(asyncio.run(mcp.list_tools()), key=lambda t: t.name):
        props = t.inputSchema.get("properties", {})
        req = set(t.inputSchema.get("required", []))
        params = ", ".join(f"{k}{'' if k in req else '?'}" for k in props)
        lines.append(f"- **{t.name}**({params}) — {(t.description or '').strip().splitlines()[0]}")
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
```

- [ ] **Step 3: 验证**

Run: `uv run blender-mcp-pro dump-tools && uv run pytest -q`
Expected: dump 输出只有表头（还没工具）；全部测试通过（protocol 5 + harness 4 + parity 2）。

- [ ] **Step 4: Commit**

```bash
git add src/blender_mcp_pro/cli.py addon/blender_mcp_pro/__init__.py
git commit -m "feat: CLI（serve/install-addon/dump-tools）与插件偏好、N 面板"
```

---

## 类目任务通用模板（Task 7–23 都按此执行）

每个类目任务交付三个文件，顺序固定：

1. `tests/test_<类目>.py` —— 先写，跑一遍确认全部 `BlenderError: UnknownTool`。
2. `addon/blender_mcp_pro/handlers/<类目>.py` —— `@command("<tool>")` 实现；**模块顶层只允许 import，不得执行 bpy 调用**（对账测试用假 bpy 加载）。写完在 `handlers/__init__.py` 追加 `from . import <类目>`。
3. `src/blender_mcp_pro/tools/<类目>.py` —— `@mcp.tool()` 一函数一工具，docstring 第一行是描述，参数带类型注解与默认值，函数体一行 `return call("<tool>", **locals())` 风格转发（长任务用 `timeout=LONG`）。写完在 `tools/__init__.py` 追加 `from . import <类目>  # noqa: F401`。

然后 `uv run pytest -q` 全绿 → 只 add 这三个文件 + 两个 `__init__.py` → commit `feat(<类目>): ...`。

只读工具用 `mutates=False`。所有 handler 返回值必须经过 `serialize()` 或本身就是基本类型。

---

### Task 7: Scene & Objects（16）

**Files:** `tests/test_scene.py`、`handlers/scene.py`、`tools/scene.py`

**Interfaces（server 签名 = 契约）:**
```python
get_scene_info() -> dict
list_objects(type: str | None = None, collection: str | None = None, pattern: str | None = None, selected: bool = False) -> list[dict]
get_object_info(name: str) -> dict
create_primitive(type: str, name: str | None = None, location: list[float] | None = None, rotation: list[float] | None = None,
                 scale: list[float] | None = None, size: float | None = None, radius: float | None = None, depth: float | None = None,
                 segments: int | None = None, text: str | None = None, collection: str | None = None) -> dict
delete_object(objects: list[str] | dict, delete_children: bool = False) -> dict
duplicate_object(name: str, new_name: str | None = None, linked: bool = False, offset: list[float] | None = None) -> dict
set_transform(name: str, location=None, rotation=None, scale=None, relative: bool = False) -> dict
rename_object(name: str, new_name: str, rename_data: bool = True) -> dict
set_parent(child: str, parent: str | None = None, keep_transform: bool = True) -> dict
set_visibility(objects, hide_viewport: bool | None = None, hide_render: bool | None = None, hide_select: bool | None = None) -> dict
select_objects(objects, mode: str = "replace", active: str | None = None) -> dict
manage_collection(action: str, name: str, parent: str | None = None, objects=None, new_name: str | None = None) -> dict
join_objects(objects, target: str | None = None) -> dict
apply_transforms(objects, location: bool = True, rotation: bool = True, scale: bool = True) -> dict
set_origin(name: str, type: str = "GEOMETRY") -> dict
set_custom_property(name: str, key: str, value=None) -> dict
```

**Handler 要点:**
- `create_primitive`: type 映射 → `bpy.ops.mesh.primitive_{cube,uv_sphere,ico_sphere,cylinder,cone,torus,plane,circle,monkey}_add`、`object.empty_add`、`object.text_add`（`obj.data.body = text`）；size/radius/depth/segments 只传给支持该参数的 op；建完 `bpy.context.active_object` 改名、可选移到 collection；返回 `obj_brief`。
- `delete_object`: `bpy.data.objects.remove(o, do_unlink=True)`；`delete_children` 递归 `o.children_recursive`；返回 `{"deleted": [...]}`。
- `duplicate_object`: `o.copy()`，非 linked 时 `data.copy()`；链接到原对象所在集合；返回 brief。
- `set_transform`: relative 时相加/相乘。
- `set_parent`: `keep_transform` → `child.matrix_parent_inverse = parent.matrix_world.inverted()`；parent None → 清除并保留世界矩阵（`mw = child.matrix_world.copy(); child.parent=None; child.matrix_world = mw`）。
- `select_objects`: mode ∈ replace/add/remove。
- `manage_collection`: create（parent 默认 scene collection）/delete（对象移回 scene collection）/move（先从所有集合 unlink）/link/unlink/rename。
- `join_objects`: `select_only(objs, target)` → `bpy.ops.object.join()`。
- `apply_transforms`: `select_only` → `bpy.ops.object.transform_apply(...)`。
- `set_origin`: `enum_check(type, ["GEOMETRY","CURSOR","CENTER_OF_MASS","CENTER_OF_VOLUME","BOUNDS"])` 映射到 `origin_set(type=...)`（GEOMETRY→ORIGIN_GEOMETRY，CURSOR→ORIGIN_CURSOR，CENTER_OF_MASS→ORIGIN_CENTER_OF_MASS，CENTER_OF_VOLUME→ORIGIN_CENTER_OF_VOLUME，BOUNDS→ORIGIN_GEOMETRY + center='BOUNDS'）。
- `set_custom_property`: value None → `del o[key]`。
- `get_scene_info`: 集合树递归 `{"name", "children": [...], "objects": [...]}`；类型计数 `Counter(o.type)`。

**Tests（节选，实际按每个工具至少一条）:**
```python
def test_create_and_info(blender):
    r = call(blender, "create_primitive", type="cylinder", name="Pillar", location=[1, 2, 3], radius=0.5, depth=2)
    assert r["name"] == "Pillar" and r["location"] == [1, 2, 3]
    info = call(blender, "get_object_info", name="Pillar")
    assert info["type"] == "MESH" and info["mesh"]["vertices"] > 0

def test_missing_object_lists_candidates(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "get_object_info", name="Cub")
    assert "Cube" in ei.value.message

def test_parent_keep_transform(blender):
    call(blender, "create_primitive", type="empty", name="Root", location=[5, 0, 0])
    call(blender, "set_parent", child="Cube", parent="Root")
    info = call(blender, "get_object_info", name="Cube")
    assert info["parent"] == "Root" and info["world_location"] == [0, 0, 0]

def test_manage_collection_move(blender):
    call(blender, "manage_collection", action="create", name="Props")
    call(blender, "manage_collection", action="move", name="Props", objects=["Cube"])
    assert call(blender, "get_object_info", name="Cube")["collections"] == ["Props"]

def test_join_and_apply(blender):
    call(blender, "create_primitive", type="cube", name="B", location=[3, 0, 0])
    r = call(blender, "join_objects", objects=["Cube", "B"], target="Cube")
    assert r["name"] == "Cube" and call(blender, "get_object_info", name="Cube")["mesh"]["vertices"] == 16
    call(blender, "set_transform", name="Cube", scale=[2, 2, 2])
    call(blender, "apply_transforms", objects=["Cube"])
    assert call(blender, "get_object_info", name="Cube")["scale"] == [1, 1, 1]
```

---

### Task 8: Scene Utilities（13）

**Files:** `tests/test_utilities.py`、`handlers/utilities.py`、`tools/utilities.py`

**Interfaces:**
```python
execute_code(code: str, return_var: str | None = None) -> dict          # {"stdout", "result"}
get_blender_info() -> dict
get_api_docs(path: str) -> dict
undo() -> dict ; redo() -> dict
purge_orphans() -> dict
set_units(system=None, scale_length=None, length_unit=None, rotation_unit=None) -> dict
set_cursor(location=None, rotation=None) -> dict
measure_distance(a, b) -> dict                                          # a/b: 对象名或 [x,y,z]
get_bounding_box(objects, world: bool = True) -> dict                   # {"min","max","center","size"}
ray_cast(origin: list[float], direction: list[float], distance: float = 1000.0) -> dict
check_mesh(name: str) -> dict
mesh_cleanup(name: str, recalc_normals=False, inside=False, merge_by_distance=False, threshold=0.0001,
             shade_smooth=None, auto_smooth_angle=None, dissolve_degenerate=False) -> dict
```

**Handler 要点:**
- `execute_code`: `ns = {"bpy": bpy, "bmesh": bmesh, "mathutils": mathutils, "math": math}`；`contextlib.redirect_stdout(io.StringIO())` 包 `exec(code, ns)`；`return_var` 存在则 `serialize(ns[return_var])`。
- `get_api_docs`: 三种路径。`bpy.ops.<mod>.<op>` → `getattr(bpy.ops.<mod>, op).get_rna_type()` 的 `properties` 与 description；`bpy.types.<T>` → `bl_rna.description` + `rna_props`；`bpy.types.<T>.<prop>` → 该属性 type/description/enum/default/array。找不到时 `ToolError` 并列出前 20 个相近的名字。
- `undo/redo`: `bpy.ops.ed.undo()` / `redo()`（`mutates=False`）。
- `purge_orphans`: `bpy.data.orphans_purge(do_recursive=True)` 返回删除数。
- `ray_cast`: `bpy.context.scene.ray_cast(bpy.context.view_layer.depsgraph, Vector(origin), Vector(direction).normalized(), distance=distance)`。
- `check_mesh`: `bmesh.new(); bm.from_mesh(me)`；非流形边、松散点、ngon、`bmesh.ops.find_doubles`。
- `mesh_cleanup`: bmesh ops（`recalc_face_normals` 后 `inside` 时翻转、`remove_doubles`、`dissolve_degenerate`），`bm.to_mesh(me)`；`shade_smooth` 设 `polygons.use_smooth`；`auto_smooth_angle` → `select_only([o]); bpy.ops.object.shade_smooth_by_angle(angle=...)`（失败则 `shade_auto_smooth`）。

**Tests:** execute_code 返回 stdout 与变量；get_api_docs 三种路径都有 description；purge 返回数字；measure_distance("Cube","Camera") ≈ `|Camera.location|`；get_bounding_box(["Cube"]) size == [2,2,2]；ray_cast 从 [0,0,10] 向 [0,0,-1] 命中 Cube 于 z=1；check_mesh Cube 六面全四边、无非流形；mesh_cleanup merge 后顶点数不变、shade_smooth 生效。

---

### Task 9: Materials（9）

**Files:** `tests/test_materials.py`、`handlers/materials.py`、`tools/materials.py`

**Interfaces:**
```python
list_materials(used_only: bool = False) -> list[dict]
get_material_info(name: str) -> dict
create_material(name: str, base_color=None, metallic=None, roughness=None, emission_color=None, emission_strength=None,
                alpha=None, ior=None, assign_to: str | None = None) -> dict
assign_material(object: str, material: str, slot: int | None = None) -> dict
set_principled_inputs(material: str, inputs: dict) -> dict
set_material_settings(material: str, surface_render_method=None, backface_culling=None, displacement_method=None, pass_index=None) -> dict
add_image_texture(material: str, image_path: str, target: str = "Base Color", colorspace: str | None = None, projection: str | None = None) -> dict
create_pbr_material(name: str, base_color=None, roughness=None, metallic=None, normal=None, height=None, ao=None, assign_to=None) -> dict
delete_material(name: str, unlink_only: bool = False) -> dict
```

**Handler 要点:**
- `_principled(mat)`: `next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")`，没有则新建并连到 Output。
- `set_principled_inputs`: 插槽名不存在 → ToolError 列出全部 `inputs.keys()`；颜色型插槽接受 3/4 分量。
- `add_image_texture`: `bpy.data.images.load(path, check_existing=True)`；`ShaderNodeTexImage`；`target == "Normal"` 时经 `ShaderNodeNormalMap`；非颜色贴图 colorspace 默认 `Non-Color`。
- `create_pbr_material`: 依次调用 `add_image_texture`；`height` → `ShaderNodeDisplacement` 接 Output.Displacement；`ao` → `ShaderNodeMix`(MULTIPLY) 混进 Base Color。
- `set_material_settings`: 5.2 用 `surface_render_method`(DITHERED/BLENDED)、`use_backface_culling`、`displacement_method`、`pass_index`。

**Tests:** create_material 后 `get_material_info` 的 principled.Base Color ≈ 输入；assign 到 Cube 后 material_slots 含它；set_principled_inputs 错插槽名报错含 "Roughness"；add_image_texture 用测试里 `create_image` 生成的 PNG（先 `bpy.data.images.new` 再 `save_render` 到 tmp）→ 节点数 +1，Normal 时 +2；delete_material 后 list 不含。

---

### Task 10: Shader Nodes（10）+ `nodes_common.py`

**Files:** `addon/blender_mcp_pro/nodes_common.py`、`tests/test_shader_nodes.py`、`handlers/shader_nodes.py`、`tools/shader_nodes.py`

**nodes_common 接口（Task 13 几何节点复用）:**
```python
get_tree(material: str | None = None, node_group: str | None = None) -> NodeTree
find_node(tree, name) -> Node                     # 按 name，再按 label，报错列候选
find_socket(sockets, key) -> NodeSocket           # key: 名字 / 索引 int / "Name#2" 第 N 个同名
socket_value(sock) -> Any
node_dump(node) -> dict                           # type,name,label,location,inputs{name:value},outputs[names],properties{}
tree_dump(tree) -> dict                           # {"nodes":[...],"links":[{from_node,from_socket,to_node,to_socket}]}
add_node(tree, type, name=None, location=None, inputs=None, properties=None) -> Node
set_input(node, socket, value)
set_property(node, prop, value)                   # image/node_tree/object 类指针按名解析；enum 校验
link(tree, from_node, from_socket, to_node, to_socket) -> dict
unlink(tree, to_node, to_socket) -> int
build(tree, nodes: list[dict], links: list[dict], clear: bool) -> dict
node_types(prefix: str, filter: str | None) -> list[dict]   # 遍历 bpy.types，实例化到临时树读插槽
```

**Interfaces（server）:**
```python
list_shader_nodes(material: str) -> dict
add_shader_node(material: str, type: str, name=None, location=None, inputs: dict | None = None, properties: dict | None = None) -> dict
remove_shader_node(material: str, node: str) -> dict
set_node_input(material: str, node: str, socket: str | int, value) -> dict
set_node_property(material: str, node: str, property: str, value) -> dict
link_nodes(material: str, from_node: str, from_socket: str | int, to_node: str, to_socket: str | int) -> dict
unlink_nodes(material: str, to_node: str, to_socket: str | int) -> dict
set_color_ramp(material: str, node: str, stops: list[dict], interpolation: str | None = None) -> dict
build_node_tree(material: str, nodes: list[dict], links: list[dict], clear: bool = False) -> dict
get_node_types(tree: str = "shader", filter: str | None = None) -> list[dict]
```
- `node_types`: shader 用临时 `bpy.data.materials.new("__mcp_probe")` 的树，geometry 用临时 `bpy.data.node_groups.new("__mcp_probe","GeometryNodeTree")`；对每个 `bpy.types` 名以 prefix 开头且有 `bl_rna` 的类型尝试 `nodes.new()`，读 inputs/outputs 名，最后删临时数据块。type 名允许省略前缀（"TexNoise" → "ShaderNodeTexNoise"）。
- `set_color_ramp`: `node.color_ramp.elements`：先删到 1 个，再 `elements.new(pos)` 逐个设 color。
- `build`: nodes 项 `{type, name?, location?, inputs?, properties?}`，links 项同 link 参数；`clear` 先 `nodes.clear()`。

**Tests:** add TexNoise + link 到 Base Color → list 里 links 有一条；set_node_input 数值；set_color_ramp 三档；build_node_tree 一次建 Noise→ColorRamp→Principled；get_node_types("shader","noise") 含 ShaderNodeTexNoise 且 inputs 含 "Scale"。

---

### Task 11: Lights（6）

**Interfaces:**
```python
list_lights() -> list[dict]
get_light_info(name: str) -> dict
create_light(type: str, name=None, location=None, rotation=None, energy=None, color=None, radius=None, size=None,
             spot_size=None, spot_blend=None, target=None) -> dict
set_light(name: str, energy=None, color=None, radius=None, size=None, shape=None, spot_size=None, spot_blend=None,
          use_shadow=None, angle=None) -> dict
point_light_at(light: str, target, use_constraint: bool = False) -> dict
set_world_lighting(color=None, strength=None, hdri_path=None, rotation=None) -> dict
```
**要点:** `bpy.data.lights.new(name, type)` + object + `link_to_scene`；`radius` → `shadow_soft_size`；AREA 用 `size/shape`；SUN 用 `angle`；`point_light_at` 与相机共用 `utils.look_at(obj, target)`（把它加进 utils：`direction.to_track_quat('-Z','Y').to_euler()`；`use_constraint` 加 TRACK_TO，target 为坐标时先建 Empty）。`set_world_lighting`: `world.use_nodes`（world 在 5.2 仍有 use_nodes）；Background 节点 Color/Strength；hdri → Environment Texture + Mapping + Texture Coordinate，rotation 写进 Mapping.Rotation。

**Tests:** 四种 type 各建一个；set_light energy；point_light_at Cube 后 light 的 -Z 轴指向 Cube（用 `execute_code` 算 `(obj.matrix_world.to_quaternion() @ Vector((0,0,-1))).dot((target-loc).normalized()) > 0.99`）；set_world_lighting color+strength 后 world 节点值正确。

---

### Task 12: Modifiers（8）

**Interfaces:**
```python
list_modifier_types(filter: str | None = None) -> list[dict]
list_modifiers(object: str) -> list[dict]
get_modifier_settings(object: str, modifier: str) -> dict
add_modifier(object: str, type: str, name=None, settings: dict | None = None) -> dict
set_modifier(object: str, modifier: str, settings: dict) -> dict
remove_modifier(object: str, modifier: str) -> dict
apply_modifier(object: str, modifier: str) -> dict
move_modifier(object: str, modifier: str, index: int | None = None, direction: str | None = None) -> dict
```
**要点:** 类型枚举来自 `bpy.types.ObjectModifiers.bl_rna.functions['new'].parameters['type'].enum_items`；`list_modifier_types` 对每种类型在临时 Cube 上 `modifiers.new` 一次读 `rna_props`（结果缓存到模块级 dict）；`add_modifier` 后 `set_props(mod, settings, tool_hint=f"{type}: ")`；`apply_modifier` → `select_only([o]); bpy.ops.object.modifier_apply(modifier=name)`；`move_modifier` → `bpy.ops.object.modifier_move_to_index(modifier=, index=)`，direction UP/DOWN/TOP/BOTTOM 换算 index。

**Tests:** 22 种类型参数化各 add 一次（BOOLEAN/SHRINKWRAP/CURVE/LATTICE/ARMATURE 等需要目标的先建目标对象），断言 list_modifiers 含之；SUBSURF levels=2 + apply 后顶点数 386；unknown setting 报错含 "levels"；move 到 index 0。

---

### Task 13: Geometry Nodes（11）

**Interfaces:**
```python
list_node_groups(type: str | None = None) -> list[dict]
create_geometry_nodes(object: str, group_name: str | None = None, modifier_name: str | None = None) -> dict
get_node_tree(node_group: str) -> dict
add_geometry_node(node_group: str, type: str, name=None, location=None, inputs=None, properties=None) -> dict
remove_geometry_node(node_group: str, node: str) -> dict
link_geometry_nodes(node_group: str, from_node: str, from_socket, to_node: str, to_socket) -> dict
unlink_geometry_nodes(node_group: str, to_node: str, to_socket) -> dict
set_geometry_node_input(node_group: str, node: str, socket, value) -> dict
add_group_socket(node_group: str, name: str, in_out: str = "INPUT", socket_type: str = "NodeSocketFloat", default=None) -> dict
set_gn_modifier_input(object: str, modifier: str, input: str, value) -> dict
build_geometry_node_tree(node_group: str, nodes: list[dict], links: list[dict], clear: bool = False) -> dict
```
**要点:** `create_geometry_nodes`: `bpy.data.node_groups.new(name, "GeometryNodeTree")`；`tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")` 与 OUTPUT；`NodeGroupInput`/`NodeGroupOutput` 节点并连；`mod = o.modifiers.new(name, "NODES"); mod.node_group = tree`。`set_gn_modifier_input`: 在 `tree.interface.items_tree` 按 name 找 `identifier`，`mod[identifier] = value`（Object 类型按名解析）。

**Tests:** create → get_node_tree 有 2 节点 1 连线；加 `GeometryNodeMeshCube` 接到 Group Output 后 Cube 的 evaluated mesh 顶点数 8（`execute_code` 里 `obj.evaluated_get(depsgraph).data.vertices`）；add_group_socket Float "Size" + set_gn_modifier_input 生效；build 一次建 Distribute Points on Faces。

---

### Task 14: Camera（7）

**Interfaces:**
```python
list_cameras() -> list[dict]
get_camera_info(name: str) -> dict
create_camera(name=None, location=None, rotation=None, lens=None, type=None, sensor_width=None, clip_start=None, clip_end=None, set_active: bool = True) -> dict
set_camera(name: str, lens=None, type=None, ortho_scale=None, clip_start=None, clip_end=None, shift_x=None, shift_y=None, dof: dict | None = None) -> dict
set_active_camera(name: str) -> dict
point_camera_at(camera: str, target, use_constraint: bool = False) -> dict
frame_objects(camera: str, objects, margin: float = 1.1) -> dict
```
**要点:** `dof` 键 `enabled/focus_object/focus_distance/fstop` → `cam.data.dof.use_dof/focus_object/focus_distance/aperture_fstop`。`frame_objects`: 收集所有对象世界空间包围盒角点 → 中心 + 半径 r；`fov = min(cam.angle_x, cam.angle_y)`；`dist = r / sin(fov/2) * margin`；沿相机当前朝向（`matrix_world.to_quaternion() @ Vector((0,0,-1))`）反向放置，再 `look_at`。

**Tests:** create 后 scene.camera 为它；set_camera dof；frame_objects 后 Cube 中心在相机视锥内（`bpy_extras.object_utils.world_to_camera_view` 结果 0<x<1, 0<y<1, z>0，用 execute_code 校验）。

---

### Task 15: Render（7）

**Interfaces:**
```python
get_render_settings() -> dict
set_render_settings(engine=None, resolution: list[int] | None = None, percentage=None, samples=None, fps=None, file_format=None,
                    color_mode=None, output_path=None, film_transparent=None, motion_blur=None, denoise=None, engine_settings: dict | None = None) -> dict
set_color_management(view_transform=None, look=None, exposure=None, gamma=None) -> dict
list_render_engines() -> list[str]
render_image(output_path: str | None = None, frame: int | None = None, return_image: bool = True, max_preview_size: int = 512) -> Image | dict   # timeout=LONG
render_animation(output_path: str, frame_start=None, frame_end=None) -> dict                                                              # timeout=LONG
viewport_screenshot(output_path: str | None = None, return_image: bool = True) -> Image | dict
```
**要点:** `samples` 按引擎写 `scene.eevee.taa_render_samples` / `scene.cycles.samples`；`denoise` → `scene.cycles.use_denoising`；`engine_settings` 用 `set_props(scene.eevee 或 scene.cycles, ...)`。`list_render_engines`: `["BLENDER_EEVEE","BLENDER_WORKBENCH","CYCLES"] + [e.bl_idname for e in bpy.types.RenderEngine.__subclasses__()]` 去重。`render_image`: 默认输出 `tmp/render_<frame>.png`（绝对路径）；`bpy.ops.render.render(write_still=True)`；预览：`bpy.data.images.load` → `img.scale()` 到 max 边 → `save_render` 到临时 png → base64；返回 `{"path","image_base64","mime","resolution"}`。`viewport_screenshot`: `bpy.app.background` → `no_viewport()`；GUI：找 `VIEW_3D` area/WINDOW region，`with bpy.context.temp_override(window=, area=, region=): bpy.ops.screen.screenshot_area(filepath=)`。

**Tests:** set/get 往返；render_image 用 WORKBENCH 64×64（EEVEE 在无头 macOS 可能无 GPU 上下文，测试固定 WORKBENCH），文件存在且 base64 非空；render_animation 2 帧生成 2 个文件；viewport_screenshot 无头下报 NoViewportError。

---

### Task 16: Import/Export（5）

**Interfaces:**
```python
import_file(path: str, format: str | None = None, options: dict | None = None, collection: str | None = None) -> dict   # {"objects":[新对象名]}
export_file(path: str, format: str | None = None, objects=None, options: dict | None = None) -> dict
append_from_blend(path: str, datablock: str, name: str, link: bool = False) -> dict
save_blend(path: str | None = None, compress: bool = False) -> dict
open_blend(path: str, load_ui: bool = False) -> dict
```
**要点:** 后缀表：obj→`wm.obj_import/obj_export(export_selected_objects)`；fbx→`import_scene.fbx/export_scene.fbx(use_selection)`；gltf/glb→`import_scene.gltf/export_scene.gltf(export_format=GLB|GLTF_SEPARATE, use_selection)`；usd/usda/usdc→`wm.usd_import/usd_export(selected_objects_only)`；stl→`wm.stl_import/stl_export(export_selected_objects)`；ply→`wm.ply_import/ply_export(export_selected_objects)`；abc→`wm.alembic_import/alembic_export(selected)`；blend→`bpy.data.libraries.load` 追加全部 objects。`objects` 给了就 `select_only` 后带 selected 参数，否则全选。新增对象 = 导入前后 `bpy.data.objects` 名字差集。

**Tests:** 每种格式 export Cube 到 `tmp/` 再 import 回来，新增对象 ≥1（abc 导入的对象名可能不同，只看数量）；save_blend + open_blend 往返（open 后 `ping` 仍通，对象存在）；append_from_blend 从刚保存的 blend 追加 objects "Cube" 得到 "Cube.001"。

---

### Task 17: Animation（15）

**Interfaces:**
```python
get_animation_info(object: str | None = None) -> dict
set_frame_range(start: int, end: int, fps: int | None = None) -> dict
set_current_frame(frame: int) -> dict
insert_keyframe(object: str, data_path: str, frame: int | None = None, index: int | None = None, value=None) -> dict
insert_keyframes_batch(object: str, keys: list[dict]) -> dict
delete_keyframe(object: str, data_path: str, frame: int, index: int | None = None) -> dict
list_keyframes(object: str, data_path: str | None = None) -> list[dict]
set_interpolation(object: str, mode: str, easing: str | None = None, data_path: str | None = None, frame_range: list[int] | None = None) -> dict
add_fcurve_modifier(object: str, data_path: str, type: str, settings: dict | None = None) -> dict
assign_action(object: str, action: str | None = None) -> dict
nla_push_down(object: str) -> dict
add_nla_strip(object: str, action: str, frame_start: int, track: str | None = None, blend_type: str | None = None) -> dict
bake_animation(object: str, frame_start=None, frame_end=None, step: int = 1, visual_keying: bool = True, clear_constraints: bool = False) -> dict  # LONG
list_shape_keys(object: str) -> list[dict]
set_shape_key(object: str, name: str, value: float, frame: int | None = None) -> dict
```
**要点:** `_fcurves(obj)`: `ad = obj.animation_data; act = ad.action`；先试 `act.fcurves`（5.2 legacy 访问器），异常则走 `act.layers[0].strips[0].channelbag(ad.action_slot).fcurves`；两条路都写，实测哪条通用哪条（记进 PITFALLS）。`insert_keyframe`: value 给了先 `setattr`/`path_resolve` 写入再 `obj.keyframe_insert(data_path, frame=, index=index if index is not None else -1)`。`set_interpolation`: 遍历 fcurve.keyframe_points 设 `interpolation/easing`。`nla_push_down`: `track = ad.nla_tracks.new(); track.strips.new(act.name, int(act.frame_range[0]), act); ad.action = None`。`bake_animation`: `select_only([o]); bpy.ops.nla.bake(frame_start=, frame_end=, step=, only_selected=True, visual_keying=, clear_constraints=, bake_types={'OBJECT'})`。`set_shape_key`: 无 shape_keys 先 `shape_key_add(name="Basis")`；不存在则 `shape_key_add(name=name, from_mix=False)`；`frame` 给了 `kb.keyframe_insert("value", frame=frame)`。

**Tests:** insert 两帧 location 后 list_keyframes 有 3 条 fcurve×2 点；set_current_frame 到中间帧 location 插值正确；set_interpolation LINEAR 后 keyframe_points[0].interpolation == 'LINEAR'（execute_code 校验）；add_fcurve_modifier CYCLES 后 frame 超范围仍循环；nla_push_down 后 action None 且 track 1 条；bake 后关键帧数 == 帧数；shape key 设值。

---

### Task 18: UV & Texture（10）

**Interfaces:**
```python
list_uv_maps(object: str) -> list[dict]
add_uv_map(object: str, name: str | None = None, set_active: bool = True) -> dict
remove_uv_map(object: str, name: str) -> dict
unwrap_uv(object: str, method: str = "ANGLE_BASED", margin: float = 0.001, angle_limit: float | None = None, uv_map: str | None = None) -> dict
pack_uv_islands(object: str, margin: float = 0.001, rotate: bool = True) -> dict
mark_seams(object: str, edges: list[int] | None = None, from_sharp: bool = False, clear: bool = False) -> dict
create_image(name: str, width: int = 1024, height: int = 1024, color=None, alpha: bool = True, float_buffer: bool = False) -> dict
bake_texture(object: str, bake_type: str, image: str | None = None, size: int = 1024, output_path: str | None = None, margin: int = 16,
             selected_to_active: bool = False, cage_extrusion: float = 0.0, samples: int = 16) -> dict   # LONG
save_image(image: str, path: str, format: str | None = None) -> dict
list_images() -> list[dict]
```
**要点:** `unwrap_uv`: `with mode(o,'EDIT'): bpy.ops.mesh.select_all(action='SELECT')` 后按 method：ANGLE_BASED/CONFORMAL → `bpy.ops.uv.unwrap(method=, margin=)`；SMART_PROJECT → `uv.smart_project(angle_limit=radians(66), island_margin=margin)`；CUBE/CYLINDER/SPHERE → `uv.cube_project()` 等；LIGHTMAP → `uv.lightmap_pack()`。`mark_seams` 用 bmesh `e.seam`。`bake_texture`: 引擎切 CYCLES、`scene.cycles.samples=samples`、`scene.cycles.device='CPU'`；image 不存在则 `images.new(size)`；每个材质加 `ShaderNodeTexImage` 设 image 并 `nodes.active = node`；`select_only([o]); bpy.ops.object.bake(type=bake_type, margin=margin, use_selected_to_active=, cage_extrusion=)`；`output_path` 给了 `image.filepath_raw=...; image.file_format='PNG'; image.save()`。

**Tests:** add/remove uv map；unwrap 每种 method 后 UV 坐标非全零；mark_seams 4 条边后 seam 数 4；create_image 尺寸；bake EMIT 64px samples=1 到 tmp 文件存在（Cube 上给 emission 材质）；save_image。

---

### Task 19: Batch（8）

**Interfaces:**
```python
batch_transform(objects, location=None, rotation=None, scale=None, relative: bool = True) -> dict
batch_rename(objects, prefix: str | None = None, suffix: str | None = None, find: str | None = None, replace: str | None = None, numbering: bool = False) -> dict
batch_apply_material(objects, material: str) -> dict
batch_add_modifier(objects, type: str, settings: dict | None = None) -> dict
batch_set_property(objects, data_path: str, value) -> dict
batch_delete(objects) -> dict
distribute_objects(objects, mode: str = "LINE", spacing: float = 2.0, axis: str = "X", columns: int = 5, radius: float = 5.0, center=None) -> dict
randomize_transform(objects, location=None, rotation=None, scale=None, uniform_scale: bool = True, seed: int = 0) -> dict
```
**要点:** `batch_set_property`: `data_path` 形如 `"scale"`、`"data.materials"`、`"modifiers['Bevel'].width"` → 拆最后一段：`base = o.path_resolve(prefix)` 后 `setattr(base, last, value)`；无 `.` 时直接 `setattr(o, path, value)`。`numbering` 给 `_001` 递增。`randomize_transform`: `random.Random(seed)`，各范围 ±。

**Tests:** batch_rename prefix+numbering → "P_Cube_001"；distribute 3 个 LINE 间距 2 → x = 0,2,4；GRID；CIRCLE 半径；randomize 同 seed 两次结果一致；batch_set_property `"modifiers['Bevel'].width"`。

---

### Task 20: Rigging（12）

**Interfaces:**
```python
create_armature(name: str | None = None, location=None, bones: list[dict] | None = None) -> dict
list_bones(armature: str, pose: bool = False) -> list[dict]
add_bone(armature: str, name: str, head: list[float], tail: list[float], parent: str | None = None, roll: float = 0.0, connect: bool = False) -> dict
set_bone(armature: str, bone: str, head=None, tail=None, roll=None, parent=None, connect=None, deform=None, inherit_scale=None) -> dict
remove_bone(armature: str, bone: str) -> dict
parent_to_armature(objects, armature: str, method: str = "AUTOMATIC") -> dict
add_bone_constraint(armature: str, bone: str, type: str, settings: dict | None = None) -> dict
set_pose(armature: str, bones: dict, keyframe: bool = False, frame: int | None = None) -> dict
reset_pose(armature: str, bones: list[str] | None = None) -> dict
set_vertex_group_weights(object: str, group: str, weights: list[list[float]] | None = None, all: float | None = None, mode: str = "REPLACE") -> dict
add_rigify_metarig(type: str = "human", name: str | None = None) -> dict
generate_rigify_rig(metarig: str) -> dict   # LONG
```
**要点:** 骨骼编辑都在 `with mode(arm_obj, 'EDIT')` 内用 `arm.edit_bones`；`parent_to_armature` method 映射 AUTOMATIC→ARMATURE_AUTO、ENVELOPE→ARMATURE_ENVELOPE、EMPTY_GROUPS→ARMATURE_NAME、DEFORM→ARMATURE；`select_only(meshes + [arm], arm); bpy.ops.object.parent_set(type=...)`。约束：`pbone = arm_obj.pose.bones[bone]; c = pbone.constraints.new(type)`；settings 里 `target` 按对象名解析，其余 `set_props`。`set_pose`: 有 `rotation_quaternion` 时先 `rotation_mode='QUATERNION'`；keyframe 时对给的通道 `pbone.keyframe_insert(channel, frame=frame)`。Rigify: `bpy.ops.preferences.addon_enable(module="rigify")`；metarig type → `bpy.ops.object.armature_human_metarig_add` / `armature_basic_human_metarig_add` / `armature_basic_quadruped_metarig_add`；generate: `select_only([m], m); bpy.ops.pose.rigify_generate()`，返回 `{"rig": m.data.rigify_target_rig.name}`。

**Tests:** create_armature 三根骨链 → list_bones 3 条且 parent 正确；parent_to_armature Cube AUTOMATIC 后 Cube 有 ARMATURE 修改器和顶点组；IK 约束存在；set_pose 旋转后 pose 矩阵变化；set_vertex_group_weights all=1 后权重；Rigify basic_human 生成 rig 对象存在（`timeout=LONG`）。

---

### Task 21: Rig Diagnostics（7）

**Interfaces:**
```python
check_rig(armature: str) -> dict                       # {"issues":[{severity,code,bone?,object?,message,fix_hint}], "summary":{...}}
check_bone_hierarchy(armature: str) -> dict           # {"roots":[...tree], "orphans":[...]}
check_bone_naming(armature: str, convention: str = "BLENDER") -> dict
find_unweighted_vertices(object: str, threshold: float = 0.0001) -> dict
get_bone_influence(object: str, vertex_index: int) -> list[dict]
list_constraint_issues(armature: str) -> list[dict]
normalize_weights(object: str, lock_active: bool = False, groups: list[str] | None = None) -> dict
```
**要点:** `check_rig` 汇总规则码：`ZERO_LENGTH_BONE`、`MULTIPLE_ROOTS`(info)、`DEFORM_BONE_NO_GROUP`（deform 骨在任一子网格无同名顶点组）、`UNWEIGHTED_VERTS`、`UNNORMALIZED_WEIGHTS`（和 >1.001 或 <0.999）、`UNAPPLIED_SCALE`（骨架或子网格 scale ≠ 1）、`CONSTRAINT_TARGET_MISSING`、`ASYMMETRIC_NAME`（`.L` 无对应 `.R`）。`normalize_weights`: 逐顶点把各组权重按和归一，`lock_active` 时活动组不动。

**Tests:** 构造坏骨架（零长骨、`.L` 无 `.R`、未权重 Cube、缩放 2）→ check_rig 命中对应 code；normalize 后权重和 1。

---

### Task 22: Assets（8）— server 侧联网

**Files:** `src/blender_mcp_pro/assets/{cache,polyhaven,sketchfab}.py`、`tests/test_assets.py`、`handlers/assets.py`（只有 3 个本地工具）、`tools/assets.py`

**Interfaces（server）:**
```python
polyhaven_categories(asset_type: str = "hdris") -> dict
polyhaven_search(asset_type: str = "hdris", categories: list[str] | None = None, query: str | None = None, limit: int = 20) -> list[dict]
polyhaven_download(asset_id: str, asset_type: str, resolution: str = "1k", file_format: str | None = None) -> dict   # LONG
sketchfab_search(query: str, categories: list[str] | None = None, count: int = 20, downloadable: bool = True) -> list[dict]
sketchfab_download(uid: str) -> dict                                                                                  # LONG
list_asset_libraries() -> list[dict]
search_local_assets(library: str | None = None, type: str | None = None, query: str | None = None) -> list[dict]
import_local_asset(library: str, name: str, type: str = "objects", link: bool = False) -> dict
```
**要点（server 侧）:** Poly Haven API：`GET https://api.polyhaven.com/categories/{type}`、`/assets?t={type}&c={cats}`、`/files/{id}`。hdris：`files["hdri"][res]["hdr"|"exr"]["url"]` → 下载到 `cache/hdris/<id>_<res>.hdr` → `call("set_world_lighting", hdri_path=...)`。textures：取 `Diffuse/Rough/nor_gl/Displacement/AO` 各 `[res]["jpg"]["url"]`（缺的跳过）→ `call("create_pbr_material", name=id, ...)`。models：`files["gltf"][res]["gltf"]` 的 `url` + `include` 里所有文件按相对路径落到 `cache/models/<id>/` → `call("import_file", path=gltf)`。Sketchfab：`GET https://api.sketchfab.com/v3/search?type=models&q=&downloadable=true`；下载 `GET /v3/models/{uid}/download`（header `Authorization: Token <t>`，t 来自 `call("get_secret", key="sketchfab_token")`，为空报错说明去偏好里填）→ `["glb"]["url"]` 下载 → `import_file`。httpx 超时 60s，下载流式写文件，已存在则复用缓存。
**要点（addon 侧）:** `list_asset_libraries`: `preferences.filepaths.asset_libraries` 的 name/path；`search_local_assets`: 遍历库目录 `*.blend`，`with bpy.data.libraries.load(p) as (src, _): names = getattr(src, type)`，query 子串过滤；`import_local_asset`: `libraries.load(p, link=link)` 把 `data_to.<type> = [name]`，objects 类型 link 进 scene collection。

**Tests:** 本地三工具用测试自建的资产库（`tmp/assetlib/lib.blend`：在无头 Blender 里 `execute_code` 保存一个含 "AssetCube" 的 blend，再通过 `execute_code` 往 `preferences.filepaths.asset_libraries` 加一条指向 `tmp/assetlib`）；联网测试标 `@pytest.mark.skipif(not os.environ.get("BLENDER_MCP_ONLINE_TESTS"))`：polyhaven_categories("hdris") 非空；polyhaven_download 一个 1k HDRI 后 world 有 Environment Texture。server 侧 `polyhaven.py` 的 URL 解析用 `respx` 之类假响应？——不引入新依赖：把 `_pick_files(files_json, asset_type, res, fmt) -> list[(url, relpath)]` 写成纯函数，单测直接喂 JSON 样例。

---

### Task 23: Workflows（7）

**Interfaces:**
```python
setup_three_point_lighting(target: str, distance: float = 6.0, height: float = 3.0, key_energy: float = 1000.0, fill_ratio: float = 0.4, rim_ratio: float = 0.8, color_temp: float | None = None) -> dict
setup_studio_scene(subject: str | None = None, backdrop: bool = True, ground: bool = True, hdri_path: str | None = None, camera: bool = True) -> dict
turntable_animation(object: str, frames: int = 120, revolutions: float = 1.0, camera: str | None = None) -> dict
quick_product_render(object: str, output_path: str, resolution: list[int] | None = None, samples: int = 64, engine: str = "BLENDER_EEVEE") -> Image | dict   # LONG
material_from_texture_folder(folder: str, name: str | None = None, assign_to: str | None = None) -> dict
scatter_objects(source: str, surface: str, count: int = 100, seed: int = 0, scale_range: list[float] | None = None, align_to_normal: bool = True, method: str = "GEOMETRY_NODES") -> dict
export_for_game(objects, path: str, format: str = "GLB", apply_modifiers: bool = True, triangulate: bool = True, scale: float = 1.0, forward: str = "-Z", up: str = "Y") -> dict
```
**要点:** 直接 import 其他 handler 模块的函数调用（`from . import lights, camera, render, ...`），不走 socket。`setup_three_point_lighting`: Key 在目标前左上 45°、Fill 前右下弱光、Rim 后上方，均 `look_at` 目标，AREA 灯；`color_temp` 用 `ShaderNodeBlackbody` 近似 → 简化：按开尔文查表 5 档得 RGB（写在模块级常量表）。`setup_studio_scene`: backdrop = 平面 + 后缘 extrude 上弯（用 `bmesh` 建 L 形再 bevel 内角），材质中性灰。`turntable_animation`: 空物体作父级，rotation_euler.z 在 1 与 frames 帧打关键帧，LINEAR + CYCLES。`material_from_texture_folder`: 文件名小写含关键字表 `{"base_color": ("basecolor","albedo","diffuse","col"), "roughness": ("rough",), "metallic": ("metal",), "normal": ("nor","normal"), "height": ("height","disp","displacement"), "ao": ("ao","ambient")}` → `create_pbr_material`。`scatter_objects`: GEOMETRY_NODES → 在 surface 上建树：Group Input → Distribute Points on Faces(density 由 count/面积估) → Instance on Points(instance=source 的 Object Info) → Join 原几何；COLLECTION_INSTANCES → 用 `bmesh` 随机取面点放置副本。`export_for_game`: 复制对象到临时集合、`modifier_apply` 全部、`TRIANGULATE` 修改器并应用、缩放，调 `io.export_file`，最后删临时副本。

**Tests:** 三点光后 3 盏 AREA 灯存在且都朝向目标；studio 场景对象数增加；turntable 后 Cube 父级 Z 旋转 fcurve 2 点 + CYCLES 修改器；material_from_texture_folder 用 tmp 里造的 `wood_basecolor.png/wood_roughness.png` 识别出 2 张；scatter 后 evaluated 实例数 == count（`execute_code` 数 depsgraph object_instances）；export_for_game 输出 glb 存在。

---

### Task 24: 文档、MAINTENANCE、装进真实 Blender、接 Claude Code

**Files:** `docs/README.md`、`docs/tools.md`、`.claude/MAINTENANCE.md`、`.claude/PITFALLS.md`（如有坑）

- [ ] **Step 1: 生成工具清单** `uv run blender-mcp-pro dump-tools > docs/tools.md`，检查行数 == 159。
- [ ] **Step 2: docs/README.md**：项目一句话；架构图（spec §2 那张）；安装三条命令；Claude Code 接入命令；GUI 里启用/启动 server；开发（`uv run pytest -q`、Reload Scripts）；已知限制（viewport_screenshot 需 GUI、EEVEE 无头渲染取决于 GPU、Sketchfab 要 token）。
- [ ] **Step 3: .claude/MAINTENANCE.md**（≤150 行）：快照 3 行；架构约束（handler 顶层不许 bpy 调用；无头 timers 不触发；插件零联网；工具名两边对账）；关键决策指路 spec §9；进行中/待办；部署注意（extensions 目录软链、GUI 与 headless 争抢 userpref）。
- [ ] **Step 4: 装进真实 Blender** `uv run blender-mcp-pro install-addon`；提示用户在已打开的 GUI 里 Preferences ▸ Add-ons 启用「Blender MCP Pro (local)」（或重启 Blender），N 面板确认 running。
- [ ] **Step 5: 接 Claude Code** `claude mcp add --scope user blender-pro -- uv --directory /Users/panda/Documents/github/blender_mcp run blender-mcp-pro serve`，`claude mcp list` 看到 Connected。
- [ ] **Step 6: GUI 端到端**：用 `uv run python -c` 直连 9877 跑 `ping`、`get_scene_info`、`create_primitive`、`viewport_screenshot`，截图文件存在。
- [ ] **Step 7: Commit** docs + .claude 文件。

## Self-Review 记录

- Spec 覆盖：§2 架构 → Task 1–6；§3 协议 → Task 2–3；§4 约定 → Task 3 utils + 模板；§5 十七类 → Task 7–23（数量核对：16+13+9+10+6+8+11+7+7+5+15+8+12+7+8+7+10 = 159 ✓）；§6 错误 → Task 2–3；§7 测试 → Task 4–5 + 各类目；§8 安装 → Task 6、24；§9 决策 → Task 24 MAINTENANCE。
- 类型一致性：`call(tool, timeout=, **params)` 全程一致；`resolve_objects` 接受 `list[str] | dict | str`；`look_at` 在 Task 11 加进 utils，Task 14 复用；`nodes_common` 在 Task 10 建，Task 13 复用。
- 无占位：Task 1–6 全代码；Task 7–23 为契约 + 行为 + 测试要点，执行者即本会话作者，实现时直接落文件。
