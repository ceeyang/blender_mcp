"""Shader Nodes — read and build a material's node tree."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE

Socket = str | int
_SOCKET_DOC = (
    "Socket identifier: its name ('Base Color', 'Fac', 'Color'), its 0-based index, or 'Name#2' to pick the second "
    "socket sharing a name — Math and Mix nodes have several called 'Value' or 'Color', and the name alone is "
    "ambiguous there. A wrong name fails with the node's full socket list."
)
_NODE_DOC = (
    "Node name as shown by list_shader_nodes. The label is accepted too. Nodes you create without a `name` get "
    "Blender's default ('Math', 'Math.001'), so pass an explicit name when you plan to reference it later."
)


@mcp.tool(annotations=READ_ONLY)
def list_shader_nodes(
    material: Annotated[str, Field(description="Material whose node tree to dump.")],
) -> dict:
    """Dump a material's whole node tree: every node with its type, position, current input values and settable properties, plus all the links between them.

    Read this before editing an unfamiliar material — node names are unpredictable and
    every other tool in this group addresses nodes by name. It is also how you check that
    a link actually landed where you intended.
    """
    return call("list_shader_nodes", material=material)


@mcp.tool(annotations=CREATE)
def add_shader_node(
    material: Annotated[str, Field(description="Material to add the node to.")],
    type: Annotated[str, Field(description="Node type; the 'ShaderNode' prefix is optional, so 'TexNoise' and 'ShaderNodeTexNoise' both work. Common ones: TexNoise, TexImage, TexVoronoi, TexChecker, ValToRGB (Color Ramp), Math, MixShader, BsdfPrincipled, BsdfGlass, Emission, Bump, NormalMap, Mapping, TexCoord. Search the full list with get_node_types.")],
    name: Annotated[str | None, Field(description="Name and label for the new node, used to reference it in later calls. Strongly recommended — auto-generated names are hard to predict.")] = None,
    location: Annotated[list[float] | None, Field(description="[x, y] position in the node editor. Purely cosmetic, but spacing nodes out (roughly 300 units apart, right-to-left) keeps the tree readable for the user.")] = None,
    inputs: Annotated[dict | None, Field(description="Initial socket values by name, e.g. {'Scale': 12, 'Detail': 4}. Same values you would pass to set_node_input.")] = None,
    properties: Annotated[dict | None, Field(description="Node properties (not sockets) by bpy name, e.g. {'operation': 'MULTIPLY'} on Math, {'noise_dimensions': '4D'} on TexNoise, {'image': 'wood.png'} on TexImage.")] = None,
) -> dict:
    """Add one node to a material's tree and set its values in the same call.

    Adding a node does not connect it — follow with link_nodes, or use build_node_tree to
    create several nodes and their links at once, which is far fewer round trips for
    anything non-trivial.
    """
    return call("add_shader_node", material=material, type=type, name=name, location=location, inputs=inputs,
                properties=properties)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_shader_node(
    material: Annotated[str, Field(description="Material that owns the node.")],
    node: Annotated[str, Field(description=_NODE_DOC)],
) -> dict:
    """Delete a node from a material's tree, along with every link attached to it.

    Downstream nodes fall back to their own default values. Deleting the Material Output
    or the surface shader leaves the material rendering as nothing.
    """
    return call("remove_shader_node", material=material, node=node)


@mcp.tool(annotations=UPDATE)
def set_node_input(
    material: Annotated[str, Field(description="Material that owns the node.")],
    node: Annotated[str, Field(description=_NODE_DOC)],
    socket: Annotated[Socket, Field(description=_SOCKET_DOC)],
    value: Annotated[float | int | bool | str | list, Field(description="Value matching the socket type: float for VALUE, [r,g,b] or [r,g,b,a] 0-1 for RGBA, [x,y,z] for VECTOR, bool for BOOLEAN, an object/image name for pointer sockets.")],
) -> dict:
    """Set the default value of one node input socket.

    Only takes effect while nothing is linked into that socket — a link always wins over
    the value beneath it. To change what feeds the socket instead, use link_nodes, or
    unlink_nodes first to expose the value again.
    """
    return call("set_node_input", material=material, node=node, socket=socket, value=value)


@mcp.tool(annotations=UPDATE)
def set_node_property(
    material: Annotated[str, Field(description="Material that owns the node.")],
    node: Annotated[str, Field(description=_NODE_DOC)],
    property: Annotated[str, Field(description="bpy property name, e.g. 'operation', 'blend_type', 'data_type', 'image', 'interpolation', 'projection', 'distribution'. An invalid name fails with the list of writable properties for that node.")],
    value: Annotated[float | int | bool | str | list | None, Field(description="New value. Enum properties take the identifier string (uppercase, e.g. 'MULTIPLY'); pointer properties like 'image' or 'node_tree' take a datablock NAME, or a file path for images.")],
) -> dict:
    """Set a node property — a setting on the node itself rather than one of its input sockets.

    Properties change what a node does (Math's `operation`, Mix's `blend_type`), and often
    change which sockets exist, so the response lists the node's sockets after the change.
    Use set_node_input for the sockets themselves.
    """
    return call("set_node_property", material=material, node=node, property=property, value=value)


@mcp.tool(annotations=UPDATE)
def link_nodes(
    material: Annotated[str, Field(description="Material that owns both nodes.")],
    from_node: Annotated[str, Field(description="Source node name (the one producing the value).")],
    from_socket: Annotated[Socket, Field(description="Output socket on the source node, e.g. 'Color', 'Fac', 'BSDF'. " + _SOCKET_DOC)],
    to_node: Annotated[str, Field(description="Destination node name (the one consuming the value).")],
    to_socket: Annotated[Socket, Field(description="Input socket on the destination node, e.g. 'Base Color', 'Surface'. " + _SOCKET_DOC)],
) -> dict:
    """Connect one node's output to another node's input.

    Linking into a socket that is already connected replaces the old link. Incompatible
    socket types fail rather than silently doing nothing. Signal flows right to left in
    the UI but the arguments here read source-to-destination.
    """
    return call("link_nodes", material=material, from_node=from_node, from_socket=from_socket, to_node=to_node,
                to_socket=to_socket)


@mcp.tool(annotations=UPDATE)
def unlink_nodes(
    material: Annotated[str, Field(description="Material that owns the node.")],
    to_node: Annotated[str, Field(description=_NODE_DOC)],
    to_socket: Annotated[Socket, Field(description="The INPUT socket to disconnect. " + _SOCKET_DOC)],
) -> dict:
    """Remove every link feeding one input socket, exposing its default value again.

    Addressed by destination because an input takes at most one link, while an output can
    fan out to many. The nodes themselves are left in place — use remove_shader_node to
    delete them.
    """
    return call("unlink_nodes", material=material, to_node=to_node, to_socket=to_socket)


@mcp.tool(annotations=UPDATE)
def set_color_ramp(
    material: Annotated[str, Field(description="Material that owns the ramp node.")],
    node: Annotated[str, Field(description="Name of a Color Ramp (ValToRGB) node.")],
    stops: Annotated[list[dict], Field(description="The complete list of stops, e.g. [{'position': 0.0, 'color': [0,0,0]}, {'position': 1.0, 'color': [1,1,1]}]. Position is 0-1, colour is [r,g,b] or [r,g,b,a] 0-1. This REPLACES all existing stops rather than adding to them.")],
    interpolation: Annotated[str | None, Field(description="'LINEAR' (default), 'CONSTANT' (hard steps, for masks and toon shading), 'EASE', 'B_SPLINE' or 'CARDINAL'.")] = None,
) -> dict:
    """Define a Color Ramp node's gradient stops in one call.

    Colour ramps turn a single value (noise, height, a mask) into colours, so this is the
    usual way to shape procedural textures. The stop list is replacing, not additive —
    always pass the full gradient you want.
    """
    return call("set_color_ramp", material=material, node=node, stops=stops, interpolation=interpolation)


@mcp.tool(annotations=CREATE)
def build_node_tree(
    material: Annotated[str, Field(description="Material whose tree to build in.")],
    nodes: Annotated[list[dict], Field(description="Nodes to create: [{'type': 'TexNoise', 'name': 'N', 'location': [-600, 0], 'inputs': {'Scale': 5}, 'properties': {...}}, ...]. Only 'type' is required, but always give 'name' so links can reference the node.")],
    links: Annotated[list[dict] | None, Field(description="Links between them: [{'from_node': 'N', 'from_socket': 'Fac', 'to_node': 'P', 'to_socket': 'Base Color'}, ...]. Names must match those in `nodes` or already exist in the tree.")] = None,
    clear: Annotated[bool, Field(description="true wipes the existing tree first, INCLUDING the Principled BSDF and Material Output — so your node list must then supply an output node or the material renders as nothing. false (default) adds to what is there.")] = False,
) -> dict:
    """Create many nodes and their links in a single call — the efficient way to build a shader.

    Prefer this over repeated add_shader_node/link_nodes calls: one round trip instead of
    a dozen, and the whole tree either builds or fails together. Mind `clear`, which
    removes the output node too.
    """
    return call("build_node_tree", material=material, nodes=nodes, links=links, clear=clear)


@mcp.tool(annotations=READ_ONLY)
def get_node_types(
    tree: Annotated[str, Field(description="'shader' for material nodes (102 types) or 'geometry' for geometry-node types (274 types).")] = "shader",
    filter: Annotated[str | None, Field(description="Case-insensitive substring on the type name or label, e.g. 'noise', 'mix', 'curve'. Omit at your peril — the unfiltered geometry list is 274 entries.")] = None,
) -> list[dict]:
    """Search the node types available in this Blender build, each with its exact input and output socket names.

    The reliable way to get socket names right before calling add_shader_node or
    link_nodes, since they change between Blender versions. Serves both shader and
    geometry node trees; always pass a `filter`.
    """
    return call("get_node_types", tree=tree, filter=filter)
