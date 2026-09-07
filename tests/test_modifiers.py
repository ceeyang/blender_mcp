import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call, run_py


@pytest.fixture
def targets(blender):
    call(blender, "create_primitive", type="cube", name="B", location=[0.5, 0.5, 0.5])
    run_py(blender, """
arm = bpy.data.armatures.new('Arm'); ao = bpy.data.objects.new('Arm', arm); bpy.context.scene.collection.objects.link(ao)
cv = bpy.data.curves.new('Cv', 'CURVE'); cv.dimensions = '3D'; sp = cv.splines.new('BEZIER'); sp.bezier_points.add(1)
sp.bezier_points[1].co = (0, 0, 3); co = bpy.data.objects.new('Cv', cv); bpy.context.scene.collection.objects.link(co)
lat = bpy.data.lattices.new('Lat'); lo = bpy.data.objects.new('Lat', lat); bpy.context.scene.collection.objects.link(lo)
result = 1""")


CASES = [
    ("SUBSURF", {"levels": 2}), ("BEVEL", {"width": 0.1, "segments": 3}), ("ARRAY", {"count": 3}), ("MIRROR", {"use_axis": [True, True, False]}),
    ("SOLIDIFY", {"thickness": 0.1}), ("BOOLEAN", {"object": "B", "operation": "DIFFERENCE"}), ("DISPLACE", {"strength": 0.5}),
    ("DECIMATE", {"ratio": 0.5}), ("SHRINKWRAP", {"target": "B"}), ("NODES", {}), ("ARMATURE", {"object": "Arm"}),
    ("WIREFRAME", {"thickness": 0.02}), ("SCREW", {"angle": 3.14}), ("TRIANGULATE", {}), ("WELD", {"merge_threshold": 0.01}),
    ("REMESH", {"voxel_size": 0.2}), ("SKIN", {}), ("CURVE", {"object": "Cv"}), ("LATTICE", {"object": "Lat"}),
    ("SIMPLE_DEFORM", {"deform_method": "TWIST", "angle": 1.0}), ("CAST", {"factor": 0.5}), ("SMOOTH", {"factor": 0.5, "iterations": 2}),
]


@pytest.mark.parametrize("mtype,settings", CASES, ids=[c[0] for c in CASES])
def test_add_each_type(blender, targets, mtype, settings):
    r = call(blender, "add_modifier", object="Cube", type=mtype, settings=settings)
    assert r["type"] == mtype
    for k, v in settings.items():
        got = r["settings"][k]
        if isinstance(got, dict):
            assert got["name"] == v
        elif isinstance(v, float):
            assert abs(got - v) < 1e-5
        else:
            assert got == v
    assert [m["type"] for m in call(blender, "list_modifiers", object="Cube")] == [mtype]


def test_types_listing(blender):
    types = call(blender, "list_modifier_types")
    assert len(types) >= 80
    sub = call(blender, "list_modifier_types", filter="subsurf")
    assert sub[0]["type"] == "SUBSURF" and "levels" in sub[0]["settings"] and sub[0]["settings"]["subdivision_type"]["enum"]


def test_settings_apply_and_errors(blender):
    call(blender, "add_modifier", object="Cube", type="SUBSURF", name="Sub", settings={"levels": 2})
    s = call(blender, "get_modifier_settings", object="Cube", modifier="Sub")
    assert s["settings"]["levels"] == 2 and "render_levels" in s["available"]
    with pytest.raises(BlenderError) as ei:
        call(blender, "set_modifier", object="Cube", modifier="Sub", settings={"level": 3})
    assert "levels" in ei.value.message
    with pytest.raises(BlenderError):
        call(blender, "set_modifier", object="Cube", modifier="Sub", settings={"subdivision_type": "BOGUS"})
    r = call(blender, "apply_modifier", object="Cube", modifier="Sub")
    assert r["vertices"] == 98 and r["modifiers"] == []


def test_move_remove(blender):
    for n in ("A", "B", "C"):
        call(blender, "add_modifier", object="Cube", type="BEVEL", name=n)
    assert call(blender, "move_modifier", object="Cube", modifier="C", direction="TOP")["order"] == ["C", "A", "B"]
    assert call(blender, "move_modifier", object="Cube", modifier="C", index=2)["order"] == ["A", "B", "C"]
    assert call(blender, "remove_modifier", object="Cube", modifier="B")["modifiers"] == ["A", "C"]
