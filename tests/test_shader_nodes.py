import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call


@pytest.fixture
def mat(blender):
    call(blender, "create_material", name="M")
    return "M"


def test_add_link_list(blender, mat):
    n = call(blender, "add_shader_node", material=mat, type="TexNoise", name="Noise", location=[-400, 0], inputs={"Scale": 12})
    assert n["type"] == "ShaderNodeTexNoise" and next(i for i in n["inputs"] if i["name"] == "Scale")["value"] == 12
    lk = call(blender, "link_nodes", material=mat, from_node="Noise", from_socket="Fac", to_node="Principled BSDF", to_socket="Base Color")
    assert lk["to_socket"] == "Base Color"
    d = call(blender, "list_shader_nodes", material=mat)
    assert any(l["from_node"] == "Noise" and l["to_socket"] == "Base Color" for l in d["links"])
    assert call(blender, "unlink_nodes", material=mat, to_node="Principled BSDF", to_socket="Base Color")["removed_links"] == 1


def test_set_input_property_remove(blender, mat):
    call(blender, "add_shader_node", material=mat, type="ShaderNodeMath", name="Math")
    r = call(blender, "set_node_property", material=mat, node="Math", property="operation", value="MULTIPLY")
    assert r["value"] == "MULTIPLY"
    r = call(blender, "set_node_input", material=mat, node="Math", socket="Value#2", value=3)
    assert r["value"] == 3
    with pytest.raises(BlenderError) as ei:
        call(blender, "set_node_input", material=mat, node="Math", socket="Nope", value=1)
    assert "Value" in ei.value.message
    with pytest.raises(BlenderError):
        call(blender, "set_node_property", material=mat, node="Math", property="operation", value="BOGUS")
    assert "Math" in call(blender, "remove_shader_node", material=mat, node="Math")["removed"]


def test_color_ramp(blender, mat):
    call(blender, "add_shader_node", material=mat, type="ValToRGB", name="Ramp")
    r = call(blender, "set_color_ramp", material=mat, node="Ramp",
             stops=[{"position": 0, "color": [0, 0, 0]}, {"position": 0.5, "color": [1, 0, 0]}, {"position": 1, "color": [1, 1, 1]}],
             interpolation="CONSTANT")
    assert len(r["stops"]) == 3 and r["stops"][1]["color"] == [1, 0, 0, 1] and r["interpolation"] == "CONSTANT"


def test_build_tree(blender, mat):
    r = call(blender, "build_node_tree", material=mat, clear=True, nodes=[
        {"type": "TexNoise", "name": "N", "inputs": {"Scale": 5}},
        {"type": "ValToRGB", "name": "R"},
        {"type": "BsdfPrincipled", "name": "P"},
        {"type": "OutputMaterial", "name": "Out"},
    ], links=[
        {"from_node": "N", "from_socket": "Fac", "to_node": "R", "to_socket": "Fac"},
        {"from_node": "R", "from_socket": "Color", "to_node": "P", "to_socket": "Base Color"},
        {"from_node": "P", "from_socket": "BSDF", "to_node": "Out", "to_socket": "Surface"},
    ])
    assert r["nodes"] == ["N", "R", "P", "Out"] and len(r["links"]) == 3
    assert len(call(blender, "list_shader_nodes", material=mat)["nodes"]) == 4


def test_node_types(blender):
    shader = call(blender, "get_node_types", tree="shader", filter="noise")
    assert any(t["type"] == "ShaderNodeTexNoise" and any(i["name"] == "Scale" for i in t["inputs"]) for t in shader)
    geo = call(blender, "get_node_types", tree="geometry", filter="cube")
    assert any(t["type"] == "GeometryNodeMeshCube" for t in geo)
    assert len(call(blender, "get_node_types", tree="geometry")) > 200
