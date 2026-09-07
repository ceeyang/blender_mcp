import asyncio

from ..server import mcp

# 类目模块（每个类目追加一行）


def tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}
