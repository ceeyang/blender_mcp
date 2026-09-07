import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call


def test_ping(blender):
    r = call(blender, "ping")
    assert r["blender"].startswith("5.2") and r["background"] is True


def test_reset_scene_gives_factory_objects(blender):
    r = call(blender, "reset_scene")
    assert sorted(r["objects"]) == ["Camera", "Cube", "Light"]


def test_unknown_tool_error(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "no_such_tool")
    assert ei.value.type == "UnknownTool"


def test_error_carries_traceback(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "get_secret")
    assert ei.value.type == "TypeError" and "Traceback" in ei.value.traceback
