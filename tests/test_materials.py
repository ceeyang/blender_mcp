import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call, run_py


@pytest.fixture
def png(blender):
    path = str(TMP / "test_tex.png")
    run_py(blender, f"img = bpy.data.images.new('t', 8, 8); img.filepath_raw = r'{path}'; img.file_format = 'PNG'; img.save(); "
                    f"bpy.data.images.remove(img); result = 1")
    return path


def test_create_and_info(blender):
    r = call(blender, "create_material", name="Red", base_color=[1, 0, 0], roughness=0.2, metallic=1, assign_to="Cube")
    assert r["principled"]["Base Color"] == [1, 0, 0, 1] and r["principled"]["Roughness"] == 0.2 and r["objects"] == ["Cube"]
    assert call(blender, "get_object_info", name="Cube")["materials"] == ["Red"]
    assert [m["name"] for m in call(blender, "list_materials", used_only=True)] == ["Material", "Red"] or "Red" in [m["name"] for m in call(blender, "list_materials")]


def test_assign_slot(blender):
    call(blender, "create_material", name="A")
    call(blender, "create_material", name="B")
    call(blender, "assign_material", object="Cube", material="A")
    r = call(blender, "assign_material", object="Cube", material="B", slot=1)
    assert r["materials"] == ["A", "B"]
    with pytest.raises(BlenderError):
        call(blender, "assign_material", object="Camera", material="A")


def test_principled_inputs_and_bad_socket(blender):
    call(blender, "create_material", name="M")
    r = call(blender, "set_principled_inputs", material="M", inputs={"Roughness": 0.9, "Emission Color": [0, 1, 0], "Emission Strength": 2})
    assert r["changed"]["Roughness"] == 0.9 and r["changed"]["Emission Color"] == [0, 1, 0, 1]
    with pytest.raises(BlenderError) as ei:
        call(blender, "set_principled_inputs", material="M", inputs={"Specular": 0.5})
    assert "Specular IOR Level" in ei.value.message


def test_material_settings(blender):
    call(blender, "create_material", name="Glass", alpha=0.3)
    s = call(blender, "set_material_settings", material="Glass", backface_culling=True, displacement_method="BOTH")
    assert s["surface_render_method"] == "BLENDED" and s["backface_culling"] is True and s["displacement_method"] == "BOTH"


def test_image_textures(blender, png):
    call(blender, "create_material", name="T")
    n0 = call(blender, "get_material_info", name="T")["node_count"]
    r = call(blender, "add_image_texture", material="T", image_path=png, target="Base Color")
    assert r["target"] == "Base Color" and r["colorspace"] != "Non-Color"
    assert call(blender, "get_material_info", name="T")["node_count"] == n0 + 1
    r = call(blender, "add_image_texture", material="T", image_path=png, target="Normal")
    assert r["helper_node"] and call(blender, "get_material_info", name="T")["node_count"] == n0 + 3
    r = call(blender, "add_image_texture", material="T", image_path=png, target="Roughness")
    assert r["colorspace"] == "Non-Color"
    with pytest.raises(BlenderError):
        call(blender, "add_image_texture", material="T", image_path="/nope/x.png", target="Base Color")


def test_pbr_material(blender, png):
    r = call(blender, "create_pbr_material", name="PBR", base_color=png, roughness=png, normal=png, height=png, ao=png, assign_to="Cube")
    assert len(r["textures"]) == 5 and r["objects"] == ["Cube"]
    links = call(blender, "list_shader_nodes", material="PBR")["links"]
    assert any(l["to_socket"] == "Displacement" for l in links) and any(l["to_socket"] == "Normal" for l in links)


def test_delete_material(blender):
    call(blender, "create_material", name="Gone", assign_to="Cube")
    r = call(blender, "delete_material", name="Gone")
    assert r["unlinked_from"] == ["Cube"] and "Gone" not in [m["name"] for m in call(blender, "list_materials")]
    assert call(blender, "get_object_info", name="Cube")["materials"] == [None]
