import asyncio

from ..server import mcp

from . import scene  # noqa: E402,F401
from . import utilities  # noqa: E402,F401
from . import materials  # noqa: E402,F401
from . import shader_nodes  # noqa: E402,F401
from . import lights  # noqa: E402,F401


def tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}
