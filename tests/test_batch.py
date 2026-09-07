import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import call


@pytest.fixture
def three(blender):
    for n in ("A", "B", "C"):
        call(blender, "create_primitive", type="cube", name=n)
    return ["A", "B", "C"]


def test_transform_rename(blender, three):
    r = call(blender, "batch_transform", objects=three, location=[0, 0, 1], scale=[2, 2, 2])
    assert all(o["location"][2] == 1 and o["scale"] == [2, 2, 2] for o in r["objects"])
    r = call(blender, "batch_rename", objects=three, prefix="P_", numbering=True)
    assert r["renamed"] == {"A": "P_A_001", "B": "P_B_002", "C": "P_C_003"}
    r = call(blender, "batch_rename", objects={"pattern": "P_*"}, find="P_", replace="Q_")
    assert set(r["renamed"].values()) == {"Q_A_001", "Q_B_002", "Q_C_003"}


def test_material_modifier_property_delete(blender, three):
    call(blender, "create_material", name="M")
    r = call(blender, "batch_apply_material", objects=three + ["Camera"], material="M")
    assert r["applied"] == three and r["skipped"] == ["Camera"]
    r = call(blender, "batch_add_modifier", objects=three, type="BEVEL", settings={"width": 0.2})
    assert set(r["added"].values()) == {"Bevel"}
    r = call(blender, "batch_set_property", objects=three, data_path="modifiers['Bevel'].width", value=0.5)
    assert call(blender, "get_modifier_settings", object="A", modifier="Bevel")["settings"]["width"] == 0.5
    call(blender, "batch_set_property", objects=three, data_path="hide_render", value=True)
    assert call(blender, "get_object_info", name="B")["hide_render"] is True
    with pytest.raises(BlenderError):
        call(blender, "batch_set_property", objects=three, data_path="nope", value=1)
    assert sorted(call(blender, "batch_delete", objects={"pattern": "[ABC]"})["deleted"]) == three


def test_distribute(blender, three):
    r = call(blender, "distribute_objects", objects=three, mode="LINE", spacing=2)
    assert [p["location"][0] for p in r["positions"]] == [-2, 0, 2]
    r = call(blender, "distribute_objects", objects=three, mode="GRID", spacing=1, columns=2)
    assert r["positions"][2]["location"][1] == 0.5 and r["positions"][0]["location"][0] == -0.5
    r = call(blender, "distribute_objects", objects=three, mode="CIRCLE", radius=3, center=[1, 1, 0])
    assert r["positions"][0]["location"] == [4, 1, 0]


def test_randomize_reproducible(blender, three):
    a = call(blender, "randomize_transform", objects=three, location=[1, 1, 0], rotation=[0, 0, 3.14], scale=[0.5], seed=7)
    call(blender, "batch_transform", objects=three, location=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1], relative=False)
    b = call(blender, "randomize_transform", objects=three, location=[1, 1, 0], rotation=[0, 0, 3.14], scale=[0.5], seed=7)
    assert [o["location"] for o in a["objects"]] == [o["location"] for o in b["objects"]]
    assert a["objects"][0]["location"] != [0, 0, 0]
