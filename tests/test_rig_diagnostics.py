from tests.conftest import call

BAD = [{"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
       {"name": "Arm.L", "head": [0, 0, 1], "tail": [1, 0, 1], "parent": "Root"},
       {"name": "Stub", "head": [0, 0, 1], "tail": [0, 0, 1.0005], "parent": "Root"},
       {"name": "Loose", "head": [5, 5, 5], "tail": [5, 5, 6]}]


def test_check_rig_finds_problems(blender):
    call(blender, "create_armature", name="Rig", bones=BAD)
    call(blender, "set_transform", name="Rig", scale=[2, 2, 2])
    call(blender, "parent_to_armature", objects=["Cube"], armature="Rig", method="EMPTY_GROUPS")
    call(blender, "add_bone_constraint", armature="Rig", bone="Arm.L", type="COPY_LOCATION")
    r = call(blender, "check_rig", armature="Rig")
    codes = {i["code"] for i in r["issues"]}
    assert {"ZERO_LENGTH_BONE", "ASYMMETRIC_NAME", "UNAPPLIED_SCALE", "UNWEIGHTED_VERTS", "CONSTRAINT_TARGET_MISSING", "MULTIPLE_ROOTS"} <= codes
    assert r["summary"]["errors"] >= 2 and r["summary"]["meshes"] == ["Cube"]
    h = call(blender, "check_bone_hierarchy", armature="Rig")
    assert [x["name"] for x in h["roots"]] == ["Root", "Loose"] and h["isolated"] == ["Loose"] and h["max_depth"] == 1
    n = call(blender, "check_bone_naming", armature="Rig")
    assert n["missing_mirror"] == [{"bone": "Arm.L", "expected_mirror": "Arm.R"}]
    u = call(blender, "find_unweighted_vertices", object="Cube")
    assert u["count"] == 8 and u["armature"] == "Rig"
    ci = call(blender, "list_constraint_issues", armature="Rig")
    assert ci[0]["code"] == "TARGET_MISSING" and ci[0]["bone"] == "Arm.L"


def test_normalize(blender):
    call(blender, "set_vertex_group_weights", object="Cube", group="A", all=0.5)
    call(blender, "set_vertex_group_weights", object="Cube", group="B", all=1.0)
    r = call(blender, "normalize_weights", object="Cube")
    assert r["vertices_changed"] == 8
    inf = call(blender, "get_bone_influence", object="Cube", vertex_index=0)
    assert abs(sum(d["weight"] for d in inf) - 1) < 1e-5 and abs(inf[0]["weight"] - 2 / 3) < 1e-5
    call(blender, "create_armature", name="Rig", bones=[{"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]}])
    call(blender, "parent_to_armature", objects=["Cube"], armature="Rig", method="AUTOMATIC")
    assert not any(i["code"] == "UNNORMALIZED_WEIGHTS" for i in call(blender, "check_rig", armature="Rig")["issues"])
