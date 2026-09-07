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
