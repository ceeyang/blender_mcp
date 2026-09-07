import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call, run_py


def test_scene_info(blender):
    r = call(blender, "get_scene_info")
    assert r["object_count"] == 3 and r["objects_by_type"] == {"CAMERA": 1, "LIGHT": 1, "MESH": 1}
    assert r["active_camera"] == "Camera" and r["collections"]["children"][0]["name"] == "Collection"


def test_list_objects_filters(blender):
    assert [o["name"] for o in call(blender, "list_objects", type="MESH")] == ["Cube"]
    assert [o["name"] for o in call(blender, "list_objects", pattern="C*")] == ["Camera", "Cube"]
    assert [o["name"] for o in call(blender, "list_objects", collection="Collection")] == ["Camera", "Cube", "Light"]


@pytest.mark.parametrize("ptype", ["cube", "plane", "uv_sphere", "ico_sphere", "cylinder", "cone", "torus", "circle", "monkey", "empty", "text"])
def test_create_every_primitive(blender, ptype):
    r = call(blender, "create_primitive", type=ptype, name=f"P_{ptype}", location=[1, 2, 3])
    assert r["name"] == f"P_{ptype}" and r["location"] == [1, 2, 3]


def test_create_with_dimensions_and_info(blender):
    r = call(blender, "create_primitive", type="cylinder", name="Pillar", radius=0.5, depth=2, segments=8)
    info = call(blender, "get_object_info", name="Pillar")
    assert info["type"] == "MESH" and info["mesh"]["vertices"] == 16
    assert r["dimensions"] == [1, 1, 2]
    t = call(blender, "create_primitive", type="text", name="Label", text="hello")
    assert run_py(blender, "result = bpy.data.objects['Label'].data.body") == "hello"


def test_missing_object_lists_candidates(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "get_object_info", name="Cub")
    assert ei.value.type == "ToolError" and "Cube" in ei.value.message


def test_delete_with_children(blender):
    call(blender, "create_primitive", type="empty", name="Root")
    call(blender, "set_parent", child="Cube", parent="Root")
    r = call(blender, "delete_object", objects=["Root"], delete_children=True)
    assert sorted(r["deleted"]) == ["Cube", "Root"]
    assert call(blender, "get_scene_info")["object_count"] == 2


def test_duplicate(blender):
    r = call(blender, "duplicate_object", name="Cube", new_name="Cube2", offset=[3, 0, 0])
    assert r["name"] == "Cube2" and r["location"] == [3, 0, 0]
    assert run_py(blender, "result = bpy.data.objects['Cube2'].data != bpy.data.objects['Cube'].data") is True
    r = call(blender, "duplicate_object", name="Cube", new_name="Cube3", linked=True)
    assert run_py(blender, "result = bpy.data.objects['Cube3'].data == bpy.data.objects['Cube'].data") is True


def test_set_transform_relative(blender):
    call(blender, "set_transform", name="Cube", location=[1, 1, 1], scale=[2, 2, 2])
    r = call(blender, "set_transform", name="Cube", location=[1, 0, 0], scale=[2, 1, 1], relative=True)
    assert r["location"] == [2, 1, 1] and r["scale"] == [4, 2, 2]


def test_rename(blender):
    r = call(blender, "rename_object", name="Cube", new_name="Box")
    assert r["name"] == "Box" and r["data"] == "Box"


def test_parent_keep_transform(blender):
    call(blender, "create_primitive", type="empty", name="Root", location=[5, 0, 0])
    r = call(blender, "set_parent", child="Cube", parent="Root")
    assert r["world_location"] == [0, 0, 0]
    info = call(blender, "get_object_info", name="Cube")
    assert info["parent"] == "Root" and info["world_location"] == [0, 0, 0]
    r = call(blender, "set_parent", child="Cube")
    assert r["parent"] is None and call(blender, "get_object_info", name="Cube")["world_location"] == [0, 0, 0]


def test_visibility_and_select(blender):
    call(blender, "set_visibility", objects=["Cube"], hide_render=True)
    assert call(blender, "get_object_info", name="Cube")["hide_render"] is True
    r = call(blender, "select_objects", objects=["Cube", "Light"], active="Light")
    assert sorted(r["selected"]) == ["Cube", "Light"] and r["active"] == "Light"
    r = call(blender, "select_objects", objects=["Cube"], mode="remove")
    assert r["selected"] == ["Light"]
    assert [o["name"] for o in call(blender, "list_objects", selected=True)] == ["Light"]


def test_manage_collection(blender):
    call(blender, "manage_collection", action="create", name="Props")
    call(blender, "manage_collection", action="move", name="Props", objects=["Cube"])
    assert call(blender, "get_object_info", name="Cube")["collections"] == ["Props"]
    call(blender, "manage_collection", action="link", name="Collection", objects=["Cube"])
    assert sorted(call(blender, "get_object_info", name="Cube")["collections"]) == ["Collection", "Props"]
    call(blender, "manage_collection", action="rename", name="Props", new_name="Stuff")
    call(blender, "manage_collection", action="delete", name="Stuff")
    assert call(blender, "get_object_info", name="Cube")["collections"] == ["Collection"]


def test_join_and_apply(blender):
    call(blender, "create_primitive", type="cube", name="B", location=[3, 0, 0])
    r = call(blender, "join_objects", objects=["Cube", "B"], target="Cube")
    assert r["name"] == "Cube" and call(blender, "get_object_info", name="Cube")["mesh"]["vertices"] == 16
    call(blender, "set_transform", name="Cube", scale=[2, 2, 2])
    call(blender, "apply_transforms", objects=["Cube"])
    info = call(blender, "get_object_info", name="Cube")
    assert info["scale"] == [1, 1, 1] and info["dimensions"][0] == 10


def test_set_origin(blender):
    call(blender, "set_transform", name="Cube", location=[0, 0, 0])
    call(blender, "set_cursor", location=[1, 0, 0])
    r = call(blender, "set_origin", name="Cube", type="CURSOR")
    assert r["location"] == [1, 0, 0]


def test_custom_property(blender):
    r = call(blender, "set_custom_property", name="Cube", key="tag", value="hero")
    assert r["value"] == "hero" and call(blender, "get_object_info", name="Cube")["custom_properties"] == {"tag": "hero"}
    call(blender, "set_custom_property", name="Cube", key="tag")
    assert call(blender, "get_object_info", name="Cube")["custom_properties"] == {}


def test_objects_filters(blender):
    r = call(blender, "delete_object", objects={"type": "LIGHT"})
    assert r["deleted"] == ["Light"]
    with pytest.raises(BlenderError):
        call(blender, "delete_object", objects={"pattern": "Nope*"})
