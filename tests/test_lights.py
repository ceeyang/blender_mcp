import pytest

from tests.conftest import TMP, call, run_py


@pytest.mark.parametrize("ltype", ["POINT", "SUN", "SPOT", "AREA"])
def test_create_each(blender, ltype):
    r = call(blender, "create_light", type=ltype, name=f"L_{ltype}", location=[0, 0, 5], energy=500, color=[1, 0.5, 0.5])
    assert r["light_type"] == ltype and r["energy"] == 500 and r["color"] == [1, 0.5, 0.5]
    assert f"L_{ltype}" in [l["name"] for l in call(blender, "list_lights")]


def test_set_light(blender):
    call(blender, "create_light", type="AREA", name="A")
    r = call(blender, "set_light", name="A", size=4, shape="DISK", energy=50, use_shadow=False)
    assert r["size"] == 4 and r["shape"] == "DISK" and r["use_shadow"] is False
    call(blender, "create_light", type="SPOT", name="S", spot_size=0.5, spot_blend=0.3)
    assert call(blender, "get_light_info", name="S")["spot_size"] == 0.5


def test_point_at(blender):
    call(blender, "create_light", type="SPOT", name="S", location=[3, 3, 3])
    call(blender, "point_light_at", light="S", target="Cube")
    dot = run_py(blender, "o = bpy.data.objects['S']; d = (o.matrix_world.to_quaternion() @ Vector((0,0,-1))); "
                          "t = (bpy.data.objects['Cube'].location - o.location).normalized(); result = d.dot(t)")
    assert dot > 0.999
    r = call(blender, "point_light_at", light="S", target=[0, 0, 5], use_constraint=True)
    assert r["constraint"] and call(blender, "get_object_info", name="S")["constraints"][0]["type"] == "TRACK_TO"


def test_world(blender):
    r = call(blender, "set_world_lighting", color=[0.1, 0.2, 0.3], strength=2)
    assert r["color"] == [0.1, 0.2, 0.3, 1] and r["strength"] == 2 and r["hdri"] is None
    path = str(TMP / "hdri.png")
    run_py(blender, f"img = bpy.data.images.new('h', 4, 2); img.filepath_raw = r'{path}'; img.file_format='PNG'; img.save(); result=1")
    r = call(blender, "set_world_lighting", hdri_path=path, rotation=[0, 0, 1.5])
    assert r["hdri"].endswith("hdri.png")
    assert run_py(blender, "t = bpy.context.scene.world.node_tree; result = [n.bl_idname for n in t.nodes]").count("ShaderNodeMapping") == 1
