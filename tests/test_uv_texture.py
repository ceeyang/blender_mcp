import os

import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call, run_py


def test_uv_maps(blender):
    assert [u["name"] for u in call(blender, "list_uv_maps", object="Cube")] == ["UVMap"]
    r = call(blender, "add_uv_map", object="Cube", name="Lightmap")
    assert r["uv_maps"] == ["UVMap", "Lightmap"] and call(blender, "list_uv_maps", object="Cube")[1]["active"]
    assert call(blender, "remove_uv_map", object="Cube", name="Lightmap")["uv_maps"] == ["UVMap"]
    with pytest.raises(BlenderError):
        call(blender, "remove_uv_map", object="Cube", name="Nope")


@pytest.mark.parametrize("method", ["ANGLE_BASED", "CONFORMAL", "SMART_PROJECT", "CUBE", "CYLINDER", "SPHERE", "LIGHTMAP"])
def test_unwrap_methods(blender, method):
    call(blender, "create_primitive", type="uv_sphere", name="S")
    r = call(blender, "unwrap_uv", object="S", method=method)
    assert r["method"] == method and r["uv_bounds"]["max"] != r["uv_bounds"]["min"]
    assert call(blender, "get_object_info", name="S")["type"] == "MESH"


def test_seams_and_pack(blender):
    r = call(blender, "mark_seams", object="Cube", edges=[0, 1, 2, 3])
    assert r["seams"] == 4
    assert call(blender, "mark_seams", object="Cube", clear=True)["seams"] == 0
    run_py(blender, "me = bpy.data.objects['Cube'].data; me.edges[5].use_edge_sharp = True; result = 1")
    assert call(blender, "mark_seams", object="Cube", from_sharp=True)["seams"] == 1
    call(blender, "unwrap_uv", object="Cube", method="SMART_PROJECT")
    r = call(blender, "pack_uv_islands", object="Cube", margin=0.02)
    assert 0 <= r["uv_bounds"]["min"][0] and r["uv_bounds"]["max"][0] <= 1


def test_images(blender):
    r = call(blender, "create_image", name="Blank", width=64, height=32, color=[1, 0, 0])
    assert r["size"] == [64, 32]
    p = str(TMP / "blank.png")
    r = call(blender, "save_image", image="Blank", path=p)
    assert os.path.exists(p) and r["format"] == "PNG"
    assert any(i["name"] == "Blank" for i in call(blender, "list_images"))


def test_bake_emit(blender):
    call(blender, "create_material", name="Glow", emission_color=[0, 1, 0], emission_strength=1, assign_to="Cube")
    p = str(TMP / "bake_emit.png")
    r = call(blender, "bake_texture", object="Cube", bake_type="EMIT", size=32, samples=1, output_path=p, timeout=600)
    assert r["size"] == [32, 32] and os.path.exists(p)
    px = run_py(blender, "img = bpy.data.images['Cube_EMIT']; px = list(img.pixels); result = [max(px[0::4]), max(px[1::4])]")
    assert px[1] > 0.5 and px[0] < 0.1
