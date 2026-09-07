import os

import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call, run_py


def test_three_point(blender):
    r = call(blender, "setup_three_point_lighting", target="Cube", color_temp=4000)
    assert [l["name"] for l in r["lights"]] == ["Key", "Fill", "Rim"] and all(l["light_type"] == "AREA" for l in r["lights"])
    assert r["lights"][1]["energy"] == 400 and r["lights"][0]["color"][2] < 0.7
    dot = run_py(blender, "o = bpy.data.objects['Rim']; d = o.matrix_world.to_quaternion() @ Vector((0,0,-1)); "
                          "result = d.dot((bpy.data.objects['Cube'].location - o.location).normalized())")
    assert dot > 0.99


def test_studio_scene(blender):
    before = call(blender, "get_scene_info")["object_count"]
    r = call(blender, "setup_studio_scene", subject="Cube")
    assert "Backdrop" in r["created"] and r["camera"] == "StudioCam"
    assert call(blender, "get_scene_info")["object_count"] == before + 5
    assert call(blender, "get_object_info", name="Backdrop")["materials"] == ["Studio_Backdrop"]


def test_turntable(blender):
    r = call(blender, "turntable_animation", object="Cube", frames=48, revolutions=2)
    assert r["pivot"] == "Cube_Turntable" and r["camera"] == "TurntableCam"
    ks = call(blender, "list_keyframes", object="Cube_Turntable", data_path="rotation_euler")
    assert len(ks) == 1 and len(ks[0]["keyframes"]) == 2 and ks[0]["modifiers"] == ["CYCLES"] and ks[0]["keyframes"][0]["interpolation"] == "LINEAR"
    assert call(blender, "get_object_info", name="Cube")["parent"] == "Cube_Turntable"
    assert call(blender, "get_scene_info")["frame_end"] == 48


def test_quick_render(blender):
    p = str(TMP / "product.png")
    r = call(blender, "quick_product_render", object="Cube", output_path=p, resolution=[64, 48], samples=1, engine="BLENDER_WORKBENCH", timeout=600)
    assert os.path.exists(r["path"]) and r["camera"] == "ProductCam" and len(r["lights"]) == 3 and r["image_base64"]


def test_material_from_folder(blender):
    folder = TMP / "wood_tex"
    folder.mkdir(exist_ok=True)
    for n in ("wood_basecolor.png", "wood_roughness.png", "Wood_Normal-GL.png", "readme.txt"):
        run_py(blender, f"img = bpy.data.images.new('t', 4, 4); img.filepath_raw = r'{folder / n}'; img.file_format='PNG'; img.save(); bpy.data.images.remove(img); result=1") if n.endswith(".png") else (folder / n).write_text("x")
    r = call(blender, "material_from_texture_folder", folder=str(folder), assign_to="Cube")
    assert r["name"] == "wood_tex" and set(r["detected"]) == {"base_color", "roughness", "normal"}
    assert call(blender, "get_object_info", name="Cube")["materials"] == ["wood_tex"]
    with pytest.raises(BlenderError):
        call(blender, "material_from_texture_folder", folder=str(TMP))


def test_scatter_both_methods(blender):
    call(blender, "create_primitive", type="plane", name="Ground", size=10)
    call(blender, "create_primitive", type="ico_sphere", name="Rock", radius=0.2, location=[20, 20, 0])
    r = call(blender, "scatter_objects", source="Rock", surface="Ground", count=50, seed=3, scale_range=[0.5, 1.5])
    assert r["method"] == "GEOMETRY_NODES" and 20 <= r["instances"] <= 90
    r = call(blender, "scatter_objects", source="Rock", surface="Ground", count=12, method="COPIES")
    assert r["instances"] == 12 and call(blender, "get_object_info", name=r["objects"][0])["parent"] == "Scatter_Rock"


def test_export_for_game(blender):
    call(blender, "add_modifier", object="Cube", type="SUBSURF", settings={"levels": 1})
    p = str(TMP / "game" / "cube.glb")
    r = call(blender, "export_for_game", objects=["Cube"], path=p, scale=0.01)
    assert os.path.exists(p) and r["source_objects"] == ["Cube"] and r["format"] == "glb"
    info = call(blender, "get_object_info", name="Cube")
    assert info["modifiers"][0]["type"] == "SUBSURF" and info["scale"] == [1, 1, 1] and call(blender, "get_scene_info")["object_count"] == 3
    r = call(blender, "export_for_game", objects=["Cube"], path=str(TMP / "game" / "cube.fbx"), format="FBX")
    assert r["format"] == "fbx"
