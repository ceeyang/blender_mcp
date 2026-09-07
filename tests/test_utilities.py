import math

import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call, run_py


def test_execute_code(blender):
    r = call(blender, "execute_code", code="print('hi'); x = [o.name for o in bpy.data.objects]", return_var="x")
    assert r["stdout"] == "hi\n" and sorted(r["result"]) == ["Camera", "Cube", "Light"]
    with pytest.raises(BlenderError) as ei:
        call(blender, "execute_code", code="1/0")
    assert ei.value.type == "ZeroDivisionError"


def test_blender_info(blender):
    r = call(blender, "get_blender_info")
    assert r["version"][0] == 5 and r["addon_version"] == "0.1.0" and r["server"]["running"] is True


def test_api_docs(blender):
    t = call(blender, "get_api_docs", path="bpy.types.Object")
    assert "location" in t["properties"] and t["kind"] == "type"
    p = call(blender, "get_api_docs", path="bpy.types.Object.rotation_mode")
    assert p["kind"] == "property" and any(e["id"] == "QUATERNION" for e in p["enum"])
    o = call(blender, "get_api_docs", path="bpy.ops.mesh.primitive_cube_add")
    assert o["kind"] == "operator" and "size" in o["properties"]
    with pytest.raises(BlenderError) as ei:
        call(blender, "get_api_docs", path="bpy.types.Objec")
    assert "Object" in ei.value.message


def test_undo_redo_headless_gives_clear_error(blender):
    """background 模式没有 undo 栈；真实 undo 在 GUI 端到端验证。"""
    with pytest.raises(BlenderError) as ei:
        call(blender, "undo")
    assert ei.value.type == "ToolError" and "background" in ei.value.message


def test_purge_orphans(blender):
    run_py(blender, "bpy.data.materials.new('orphan'); result = 1")
    assert call(blender, "purge_orphans")["purged"] >= 1


def test_units_cursor(blender):
    r = call(blender, "set_units", system="IMPERIAL", scale_length=0.5, rotation_unit="RADIANS")
    assert r["system"] == "IMPERIAL" and r["scale_length"] == 0.5 and r["rotation"] == "RADIANS"
    assert call(blender, "set_cursor", location=[1, 2, 3])["location"] == [1, 2, 3]


def test_measure_and_bbox(blender):
    cam = call(blender, "get_object_info", name="Camera")["location"]
    d = call(blender, "measure_distance", a="Cube", b="Camera")["distance"]
    assert abs(d - math.sqrt(sum(c * c for c in cam))) < 1e-4
    assert call(blender, "measure_distance", a=[0, 0, 0], b=[3, 4, 0])["distance"] == 5
    bb = call(blender, "get_bounding_box", objects=["Cube"])
    assert bb["size"] == [2, 2, 2] and bb["center"] == [0, 0, 0]


def test_ray_cast(blender):
    r = call(blender, "ray_cast", origin=[0, 0, 10], direction=[0, 0, -1])
    assert r["hit"] and r["object"] == "Cube" and abs(r["location"][2] - 1) < 1e-5
    assert call(blender, "ray_cast", origin=[50, 50, 10], direction=[0, 0, -1])["hit"] is False


def test_check_and_cleanup(blender):
    r = call(blender, "check_mesh", name="Cube")
    assert r["quads"] == 6 and r["ngons"] == 0 and r["is_manifold"] and r["duplicate_vertices"] == 0
    c = call(blender, "mesh_cleanup", name="Cube", merge_by_distance=True, recalc_normals=True, shade_smooth=True)
    assert c["vertices_after"] == 8 and c["smooth"] is True
    c = call(blender, "mesh_cleanup", name="Cube", auto_smooth_angle=0.5)
    assert c["object"] == "Cube"
