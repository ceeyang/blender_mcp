"""端到端：mcp 客户端 --stdio--> 我们的 server --TCP--> 无头 Blender。"""
import asyncio
import json
import os
import pathlib
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = pathlib.Path(__file__).resolve().parents[1]


async def _session_run(port: int, fn):
    params = StdioServerParameters(command=sys.executable, args=["-m", "blender_mcp_pro.cli", "serve"], cwd=str(ROOT),
                                   env={**os.environ, "BLENDER_MCP_PORT": str(port), "PYTHONPATH": str(ROOT / "src")})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            return await fn(s)


def test_list_tools_and_call(blender):
    async def body(s):
        tools = await s.list_tools()
        names = {t.name for t in tools.tools}
        r = await s.call_tool("get_scene_info", {})
        r2 = await s.call_tool("create_primitive", {"type": "cube", "name": "ViaMCP", "location": [1, 2, 3]})
        bad = await s.call_tool("get_object_info", {"name": "Nope"})
        return names, r, r2, bad

    names, r, r2, bad = asyncio.run(_session_run(blender.port, body))
    assert len(names) == 159 and {"get_scene_info", "polyhaven_search", "render_image"} <= names
    assert not r.is_error
    payload = r.structured_content or json.loads(r.content[0].text)
    payload = payload.get("result", payload) if isinstance(payload, dict) else payload
    assert payload["object_count"] == 3
    assert not r2.is_error and "ViaMCP" in json.dumps(r2.structured_content or r2.content[0].text)
    assert bad.is_error and "Nope" in bad.content[0].text


def test_render_returns_image(blender):
    async def body(s):
        await s.call_tool("set_render_settings", {"engine": "BLENDER_WORKBENCH", "resolution": [32, 32]})
        return await s.call_tool("render_image", {"return_image": True})

    r = asyncio.run(_session_run(blender.port, body))
    assert not r.is_error
    assert "image" in [c.type for c in r.content]
