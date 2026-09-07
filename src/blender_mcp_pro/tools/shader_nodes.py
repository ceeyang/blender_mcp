"""Shader Nodes。"""
from __future__ import annotations

from ..server import mcp
from ._base import call

Socket = str | int


@mcp.tool()
def list_shader_nodes(material: str) -> dict:
    """列出材质节点树：每个节点的类型/位置/输入值/属性，以及全部连线。"""
    return call("list_shader_nodes", material=material)


@mcp.tool()
def add_shader_node(material: str, type: str, name: str | None = None, location: list[float] | None = None,
                    inputs: dict | None = None, properties: dict | None = None) -> dict:
    """添加节点。type 可省略前缀（TexNoise = ShaderNodeTexNoise）；inputs 按插槽名设值；properties 设节点属性（如 blend_type）。"""
    return call("add_shader_node", material=material, type=type, name=name, location=location, inputs=inputs, properties=properties)


@mcp.tool()
def remove_shader_node(material: str, node: str) -> dict:
    """删除节点。"""
    return call("remove_shader_node", material=material, node=node)


@mcp.tool()
def set_node_input(material: str, node: str, socket: Socket, value: float | int | bool | str | list) -> dict:
    """设置某节点某输入插槽的值（插槽可用名字、索引或 'Name#2'）。"""
    return call("set_node_input", material=material, node=node, socket=socket, value=value)


@mcp.tool()
def set_node_property(material: str, node: str, property: str, value: float | int | bool | str | list | None) -> dict:
    """设置节点属性（operation、blend_type、data_type、image=图片名或路径、node_tree=组名…）。"""
    return call("set_node_property", material=material, node=node, property=property, value=value)


@mcp.tool()
def link_nodes(material: str, from_node: str, from_socket: Socket, to_node: str, to_socket: Socket) -> dict:
    """连线。"""
    return call("link_nodes", material=material, from_node=from_node, from_socket=from_socket, to_node=to_node, to_socket=to_socket)


@mcp.tool()
def unlink_nodes(material: str, to_node: str, to_socket: Socket) -> dict:
    """断开某输入插槽上的连线。"""
    return call("unlink_nodes", material=material, to_node=to_node, to_socket=to_socket)


@mcp.tool()
def set_color_ramp(material: str, node: str, stops: list[dict], interpolation: str | None = None) -> dict:
    """设置 Color Ramp：stops=[{position, color}]，interpolation: LINEAR/EASE/CONSTANT/B_SPLINE/CARDINAL。"""
    return call("set_color_ramp", material=material, node=node, stops=stops, interpolation=interpolation)


@mcp.tool()
def build_node_tree(material: str, nodes: list[dict], links: list[dict] | None = None, clear: bool = False) -> dict:
    """一次性建树：nodes=[{type,name?,location?,inputs?,properties?}]，links=[{from_node,from_socket,to_node,to_socket}]。"""
    return call("build_node_tree", material=material, nodes=nodes, links=links, clear=clear)


@mcp.tool()
def get_node_types(tree: str = "shader", filter: str | None = None) -> list[dict]:
    """枚举可用节点类型及其输入/输出插槽。tree: shader/geometry；filter 子串过滤。"""
    return call("get_node_types", tree=tree, filter=filter)
