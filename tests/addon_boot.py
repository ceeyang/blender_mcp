"""blender -b --factory-startup --python tests/addon_boot.py -- --port N
从源码目录加载插件、起 server，并在主线程循环 drain（无头模式 timers 不触发）。"""
import os
import sys
import time

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 9877

root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon"))
sys.path.insert(0, root)

import blender_mcp_pro  # noqa: E402,F401
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
