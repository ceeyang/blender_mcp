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


def _recv_exact(sock: socket.socket, n: int):
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
