"""节点树共用操作（shader 材质树与 geometry 节点组）。模块顶层不得调用 bpy。"""
from __future__ import annotations

import os

import bpy

from .utils import (ToolError, abs_path, color4, enum_check, find_collection, find_image, find_material,
                    find_node_group, find_object, find_texture, serialize, vec)

_BASE_NODE_PROPS: set[str] | None = None
_TYPE_CACHE: dict[str, list[dict]] = {}


def get_tree(material: str | None = None, node_group: str | None = None) -> bpy.types.NodeTree:
    if material:
        m = find_material(material)
        if m.node_tree is None:
            m.use_nodes = True
        return m.node_tree
    if node_group:
        return find_node_group(node_group)
    raise ToolError("material or node_group is required")


def find_node(tree: bpy.types.NodeTree, name: str) -> bpy.types.Node:
    n = tree.nodes.get(name)
    if n is not None:
        return n
    for x in tree.nodes:
        if x.label == name:
            return x
    raise ToolError(f"Node '{name}' not found. Available: {', '.join(x.name for x in tree.nodes)}")


def find_socket(sockets, key):
    """key: 名字 / 索引 / 'Name#2'（第二个同名插槽）。"""
    if isinstance(key, bool):
        raise ToolError("socket key must be a name or an index")
    if isinstance(key, int):
        if 0 <= key < len(sockets):
            return sockets[key]
        raise ToolError(f"socket index {key} out of range (0..{len(sockets) - 1})")
    if isinstance(key, str):
        base, nth = key, 0
        if "#" in key:
            base, n = key.rsplit("#", 1)
            if n.isdigit():
                nth = int(n) - 1
        matches = [s for s in sockets if s.name == base or s.identifier == base]
        if not matches:
            matches = [s for s in sockets if s.name.lower() == base.lower()]
        if not matches:
            avail = ", ".join(f"{s.name}" for s in sockets if s.enabled)
            raise ToolError(f"socket '{key}' not found. Available: {avail}")
        if nth >= len(matches):
            raise ToolError(f"only {len(matches)} socket(s) named '{base}'")
        return matches[nth]
    raise ToolError(f"unsupported socket key {key!r}")


def socket_value(sock):
    if not hasattr(sock, "default_value"):
        return None
    try:
        return serialize(sock.default_value)
    except Exception:  # noqa: BLE001
        return None


_POINTER_SOCKETS = {
    "OBJECT": lambda n: find_object(n),
    "COLLECTION": lambda n: find_collection(n),
    "IMAGE": lambda n: find_image(n),
    "MATERIAL": lambda n: find_material(n),
    "TEXTURE": lambda n: find_texture(n),
}


def set_socket_value(sock, value):
    if not hasattr(sock, "default_value"):
        raise ToolError(f"socket '{sock.name}' ({sock.type}) has no default value; link it instead")
    t = sock.type
    try:
        if t == "RGBA":
            sock.default_value = color4(value)
        elif t == "VECTOR":
            v = list(value)
            n = len(sock.default_value)
            if len(v) < n:
                v += [0.0] * (n - len(v))
            sock.default_value = v[:n]
        elif t == "VALUE":
            sock.default_value = float(value)
        elif t == "INT":
            sock.default_value = int(value)
        elif t == "BOOLEAN":
            sock.default_value = bool(value)
        elif t == "STRING":
            sock.default_value = str(value)
        elif t in _POINTER_SOCKETS:
            sock.default_value = None if value is None else _POINTER_SOCKETS[t](value)
        else:
            sock.default_value = value
    except (TypeError, ValueError) as e:
        raise ToolError(f"cannot set socket '{sock.name}' ({t}) to {value!r}: {e}") from e


def _base_props() -> set[str]:
    global _BASE_NODE_PROPS
    if _BASE_NODE_PROPS is None:
        _BASE_NODE_PROPS = {p.identifier for p in bpy.types.Node.bl_rna.properties} | {"color_ramp", "mapping", "texture_mapping",
                                                                                      "color_mapping", "image_user", "interface"}
    return _BASE_NODE_PROPS


def node_props(node) -> dict:
    base = _base_props()
    out = {}
    for p in node.bl_rna.properties:
        if p.identifier in base or p.is_readonly:
            continue
        try:
            out[p.identifier] = serialize(getattr(node, p.identifier))
        except Exception:  # noqa: BLE001
            continue
    if node.bl_idname in ("ShaderNodeValToRGB",) and hasattr(node, "color_ramp"):
        out["color_ramp"] = {"interpolation": node.color_ramp.interpolation,
                             "stops": [{"position": round(e.position, 6), "color": vec(e.color)} for e in node.color_ramp.elements]}
    return out


def node_dump(node) -> dict:
    return {
        "name": node.name, "type": node.bl_idname, "label": node.label, "location": vec(node.location),
        "inputs": [{"name": s.name, "type": s.type, "value": socket_value(s), "linked": s.is_linked}
                   for s in node.inputs if s.enabled],
        "outputs": [{"name": s.name, "type": s.type, "linked": s.is_linked} for s in node.outputs if s.enabled],
        "properties": node_props(node),
    }


def tree_dump(tree) -> dict:
    return {
        "name": tree.name, "type": tree.bl_idname,
        "nodes": [node_dump(n) for n in tree.nodes],
        "links": [{"from_node": l.from_node.name, "from_socket": l.from_socket.name,
                   "to_node": l.to_node.name, "to_socket": l.to_socket.name} for l in tree.links],
    }


def resolve_node_type(tree, type_name: str) -> str:
    prefix = "GeometryNode" if tree.bl_idname == "GeometryNodeTree" else "ShaderNode"
    for cand in (type_name, prefix + type_name, "Node" + type_name, "FunctionNode" + type_name, "ShaderNode" + type_name):
        if hasattr(bpy.types, cand):
            return cand
    raise ToolError(f"unknown node type '{type_name}'. Use get_node_types to search (e.g. TexNoise, MixShader, MeshCube)")


def add_node(tree, type: str, name=None, location=None, inputs=None, properties=None):
    bl = resolve_node_type(tree, type)
    try:
        node = tree.nodes.new(bl)
    except RuntimeError as e:
        raise ToolError(f"cannot add node '{bl}' to {tree.bl_idname}: {e}") from e
    if name:
        node.name = name
        node.label = name
    if location is not None:
        node.location = location
    if properties:
        for k, v in properties.items():
            set_property(node, k, v)
    if inputs:
        for k, v in inputs.items():
            set_socket_value(find_socket(node.inputs, k), v)
    return node


def _pointer_for(kind: str, value):
    if "Image" in kind:
        if isinstance(value, str) and (os.path.sep in value or value.lower().endswith((".png", ".jpg", ".jpeg", ".exr", ".hdr", ".tif", ".tiff"))) \
                and value not in bpy.data.images:
            return bpy.data.images.load(abs_path(value), check_existing=True)
        return find_image(value)
    if "NodeTree" in kind:
        return find_node_group(value)
    if kind == "Object":
        return find_object(value)
    if kind == "Collection":
        return find_collection(value)
    if kind == "Material":
        return find_material(value)
    if kind == "Texture":
        return find_texture(value)
    raise ToolError(f"cannot resolve pointer of type {kind} by name")


def set_property(node, prop: str, value):
    p = node.bl_rna.properties.get(prop)
    if p is None or p.is_readonly:
        avail = sorted(k for k in node_props(node))
        raise ToolError(f"node '{node.name}' has no writable property '{prop}'. Available: {', '.join(avail)}")
    if p.type == "POINTER":
        setattr(node, prop, None if value is None else _pointer_for(p.fixed_type.identifier, value))
    elif p.type == "ENUM":
        opts = [e.identifier for e in p.enum_items]
        setattr(node, prop, enum_check(value, opts, prop))
    else:
        setattr(node, prop, value)
    return serialize(getattr(node, prop))


def link(tree, from_node, from_socket, to_node, to_socket) -> dict:
    a = find_node(tree, from_node)
    b = find_node(tree, to_node)
    out = find_socket(a.outputs, from_socket)
    inp = find_socket(b.inputs, to_socket)
    lk = tree.links.new(out, inp)
    if not lk.is_valid:
        raise ToolError(f"invalid link {a.name}.{out.name} -> {b.name}.{inp.name} (socket types {out.type} -> {inp.type})")
    return {"from_node": a.name, "from_socket": out.name, "to_node": b.name, "to_socket": inp.name}


def unlink(tree, to_node, to_socket) -> int:
    b = find_node(tree, to_node)
    inp = find_socket(b.inputs, to_socket)
    n = 0
    for lk in list(inp.links):
        tree.links.remove(lk)
        n += 1
    return n


def build(tree, nodes, links, clear: bool) -> dict:
    if clear:
        tree.nodes.clear()
    created = []
    for spec in nodes or []:
        if "type" not in spec:
            raise ToolError("each node spec needs 'type'")
        n = add_node(tree, spec["type"], spec.get("name"), spec.get("location"), spec.get("inputs"), spec.get("properties"))
        created.append(n.name)
    made = [link(tree, l["from_node"], l["from_socket"], l["to_node"], l["to_socket"]) for l in (links or [])]
    return {"nodes": created, "links": made}


def node_types(kind: str, filter: str | None = None) -> list[dict]:
    kind = enum_check(kind.lower(), ["shader", "geometry"], "tree")
    if kind not in _TYPE_CACHE:
        if kind == "shader":
            tmp = bpy.data.materials.new("__mcp_probe")
            tree = tmp.node_tree
            prefixes = ("ShaderNode",)
        else:
            tmp = bpy.data.node_groups.new("__mcp_probe", "GeometryNodeTree")
            tree = tmp
            prefixes = ("GeometryNode", "FunctionNode")
        out = []
        for n in sorted(dir(bpy.types)):
            if not n.startswith(prefixes):
                continue
            try:
                node = tree.nodes.new(n)
            except RuntimeError:
                continue
            out.append({"type": n, "label": getattr(node, "bl_label", n),
                        "inputs": [{"name": s.name, "type": s.type} for s in node.inputs],
                        "outputs": [{"name": s.name, "type": s.type} for s in node.outputs]})
            tree.nodes.remove(node)
        if kind == "shader":
            bpy.data.materials.remove(tmp)
        else:
            bpy.data.node_groups.remove(tmp)
        _TYPE_CACHE[kind] = out
    res = _TYPE_CACHE[kind]
    if filter:
        f = filter.lower()
        res = [t for t in res if f in t["type"].lower() or f in t["label"].lower()]
    return res


def set_color_ramp(node, stops: list[dict], interpolation: str | None = None) -> dict:
    if not hasattr(node, "color_ramp"):
        raise ToolError(f"node '{node.name}' is not a Color Ramp")
    ramp = node.color_ramp
    if interpolation:
        ramp.interpolation = enum_check(interpolation, [e.identifier for e in ramp.bl_rna.properties["interpolation"].enum_items], "interpolation")
    if stops:
        while len(ramp.elements) > 1:
            ramp.elements.remove(ramp.elements[-1])
        first = ramp.elements[0]
        first.position = float(stops[0]["position"])
        first.color = color4(stops[0]["color"])
        for s in stops[1:]:
            e = ramp.elements.new(float(s["position"]))
            e.color = color4(s["color"])
    return {"interpolation": ramp.interpolation,
            "stops": [{"position": round(e.position, 6), "color": vec(e.color)} for e in ramp.elements]}
