"""Geometry Nodes。"""
from __future__ import annotations

from ..server import mcp
from ._base import call

Socket = str | int


@mcp.tool()
def list_node_groups(type: str | None = None) -> list[dict]:
    """列出节点组（type: GEOMETRY/SHADER）。"""
    return call("list_node_groups", type=type)


@mcp.tool()
def create_geometry_nodes(object: str, group_name: str | None = None, modifier_name: str | None = None) -> dict:
    """给对象新建一个几何节点修改器与节点组（含 Group Input→Output 直通）。"""
    return call("create_geometry_nodes", object=object, group_name=group_name, modifier_name=modifier_name)


@mcp.tool()
def get_node_tree(node_group: str) -> dict:
    """节点组全貌：节点、连线、接口（输入/输出插槽）与使用者。"""
    return call("get_node_tree", node_group=node_group)


@mcp.tool()
def add_geometry_node(node_group: str, type: str, name: str | None = None, location: list[float] | None = None,
                      inputs: dict | None = None, properties: dict | None = None) -> dict:
    """添加几何节点。type 可省略前缀（MeshCube = GeometryNodeMeshCube；FunctionNode* 也可）。"""
    return call("add_geometry_node", node_group=node_group, type=type, name=name, location=location, inputs=inputs, properties=properties)


@mcp.tool()
def remove_geometry_node(node_group: str, node: str) -> dict:
    """删除几何节点。"""
    return call("remove_geometry_node", node_group=node_group, node=node)


@mcp.tool()
def link_geometry_nodes(node_group: str, from_node: str, from_socket: Socket, to_node: str, to_socket: Socket) -> dict:
    """几何节点连线。"""
    return call("link_geometry_nodes", node_group=node_group, from_node=from_node, from_socket=from_socket, to_node=to_node, to_socket=to_socket)


@mcp.tool()
def unlink_geometry_nodes(node_group: str, to_node: str, to_socket: Socket) -> dict:
    """断开几何节点某输入上的连线。"""
    return call("unlink_geometry_nodes", node_group=node_group, to_node=to_node, to_socket=to_socket)


@mcp.tool()
def set_geometry_node_input(node_group: str, node: str, socket: Socket, value: float | int | bool | str | list) -> dict:
    """设置几何节点输入插槽值。"""
    return call("set_geometry_node_input", node_group=node_group, node=node, socket=socket, value=value)


@mcp.tool()
def add_group_socket(node_group: str, name: str, in_out: str = "INPUT", socket_type: str = "NodeSocketFloat",
                     default: float | int | bool | str | list | None = None) -> dict:
    """给节点组接口加插槽（暴露到修改器面板）。socket_type: Float/Int/Bool/Vector/Color/Object/Collection/Material/Geometry…"""
    return call("add_group_socket", node_group=node_group, name=name, in_out=in_out, socket_type=socket_type, default=default)


@mcp.tool()
def set_gn_modifier_input(object: str, modifier: str, input: str, value: float | int | bool | str | list | None) -> dict:
    """设置几何节点修改器面板上的输入值（按接口名）。"""
    return call("set_gn_modifier_input", object=object, modifier=modifier, input=input, value=value)


@mcp.tool()
def build_geometry_node_tree(node_group: str, nodes: list[dict], links: list[dict] | None = None, clear: bool = False) -> dict:
    """一次性构建几何节点树（格式同 build_node_tree）。"""
    return call("build_geometry_node_tree", node_group=node_group, nodes=nodes, links=links, clear=clear)
