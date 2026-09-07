import os

import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call


@pytest.mark.parametrize("ext", ["obj", "fbx", "glb", "gltf", "usdc", "usda", "stl", "ply", "abc", "blend"])
def test_export_import_roundtrip(blender, ext):
    path = str(TMP / "io" / f"cube.{ext}")
    r = call(blender, "export_file", path=path, objects=["Cube"])
    assert r["format"] == ext and os.path.getsize(path) > 0
    before = call(blender, "get_scene_info")["object_count"]
    r = call(blender, "import_file", path=path)
    assert r["count"] >= 1 and call(blender, "get_scene_info")["object_count"] == before + r["count"]


def test_import_into_collection_and_errors(blender):
    path = str(TMP / "io" / "c.obj")
    call(blender, "export_file", path=path, objects=["Cube"])
    call(blender, "manage_collection", action="create", name="Imported")
    r = call(blender, "import_file", path=path, collection="Imported")
    assert call(blender, "get_object_info", name=r["objects"][0])["collections"] == ["Imported"]
    with pytest.raises(BlenderError):
        call(blender, "import_file", path="/nope/x.obj")
    with pytest.raises(BlenderError) as ei:
        call(blender, "export_file", path=str(TMP / "x.xyz"))
    assert "Supported" in ei.value.message


def test_save_open_append(blender):
    path = str(TMP / "io" / "scene.blend")
    r = call(blender, "save_blend", path=path)
    assert r["path"] == path
    with pytest.raises(BlenderError) as ei:
        call(blender, "append_from_blend", path=path, datablock="objects", name="Cube")
    assert "currently open" in ei.value.message
    call(blender, "save_blend", path=str(TMP / "io" / "scene2.blend"))
    call(blender, "delete_object", objects=["Cube"])
    r = call(blender, "append_from_blend", path=path, datablock="objects", name="Cube")
    assert r["name"] == "Cube" and call(blender, "get_scene_info")["object_count"] == 3
    with pytest.raises(BlenderError) as ei:
        call(blender, "append_from_blend", path=path, datablock="objects", name="Nope")
    assert "Cube" in ei.value.message
    call(blender, "delete_object", objects={"type": "MESH"})
    r = call(blender, "open_blend", path=path)
    assert sorted(r["objects"]) == ["Camera", "Cube", "Light"] and call(blender, "ping")["blender"]
