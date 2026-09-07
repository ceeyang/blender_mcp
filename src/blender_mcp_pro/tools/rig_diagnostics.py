"""Rig Diagnostics。"""
from __future__ import annotations

from ..server import mcp
from ._base import call


@mcp.tool()
def check_rig(armature: str) -> dict:
    """骨架综合体检：零长骨、多根、deform 骨无顶点组、未权重/未归一顶点、未应用缩放、约束目标丢失、命名不对称。"""
    return call("check_rig", armature=armature)


@mcp.tool()
def check_bone_hierarchy(armature: str) -> dict:
    """骨骼层级树、孤立骨、最大深度。"""
    return call("check_bone_hierarchy", armature=armature)


@mcp.tool()
def check_bone_naming(armature: str, convention: str = "BLENDER") -> dict:
    """检查 .L/.R 对称命名：缺失镜像、不规范命名。"""
    return call("check_bone_naming", armature=armature, convention=convention)


@mcp.tool()
def find_unweighted_vertices(object: str, threshold: float = 0.0001) -> dict:
    """找出没有骨骼权重的顶点。"""
    return call("find_unweighted_vertices", object=object, threshold=threshold)


@mcp.tool()
def get_bone_influence(object: str, vertex_index: int) -> list[dict]:
    """某顶点受哪些顶点组/骨骼影响及权重。"""
    return call("get_bone_influence", object=object, vertex_index=vertex_index)


@mcp.tool()
def list_constraint_issues(armature: str) -> list[dict]:
    """列出骨骼约束问题：目标缺失、subtarget 不存在、IK 链过长、被禁用、influence 为 0。"""
    return call("list_constraint_issues", armature=armature)


@mcp.tool()
def normalize_weights(object: str, lock_active: bool = False, groups: list[str] | None = None) -> dict:
    """把每个顶点的权重归一化到 1（lock_active 保持活动组不变）。"""
    return call("normalize_weights", object=object, lock_active=lock_active, groups=groups)
