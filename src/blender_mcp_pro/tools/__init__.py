import asyncio

from ..server import mcp

from . import scene  # noqa: E402,F401
from . import utilities  # noqa: E402,F401
from . import materials  # noqa: E402,F401
from . import shader_nodes  # noqa: E402,F401
from . import lights  # noqa: E402,F401
from . import modifiers  # noqa: E402,F401
from . import geometry_nodes  # noqa: E402,F401
from . import camera  # noqa: E402,F401
from . import render  # noqa: E402,F401
from . import io  # noqa: E402,F401
from . import animation  # noqa: E402,F401
from . import uv_texture  # noqa: E402,F401
from . import batch  # noqa: E402,F401
from . import rigging  # noqa: E402,F401
from . import rig_diagnostics  # noqa: E402,F401


def tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}
