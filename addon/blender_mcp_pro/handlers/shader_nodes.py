"""Shader Nodes（10）。"""
from __future__ import annotations

from .. import nodes_common as nc
from ..registry import command
from ..utils import serialize


@command("list_shader_nodes", mutates=False)
def list_shader_nodes(material: str):
    return nc.tree_dump(nc.get_tree(material=material))


@command("add_shader_node")
def add_shader_node(material: str, type: str, name: str | None = None, location=None, inputs: dict | None = None,
                    properties: dict | None = None):
    tree = nc.get_tree(material=material)
    return nc.node_dump(nc.add_node(tree, type, name, location, inputs, properties))


@command("remove_shader_node")
def remove_shader_node(material: str, node: str):
    tree = nc.get_tree(material=material)
    n = nc.find_node(tree, node)
    name = n.name
    tree.nodes.remove(n)
    return {"removed": name, "nodes": [x.name for x in tree.nodes]}


@command("set_node_input")
def set_node_input(material: str, node: str, socket, value):
    tree = nc.get_tree(material=material)
    n = nc.find_node(tree, node)
    s = nc.find_socket(n.inputs, socket)
    nc.set_socket_value(s, value)
    return {"node": n.name, "socket": s.name, "value": nc.socket_value(s)}


@command("set_node_property")
def set_node_property(material: str, node: str, property: str, value):
    tree = nc.get_tree(material=material)
    n = nc.find_node(tree, node)
    return {"node": n.name, "property": property, "value": nc.set_property(n, property, value),
            "inputs": [s.name for s in n.inputs if s.enabled]}


@command("link_nodes")
def link_nodes(material: str, from_node: str, from_socket, to_node: str, to_socket):
    return nc.link(nc.get_tree(material=material), from_node, from_socket, to_node, to_socket)


@command("unlink_nodes")
def unlink_nodes(material: str, to_node: str, to_socket):
    return {"removed_links": nc.unlink(nc.get_tree(material=material), to_node, to_socket)}


@command("set_color_ramp")
def set_color_ramp(material: str, node: str, stops: list, interpolation: str | None = None):
    tree = nc.get_tree(material=material)
    return nc.set_color_ramp(nc.find_node(tree, node), stops, interpolation)


@command("build_node_tree")
def build_node_tree(material: str, nodes: list, links: list | None = None, clear: bool = False):
    return nc.build(nc.get_tree(material=material), nodes, links, clear)


@command("get_node_types", mutates=False)
def get_node_types(tree: str = "shader", filter: str | None = None):
    return serialize(nc.node_types(tree, filter))
