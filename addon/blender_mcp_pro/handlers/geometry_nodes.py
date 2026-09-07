"""Geometry Nodes（11）。"""
from __future__ import annotations

import bpy

from .. import nodes_common as nc
from ..registry import command
from ..utils import (ToolError, enum_check, find_collection, find_image, find_material, find_node_group, find_object,
                     serialize)


def _sync_modifiers(tree):
    """接口变化后，修改器上的 ID 属性不会自动出现；重新赋 node_group 触发同步。"""
    for o in bpy.data.objects:
        for m in o.modifiers:
            if m.type == "NODES" and m.node_group == tree:
                m.node_group = tree


def _interface(tree) -> list[dict]:
    out = []
    for it in tree.interface.items_tree:
        if it.item_type != "SOCKET":
            continue
        d = {"name": it.name, "identifier": it.identifier, "in_out": it.in_out, "socket_type": it.socket_type}
        if hasattr(it, "default_value"):
            d["default"] = serialize(it.default_value)
        out.append(d)
    return out


@command("list_node_groups", mutates=False)
def list_node_groups(type: str | None = None):
    want = None
    if type:
        want = {"GEOMETRY": "GeometryNodeTree", "SHADER": "ShaderNodeTree", "COMPOSITOR": "CompositorNodeTree"}.get(type.upper(), type)
    out = []
    for g in bpy.data.node_groups:
        if want and g.bl_idname != want:
            continue
        out.append({"name": g.name, "type": g.bl_idname, "users": g.users, "nodes": len(g.nodes),
                    "inputs": [i["name"] for i in _interface(g) if i["in_out"] == "INPUT"],
                    "outputs": [i["name"] for i in _interface(g) if i["in_out"] == "OUTPUT"]})
    return out


@command("create_geometry_nodes")
def create_geometry_nodes(object: str, group_name: str | None = None, modifier_name: str | None = None):
    o = find_object(object)
    tree = bpy.data.node_groups.new(group_name or f"{o.name}_GN", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    gi.location = (-300, 0)
    go.location = (300, 0)
    tree.links.new(gi.outputs["Geometry"], go.inputs["Geometry"])
    mod = o.modifiers.new(modifier_name or "GeometryNodes", "NODES")
    mod.node_group = tree
    return {"object": o.name, "modifier": mod.name, "node_group": tree.name, "tree": nc.tree_dump(tree)}


@command("get_node_tree", mutates=False)
def get_node_tree(node_group: str):
    tree = find_node_group(node_group)
    d = nc.tree_dump(tree)
    d["interface"] = _interface(tree)
    d["users"] = [o.name for o in bpy.data.objects for m in o.modifiers if m.type == "NODES" and m.node_group == tree]
    return d


@command("add_geometry_node")
def add_geometry_node(node_group: str, type: str, name: str | None = None, location=None, inputs: dict | None = None,
                      properties: dict | None = None):
    tree = nc.get_tree(node_group=node_group)
    return nc.node_dump(nc.add_node(tree, type, name, location, inputs, properties))


@command("remove_geometry_node")
def remove_geometry_node(node_group: str, node: str):
    tree = nc.get_tree(node_group=node_group)
    n = nc.find_node(tree, node)
    name = n.name
    tree.nodes.remove(n)
    return {"removed": name, "nodes": [x.name for x in tree.nodes]}


@command("link_geometry_nodes")
def link_geometry_nodes(node_group: str, from_node: str, from_socket, to_node: str, to_socket):
    return nc.link(nc.get_tree(node_group=node_group), from_node, from_socket, to_node, to_socket)


@command("unlink_geometry_nodes")
def unlink_geometry_nodes(node_group: str, to_node: str, to_socket):
    return {"removed_links": nc.unlink(nc.get_tree(node_group=node_group), to_node, to_socket)}


@command("set_geometry_node_input")
def set_geometry_node_input(node_group: str, node: str, socket, value):
    tree = nc.get_tree(node_group=node_group)
    n = nc.find_node(tree, node)
    s = nc.find_socket(n.inputs, socket)
    nc.set_socket_value(s, value)
    return {"node": n.name, "socket": s.name, "value": nc.socket_value(s)}


@command("add_group_socket")
def add_group_socket(node_group: str, name: str, in_out: str = "INPUT", socket_type: str = "NodeSocketFloat", default=None):
    tree = find_node_group(node_group)
    io = enum_check(in_out, ["INPUT", "OUTPUT"], "in_out")
    if not socket_type.startswith("NodeSocket"):
        socket_type = "NodeSocket" + socket_type
    try:
        item = tree.interface.new_socket(name, in_out=io, socket_type=socket_type)
    except (TypeError, RuntimeError) as e:
        raise ToolError(f"cannot create socket of type '{socket_type}': {e}") from e
    if default is not None and hasattr(item, "default_value"):
        item.default_value = default
    _sync_modifiers(tree)
    return {"node_group": tree.name, "socket": {"name": item.name, "identifier": item.identifier, "in_out": item.in_out,
                                                "socket_type": item.socket_type}}


_GN_POINTERS = {"NodeSocketObject": find_object, "NodeSocketCollection": find_collection,
                "NodeSocketMaterial": find_material, "NodeSocketImage": find_image}


@command("set_gn_modifier_input")
def set_gn_modifier_input(object: str, modifier: str, input: str, value):
    o = find_object(object)
    mod = o.modifiers.get(modifier)
    if mod is None or mod.type != "NODES":
        raise ToolError(f"'{modifier}' is not a Geometry Nodes modifier on '{o.name}'. "
                        f"Available: {', '.join(m.name for m in o.modifiers if m.type == 'NODES')}")
    tree = mod.node_group
    if tree is None:
        raise ToolError("modifier has no node group")
    inputs = [i for i in _interface(tree) if i["in_out"] == "INPUT"]
    item = next((i for i in inputs if i["name"] == input or i["identifier"] == input), None)
    if item is None:
        raise ToolError(f"input '{input}' not found. Available: {', '.join(i['name'] for i in inputs)}")
    st = item["socket_type"]
    if st in _GN_POINTERS:
        v = None if value is None else _GN_POINTERS[st](value)
    elif st == "NodeSocketFloat":
        v = float(value)
    elif st == "NodeSocketInt":
        v = int(value)
    elif st == "NodeSocketBool":
        v = bool(value)
    elif st in ("NodeSocketVector", "NodeSocketColor", "NodeSocketRotation"):
        v = [float(x) for x in value]
    else:
        v = value
    # Blender 5.2：修改器输入是 mod.properties.inputs.<identifier>.value（RNA struct）；
    # ins[identifier] = v 会把整组结构覆盖成裸值，修改器不会生效。
    ins = mod.properties.inputs
    sock = getattr(ins, item["identifier"], None)
    if sock is None:
        _sync_modifiers(tree)
        sock = getattr(mod.properties.inputs, item["identifier"], None)
    if sock is None:
        raise ToolError(f"modifier has no property for input '{item['name']}' ({item['identifier']})")
    try:
        sock.value = v
    except (TypeError, ValueError) as e:
        raise ToolError(f"cannot set '{item['name']}' ({st}) to {value!r}: {e}") from e
    o.update_tag()
    bpy.context.view_layer.update()
    return {"object": o.name, "modifier": mod.name, "input": item["name"], "identifier": item["identifier"],
            "value": serialize(getattr(mod.properties.inputs, item["identifier"]).value)}


@command("build_geometry_node_tree")
def build_geometry_node_tree(node_group: str, nodes: list, links: list | None = None, clear: bool = False):
    return nc.build(nc.get_tree(node_group=node_group), nodes, links, clear)
