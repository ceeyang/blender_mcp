from tests.conftest import call, run_py

EVAL = "dg = bpy.context.evaluated_depsgraph_get(); o = bpy.data.objects['Cube'].evaluated_get(dg); result = [len(o.data.vertices), list(o.dimensions)]"


def test_create_and_tree(blender):
    r = call(blender, "create_geometry_nodes", object="Cube", group_name="G")
    assert r["modifier"] == "GeometryNodes" and len(r["tree"]["nodes"]) == 2 and len(r["tree"]["links"]) == 1
    t = call(blender, "get_node_tree", node_group="G")
    assert t["users"] == ["Cube"] and [i["name"] for i in t["interface"]] == ["Geometry", "Geometry"]
    assert [g["name"] for g in call(blender, "list_node_groups", type="GEOMETRY")] == ["G"]


def test_mesh_cube_replaces_geometry(blender):
    call(blender, "create_geometry_nodes", object="Cube", group_name="G")
    n = call(blender, "add_geometry_node", node_group="G", type="MeshCube", name="MC", inputs={"Size": [3, 3, 3]})
    assert n["type"] == "GeometryNodeMeshCube"
    call(blender, "link_geometry_nodes", node_group="G", from_node="MC", from_socket="Mesh", to_node="Group Output", to_socket="Geometry")
    assert run_py(blender, EVAL) == [8, [3, 3, 3]]
    call(blender, "set_geometry_node_input", node_group="G", node="MC", socket="Vertices X", value=3)
    assert run_py(blender, EVAL)[0] == 12
    assert call(blender, "unlink_geometry_nodes", node_group="G", to_node="Group Output", to_socket="Geometry")["removed_links"] == 1
    assert "MC" in call(blender, "remove_geometry_node", node_group="G", node="MC")["removed"]


def test_group_socket_and_modifier_input(blender):
    call(blender, "create_geometry_nodes", object="Cube", group_name="G")
    s = call(blender, "add_group_socket", node_group="G", name="Size", socket_type="Float", default=1.0)
    assert s["socket"]["socket_type"] == "NodeSocketFloat"
    call(blender, "add_geometry_node", node_group="G", type="MeshCube", name="MC")
    call(blender, "link_geometry_nodes", node_group="G", from_node="Group Input", from_socket="Size", to_node="MC", to_socket="Size")
    call(blender, "link_geometry_nodes", node_group="G", from_node="MC", from_socket="Mesh", to_node="Group Output", to_socket="Geometry")
    r = call(blender, "set_gn_modifier_input", object="Cube", modifier="GeometryNodes", input="Size", value=4)
    assert r["value"] == 4
    assert run_py(blender, EVAL)[1] == [4, 4, 4]


def test_build(blender):
    call(blender, "create_geometry_nodes", object="Cube", group_name="G")
    r = call(blender, "build_geometry_node_tree", node_group="G", nodes=[
        {"type": "DistributePointsOnFaces", "name": "Dist", "inputs": {"Density": 5}},
    ], links=[
        {"from_node": "Group Input", "from_socket": "Geometry", "to_node": "Dist", "to_socket": "Mesh"},
        {"from_node": "Dist", "from_socket": "Points", "to_node": "Group Output", "to_socket": "Geometry"},
    ])
    assert r["nodes"] == ["Dist"] and len(r["links"]) == 2
