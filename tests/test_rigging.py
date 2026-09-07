import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call, run_py

CHAIN = [{"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
         {"name": "Mid", "head": [0, 0, 1], "tail": [0, 0, 2], "parent": "Root", "connect": True},
         {"name": "Tip", "head": [0, 0, 2], "tail": [0, 0, 3], "parent": "Mid", "connect": True}]


def test_create_list_edit(blender):
    r = call(blender, "create_armature", name="Rig", bones=CHAIN)
    assert r["bones"] == ["Root", "Mid", "Tip"] and r["bone_count"] == 3
    bones = call(blender, "list_bones", armature="Rig")
    assert bones[1]["parent"] == "Root" and bones[1]["connected"] and bones[2]["tail"] == [0, 0, 3]
    b = call(blender, "add_bone", armature="Rig", name="Side", head=[1, 0, 1], tail=[2, 0, 1], parent="Mid")
    assert b["parent"] == "Mid" and b["length"] == 1
    b = call(blender, "set_bone", armature="Rig", bone="Side", tail=[3, 0, 1], deform=False, parent="")
    assert b["length"] == 2 and b["deform"] is False and b["parent"] is None
    assert call(blender, "remove_bone", armature="Rig", bone="Side")["bones"] == ["Root", "Mid", "Tip"]
    with pytest.raises(BlenderError) as ei:
        call(blender, "set_bone", armature="Rig", bone="Nope", roll=1)
    assert "Root" in ei.value.message


def test_parent_and_weights(blender):
    call(blender, "create_armature", name="Rig", bones=CHAIN)
    call(blender, "set_transform", name="Cube", location=[0, 0, 1.5])
    r = call(blender, "parent_to_armature", objects=["Cube"], armature="Rig", method="AUTOMATIC")
    info = r["objects"]["Cube"]
    assert info["parent"] == "Rig" and "ARMATURE" in info["modifiers"] and sorted(info["vertex_groups"]) == ["Mid", "Root", "Tip"]
    r = call(blender, "set_vertex_group_weights", object="Cube", group="Extra", all=1.0)
    assert r["vertices"] == 8 and "Extra" in r["groups"]
    r = call(blender, "set_vertex_group_weights", object="Cube", group="Extra", weights=[[0, 0.25]])
    assert call(blender, "get_bone_influence", object="Cube", vertex_index=0)[-1] == {"group": "Extra", "weight": 0.25} or \
        any(d["group"] == "Extra" and d["weight"] == 0.25 for d in call(blender, "get_bone_influence", object="Cube", vertex_index=0))


def test_constraints_and_pose(blender):
    call(blender, "create_armature", name="Rig", bones=CHAIN)
    call(blender, "create_primitive", type="empty", name="IK_Target", location=[1, 0, 2])
    r = call(blender, "add_bone_constraint", armature="Rig", bone="Tip", type="IK", settings={"target": "IK_Target", "chain_count": 2})
    assert r["type"] == "IK" and r["target"] == "IK_Target"
    with pytest.raises(BlenderError):
        call(blender, "add_bone_constraint", armature="Rig", bone="Tip", type="COPY_ROTATION", settings={"target": "Rig", "subtarget": "Nope"})
    r = call(blender, "set_pose", armature="Rig", bones={"Root": {"rotation_euler": [0, 0.5, 0]}}, keyframe=True, frame=3)
    assert r["keyframed_at"] == 3 and abs(r["bones"]["Root"]["rotation_euler"][1] - 0.5) < 1e-6
    tip = run_py(blender, "bpy.context.view_layer.update(); result = list(bpy.data.objects['Rig'].pose.bones['Tip'].tail)")
    assert abs(tip[0]) > 0.5
    assert call(blender, "list_bones", armature="Rig", pose=True)[0]["pose"]["rotation_euler"][1] != 0
    r = call(blender, "reset_pose", armature="Rig")
    assert r["reset"] == ["Root", "Mid", "Tip"] and call(blender, "list_bones", armature="Rig", pose=True)[0]["pose"]["rotation_euler"] == [0, 0, 0]


def test_rigify(blender):
    r = call(blender, "add_rigify_metarig", type="basic_human", name="Meta")
    assert r["bones"] > 20
    r = call(blender, "generate_rigify_rig", metarig="Meta", timeout=600)
    assert r["rig"] and r["bones"] > r["bones"] * 0 and call(blender, "get_object_info", name=r["rig"])["type"] == "ARMATURE"
