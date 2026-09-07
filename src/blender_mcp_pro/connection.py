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
            except BlenderUnavailable:
                raise
            except (ConnectionError, OSError):
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
