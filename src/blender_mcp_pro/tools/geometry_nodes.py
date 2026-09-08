"""Geometry Nodes — procedural geometry trees and their modifier inputs."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE

Socket = str | int
_SOCKET_DOC = (
    "Socket identifier: its name ('Geometry', 'Density', 'Value'), its 0-based index, or 'Name#2' for the second "
    "socket sharing a name. A wrong name fails with the node's full socket list."
)
_GROUP_DOC = "Geometry node group name, as returned by create_geometry_nodes or list_node_groups."


@mcp.tool(annotations=READ_ONLY)
def list_node_groups(
    type: Annotated[str | None, Field(description="'GEOMETRY' or 'SHADER' to filter. Omit to list every node group in the file.")] = None,
) -> list[dict]:
    """List the node groups in the file — the reusable trees that geometry-node modifiers and shader groups point at.

    Use it to find the group name to pass to the other tools here, or to check whether a
    tree you built earlier still exists.
    """
    return call("list_node_groups", type=type)


@mcp.tool(annotations=CREATE)
def create_geometry_nodes(
    object: Annotated[str, Field(description="Object to attach the geometry-nodes modifier to. Its existing mesh becomes the tree's input geometry.")],
    group_name: Annotated[str | None, Field(description="Name for the new node group. Pass one — you need it to address the tree in every subsequent call.")] = None,
    modifier_name: Annotated[str | None, Field(description="Name for the NODES modifier on the object. Needed later by set_gn_modifier_input.")] = None,
) -> dict:
    """Create a geometry node group and attach it to an object as a NODES modifier, pre-wired with Group Input and Group Output.

    The entry point for all procedural geometry work: this gives you an empty but valid
    tree, then add_geometry_node / link_geometry_nodes (or build_geometry_node_tree) fill
    it in. The object's original mesh flows in through Group Input, so passing it straight
    to Group Output leaves the object unchanged.
    """
    return call("create_geometry_nodes", object=object, group_name=group_name, modifier_name=modifier_name)


@mcp.tool(annotations=READ_ONLY)
def get_node_tree(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
) -> dict:
    """Dump a geometry node group: every node with its inputs and properties, all links, and the group's exposed interface sockets.

    Read this before editing a tree you did not just build — node names are otherwise
    unpredictable, and every editing tool here addresses nodes by name.
    """
    return call("get_node_tree", node_group=node_group)


@mcp.tool(annotations=CREATE)
def add_geometry_node(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    type: Annotated[str, Field(description="Node type; the 'GeometryNode' prefix is optional, so 'MeshCube' and 'GeometryNodeMeshCube' both work. Common: DistributePointsOnFaces, InstanceOnPoints, JoinGeometry, SetPosition, MeshCube, MeshUVSphere, Transform, RealizeInstances, ObjectInfo, SubdivideMesh. 274 types exist — search them with get_node_types(tree='geometry').")],
    name: Annotated[str | None, Field(description="Name and label for the node, used to reference it in links. Strongly recommended.")] = None,
    location: Annotated[list[float] | None, Field(description="[x, y] position in the node editor. Cosmetic, but spacing nodes ~250 apart keeps the tree readable.")] = None,
    inputs: Annotated[dict | None, Field(description="Initial socket values by name, e.g. {'Density': 15, 'Seed': 3}.")] = None,
    properties: Annotated[dict | None, Field(description="Node properties by bpy name, e.g. {'data_type': 'FLOAT_VECTOR'} or {'object': 'Rock'} on an Object Info node.")] = None,
) -> dict:
    """Add one node to a geometry node group, with its values set in the same call.

    The node is unconnected until you link it. For anything beyond a single node,
    build_geometry_node_tree creates nodes and links together in one round trip.
    """
    return call("add_geometry_node", node_group=node_group, type=type, name=name, location=location, inputs=inputs,
                properties=properties)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_geometry_node(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    node: Annotated[str, Field(description="Node name to delete.")],
) -> dict:
    """Delete a node from a geometry node group along with its links.

    Removing a node mid-chain breaks the flow to Group Output, and the object's geometry
    disappears until you reconnect it.
    """
    return call("remove_geometry_node", node_group=node_group, node=node)


@mcp.tool(annotations=UPDATE)
def link_geometry_nodes(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    from_node: Annotated[str, Field(description="Source node name.")],
    from_socket: Annotated[Socket, Field(description="Output socket on the source, e.g. 'Geometry', 'Points', 'Instances'. " + _SOCKET_DOC)],
    to_node: Annotated[str, Field(description="Destination node name.")],
    to_socket: Annotated[Socket, Field(description="Input socket on the destination. " + _SOCKET_DOC)],
) -> dict:
    """Connect one geometry node's output to another's input.

    Geometry must reach the Group Output node for anything to appear. Sockets are typed
    (Geometry, Points, Instances, Field values), and incompatible pairings fail rather
    than silently doing nothing.
    """
    return call("link_geometry_nodes", node_group=node_group, from_node=from_node, from_socket=from_socket,
                to_node=to_node, to_socket=to_socket)


@mcp.tool(annotations=UPDATE)
def unlink_geometry_nodes(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    to_node: Annotated[str, Field(description="Node whose input to disconnect.")],
    to_socket: Annotated[Socket, Field(description="The INPUT socket to clear. " + _SOCKET_DOC)],
) -> dict:
    """Remove the links feeding one input socket, restoring its default value.

    Addressed by destination because an input accepts one link while an output can fan out
    to many.
    """
    return call("unlink_geometry_nodes", node_group=node_group, to_node=to_node, to_socket=to_socket)


@mcp.tool(annotations=UPDATE)
def set_geometry_node_input(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    node: Annotated[str, Field(description="Node whose input to set.")],
    socket: Annotated[Socket, Field(description=_SOCKET_DOC)],
    value: Annotated[float | int | bool | str | list, Field(description="Value matching the socket type: float, [x,y,z] for vectors, [r,g,b,a] 0-1 for colours, an object name for Object sockets.")],
) -> dict:
    """Set the default value of a socket on a node INSIDE the tree.

    Distinct from set_gn_modifier_input, which sets the exposed parameters on the object's
    modifier panel. Use this one for values internal to the tree; a socket with a link
    into it ignores its default.
    """
    return call("set_geometry_node_input", node_group=node_group, node=node, socket=socket, value=value)


@mcp.tool(annotations=CREATE)
def add_group_socket(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    name: Annotated[str, Field(description="Label for the socket, which becomes the parameter name shown on the modifier panel.")],
    in_out: Annotated[str, Field(description="'INPUT' exposes a parameter the user can tweak; 'OUTPUT' emits a value from the group.")] = "INPUT",
    socket_type: Annotated[str, Field(description="'NodeSocketFloat', 'NodeSocketInt', 'NodeSocketBool', 'NodeSocketVector', 'NodeSocketColor', 'NodeSocketString', 'NodeSocketObject', 'NodeSocketCollection', 'NodeSocketMaterial' or 'NodeSocketGeometry'.")] = "NodeSocketFloat",
    default: Annotated[float | int | bool | str | list | None, Field(description="Initial value for the exposed parameter.")] = None,
) -> dict:
    """Expose a parameter on a geometry node group so it appears on the object's modifier panel.

    This is what turns a hard-coded tree into a reusable, tweakable one — expose 'Count' or
    'Scale' here, then drive it per-object with set_gn_modifier_input.
    """
    return call("add_group_socket", node_group=node_group, name=name, in_out=in_out, socket_type=socket_type,
                default=default)


@mcp.tool(annotations=UPDATE)
def set_gn_modifier_input(
    object: Annotated[str, Field(description="Object carrying the geometry-nodes modifier.")],
    modifier: Annotated[str, Field(description="Name of the NODES modifier on that object (from list_modifiers).")],
    input: Annotated[str, Field(description="The exposed parameter's NAME as given to add_group_socket. The underlying identifier is resolved for you.")],
    value: Annotated[float | int | bool | str | list | None, Field(description="Value for the parameter; Object and Material sockets take a datablock name.")],
) -> dict:
    """Set an exposed geometry-nodes parameter on one object's modifier.

    The per-object counterpart to set_geometry_node_input: the same node group can drive
    many objects, each with its own values here. Use it after add_group_socket exposed the
    parameter.
    """
    return call("set_gn_modifier_input", object=object, modifier=modifier, input=input, value=value)


@mcp.tool(annotations=CREATE)
def build_geometry_node_tree(
    node_group: Annotated[str, Field(description=_GROUP_DOC)],
    nodes: Annotated[list[dict], Field(description="Nodes to create: [{'type': 'DistributePointsOnFaces', 'name': 'Dist', 'location': [-200, 0], 'inputs': {'Density': 10}}, ...]. Only 'type' is required; always give 'name' so links can reference it.")],
    links: Annotated[list[dict] | None, Field(description="Links: [{'from_node': 'Dist', 'from_socket': 'Points', 'to_node': 'Inst', 'to_socket': 'Points'}, ...]. Names may refer to nodes in this call or ones already in the tree, such as 'Group Input' and 'Group Output'.")] = None,
    clear: Annotated[bool, Field(description="true wipes the tree first, INCLUDING Group Input and Group Output — your node list must then supply them. false (default) adds to what is there.")] = False,
) -> dict:
    """Build a whole geometry node tree — many nodes and their links — in a single call.

    Strongly preferred over node-by-node construction: geometry trees need five or ten
    connected nodes to do anything, and this is one round trip that succeeds or fails as a
    unit. Remember to link the final node into 'Group Output' or nothing renders.
    """
    return call("build_geometry_node_tree", node_group=node_group, nodes=nodes, links=links, clear=clear)
