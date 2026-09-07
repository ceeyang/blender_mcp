import os
import pathlib
import socket
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_mcp_pro.cli import default_blender  # noqa: E402
from blender_mcp_pro.connection import BlenderConnection  # noqa: E402
from blender_mcp_pro.errors import BlenderTimeout, BlenderUnavailable  # noqa: E402

BLENDER = default_blender()
TMP = ROOT / "tmp"


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
    TMP.mkdir(exist_ok=True)
    port = _free_port()
    log = open(TMP / "blender_test.log", "w")
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
                raise RuntimeError(f"Blender failed to start; see {TMP / 'blender_test.log'}")
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


@pytest.fixture
def blender_or_none(request):
    """只有用到 blender 夹具的测试才拉起 Blender。"""
    if "blender" in request.fixturenames:
        return request.getfixturevalue("blender")
    return None


@pytest.fixture(autouse=True)
def fresh_scene(blender_or_none):
    if blender_or_none is not None:
        blender_or_none.call("reset_scene", {}, timeout=30)


def call(blender, tool, timeout=60.0, **params):
    return blender.call(tool, {k: v for k, v in params.items() if v is not None}, timeout=timeout)


def run_py(blender, code: str, var: str = "result"):
    """在 Blender 里执行代码并取回变量（依赖 Task 8 的 execute_code）。"""
    return blender.call("execute_code", {"code": code, "return_var": var}, timeout=120)["result"]
