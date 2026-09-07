import os

import pytest

from blender_mcp_pro.assets import polyhaven
from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call, run_py

ONLINE = bool(os.environ.get("BLENDER_MCP_ONLINE_TESTS"))

HDRI_FILES = {"hdri": {"1k": {"hdr": {"url": "https://x/a_1k.hdr"}, "exr": {"url": "https://x/a_1k.exr"}},
                       "2k": {"hdr": {"url": "https://x/a_2k.hdr"}}}}
TEX_FILES = {"blend": {}, "Diffuse": {"1k": {"jpg": {"url": "https://x/d.jpg"}}}, "Rough": {"1k": {"png": {"url": "https://x/r.png"}}},
             "nor_gl": {"1k": {"jpg": {"url": "https://x/n.jpg"}}}, "Displacement": {"1k": {"exr": {"url": "https://x/h.exr"}}},
             "AO": {"2k": {"jpg": {"url": "https://x/ao2k.jpg"}}}}
MODEL_FILES = {"gltf": {"1k": {"gltf": {"url": "https://x/m.gltf", "include": {"m.bin": {"url": "https://x/m.bin"},
                                                                                "textures/m_diff_1k.jpg": {"url": "https://x/t.jpg"}}}}}}


def test_pick_files_pure():
    h = polyhaven.pick_files("a", HDRI_FILES, "hdri", "1k")
    assert h == [{"url": "https://x/a_1k.hdr", "relpath": "hdris/a_1k.hdr", "role": "hdri"}]
    assert polyhaven.pick_files("a", HDRI_FILES, "hdris", "1k", "exr")[0]["relpath"].endswith(".exr")
    with pytest.raises(ValueError):
        polyhaven.pick_files("a", HDRI_FILES, "hdris", "8k")
    t = polyhaven.pick_files("wood", TEX_FILES, "textures", "1k")
    assert [x["role"] for x in t] == ["base_color", "roughness", "normal", "height"]
    assert t[1]["relpath"] == "textures/wood/wood_1k_roughness.png" and t[3]["url"].endswith("h.exr")
    m = polyhaven.pick_files("chair", MODEL_FILES, "models", "1k")
    assert m[0]["relpath"] == "models/chair/chair.gltf" and m[2]["relpath"] == "models/chair/textures/m_diff_1k.jpg"
    with pytest.raises(ValueError):
        polyhaven.norm_type("videos")


@pytest.fixture
def local_lib(blender):
    lib = TMP / "assetlib"
    lib.mkdir(exist_ok=True)
    path = str(lib / "lib.blend")
    run_py(blender, f"""
bpy.ops.mesh.primitive_cube_add(); o = bpy.context.active_object; o.name = 'AssetCube'; o.asset_mark()
m = bpy.data.materials.new('AssetMat'); m.asset_mark()
bpy.ops.wm.save_as_mainfile(filepath=r'{path}', copy=True)
bpy.data.objects.remove(o); bpy.data.materials.remove(m)
bpy.ops.preferences.asset_library_add(directory=r'{lib}')
bpy.context.preferences.filepaths.asset_libraries[-1].name = 'TestLib'
result = 1""")
    return "TestLib"


def test_local_assets(blender, local_lib):
    libs = call(blender, "list_asset_libraries")
    lib = next(l for l in libs if l["name"] == "TestLib")
    assert lib["exists"] and lib["blend_files"] == 1
    r = call(blender, "search_local_assets", library="TestLib")
    assert {(x["type"], x["name"]) for x in r} == {("objects", "AssetCube"), ("materials", "AssetMat"), ("meshes", "Cube")} or \
        {("objects", "AssetCube"), ("materials", "AssetMat")} <= {(x["type"], x["name"]) for x in r}
    assert [x["name"] for x in call(blender, "search_local_assets", library="TestLib", type="materials", query="mat")] == ["AssetMat"]
    r = call(blender, "import_local_asset", library="TestLib", name="AssetCube")
    assert r["name"] == "AssetCube" and call(blender, "get_object_info", name="AssetCube")["type"] == "MESH"
    with pytest.raises(BlenderError) as ei:
        call(blender, "import_local_asset", library="Nope", name="x")
    assert "TestLib" in ei.value.message


@pytest.mark.skipif(not ONLINE, reason="set BLENDER_MCP_ONLINE_TESTS=1 to hit Poly Haven")
def test_polyhaven_online(blender):
    cats = polyhaven.categories("hdris")
    assert "outdoor" in cats
    res = polyhaven.search("hdris", query="sky", limit=3)
    assert res and res[0]["id"]
    info = polyhaven.download_asset(res[0]["id"], "hdris", "1k")
    assert os.path.exists(info["files"]["hdri"])
    r = call(blender, "set_world_lighting", hdri_path=info["files"]["hdri"])
    assert r["hdri"]
