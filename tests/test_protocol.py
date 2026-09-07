import importlib.util
import json
import pathlib
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

    threading.Thread(target=run, daemon=True).start()
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
    c = conn_mod.BlenderConnection("127.0.0.1", 1)
    with pytest.raises(BlenderUnavailable):
        c.call("ping", {})


def test_addon_protocol_matches():
    """addon 侧的编解码与 server 侧互通。"""
    p = pathlib.Path(__file__).resolve().parents[1] / "addon" / "blender_mcp_pro" / "protocol.py"
    spec = importlib.util.spec_from_file_location("addon_protocol", p)
    proto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proto)
    a, b = socket.socketpair()
    b.sendall(proto.encode({"id": "1", "ok": True, "result": [1, 2]}))
    assert _read_frame(a) == {"id": "1", "ok": True, "result": [1, 2]}
    a.sendall(_frame({"id": "2", "tool": "ping", "params": {}}))
    assert proto.read_frame(b) == {"id": "2", "tool": "ping", "params": {}}
