import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call, run_py


def test_keyframes_basic(blender):
    call(blender, "set_frame_range", start=1, end=20, fps=25)
    r = call(blender, "insert_keyframe", object="Cube", data_path="location", frame=1, value=[0, 0, 0])
    assert r["action"]
    call(blender, "insert_keyframe", object="Cube", data_path="location", frame=11, value=[10, 0, 0])
    ks = call(blender, "list_keyframes", object="Cube")
    assert len(ks) == 3 and [k["frame"] for k in ks[0]["keyframes"]] == [1, 11]
    call(blender, "set_current_frame", frame=6)
    assert abs(call(blender, "get_object_info", name="Cube")["location"][0] - 5) < 0.01
    r = call(blender, "set_interpolation", object="Cube", mode="LINEAR", data_path="location")
    assert r["changed"] == 6 and call(blender, "list_keyframes", object="Cube", data_path="location")[0]["keyframes"][0]["interpolation"] == "LINEAR"
    assert call(blender, "delete_keyframe", object="Cube", data_path="location", frame=11)["deleted"] is True
    assert len(call(blender, "list_keyframes", object="Cube")[0]["keyframes"]) == 1
    info = call(blender, "get_animation_info", object="Cube")
    assert info["fps"] == 25 and info["object"]["action"] and len(info["object"]["fcurves"]) == 3


def test_batch_and_cycles(blender):
    r = call(blender, "insert_keyframes_batch", object="Cube", keys=[{"frame": 1, "location": [0, 0, 0], "scale": [1, 1, 1]},
                                                                      {"frame": 10, "location": [0, 5, 0], "scale": [2, 2, 2]}])
    assert r["inserted"] == 4 and len(r["fcurves"]) == 6
    r = call(blender, "add_fcurve_modifier", object="Cube", data_path="location", type="CYCLES")
    assert len(r["added"]) == 3
    call(blender, "set_current_frame", frame=19)
    assert abs(call(blender, "get_object_info", name="Cube")["location"][1] - 5) < 0.01
    with pytest.raises(BlenderError):
        call(blender, "add_fcurve_modifier", object="Cube", data_path="nope", type="CYCLES")


def test_custom_property_keyframe(blender):
    call(blender, "set_custom_property", name="Cube", key="power", value=0.0)
    call(blender, "insert_keyframe", object="Cube", data_path='["power"]', frame=1, value=0.0)
    call(blender, "insert_keyframe", object="Cube", data_path='["power"]', frame=10, value=1.0)
    assert len(call(blender, "list_keyframes", object="Cube", data_path='["power"]')[0]["keyframes"]) == 2


def test_actions_nla(blender):
    call(blender, "insert_keyframe", object="Cube", data_path="location", frame=1, value=[0, 0, 0])
    call(blender, "insert_keyframe", object="Cube", data_path="location", frame=10, value=[1, 0, 0])
    act = call(blender, "get_animation_info", object="Cube")["object"]["action"]
    r = call(blender, "nla_push_down", object="Cube")
    assert r["frame_start"] == 1 and r["frame_end"] == 10
    info = call(blender, "get_animation_info", object="Cube")["object"]
    assert info["action"] is None and len(info["nla_tracks"]) == 1
    r = call(blender, "add_nla_strip", object="Cube", action=act, frame_start=20, track="Second", blend_type="ADD")
    assert r["track"] == "Second" and r["frame_start"] == 20
    r = call(blender, "assign_action", object="Cube", action=act)
    assert r["action"] == act and r["fcurves"] == 3
    r = call(blender, "assign_action", object="Camera")
    assert r["action"].startswith("Camera")


def test_bake(blender):
    call(blender, "create_primitive", type="empty", name="Root")
    call(blender, "set_parent", child="Cube", parent="Root")
    call(blender, "insert_keyframe", object="Root", data_path="location", frame=1, value=[0, 0, 0])
    call(blender, "insert_keyframe", object="Root", data_path="location", frame=5, value=[4, 0, 0])
    r = call(blender, "bake_animation", object="Cube", frame_start=1, frame_end=5, timeout=300)
    assert any(fc["data_path"] == "location" and fc["keyframes"] == 5 for fc in r["fcurves"])


def test_shape_keys(blender):
    assert call(blender, "list_shape_keys", object="Cube") == []
    r = call(blender, "set_shape_key", object="Cube", name="Puff", value=0.7, frame=5)
    assert r["created"] and r["value"] == 0.7
    ks = call(blender, "list_shape_keys", object="Cube")
    assert [k["name"] for k in ks] == ["Basis", "Puff"] and ks[1]["value"] == 0.7
    with pytest.raises(BlenderError):
        call(blender, "set_shape_key", object="Camera", name="x", value=1)
