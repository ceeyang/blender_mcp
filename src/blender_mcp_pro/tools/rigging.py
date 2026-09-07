"""Rigging。"""
from __future__ import annotations

from ..server import mcp
from ._base import LONG, call

Objects = list[str] | dict | str


@mcp.tool()
def create_armature(name: str | None = None, location: list[float] | None = None, bones: list[dict] | None = None) -> dict:
    """新建骨架；bones=[{name, head, tail, parent?, roll?, connect?, deform?}] 一次建骨链。"""
    return call("create_armature", name=name, location=location, bones=bones)


@mcp.tool()
def list_bones(armature: str, pose: bool = False) -> list[dict]:
    """列出骨骼（head/tail/父子/deform），pose=true 附带姿态变换与约束。"""
    return call("list_bones", armature=armature, pose=pose)


@mcp.tool()
def add_bone(armature: str, name: str, head: list[float], tail: list[float], parent: str | None = None, roll: float = 0.0,
             connect: bool = False) -> dict:
    """添加一根骨骼。"""
    return call("add_bone", armature=armature, name=name, head=head, tail=tail, parent=parent, roll=roll, connect=connect)


@mcp.tool()
def set_bone(armature: str, bone: str, head: list[float] | None = None, tail: list[float] | None = None, roll: float | None = None,
             parent: str | None = None, connect: bool | None = None, deform: bool | None = None, inherit_scale: str | None = None) -> dict:
    """修改骨骼（parent 传空字符串即清除父级）。"""
    return call("set_bone", armature=armature, bone=bone, head=head, tail=tail, roll=roll, parent=parent, connect=connect, deform=deform,
                inherit_scale=inherit_scale)


@mcp.tool()
def remove_bone(armature: str, bone: str) -> dict:
    """删除骨骼。"""
    return call("remove_bone", armature=armature, bone=bone)


@mcp.tool()
def parent_to_armature(objects: Objects, armature: str, method: str = "AUTOMATIC") -> dict:
    """把网格绑定到骨架。method: AUTOMATIC(自动权重)/ENVELOPE/EMPTY_GROUPS/DEFORM。"""
    return call("parent_to_armature", timeout=LONG, objects=objects, armature=armature, method=method)


@mcp.tool()
def add_bone_constraint(armature: str, bone: str, type: str, settings: dict | None = None) -> dict:
    """给骨骼加约束（IK/COPY_ROTATION/COPY_LOCATION/TRACK_TO/DAMPED_TRACK/LIMIT_ROTATION/STRETCH_TO…）。settings 里 target 给对象名、subtarget 给骨骼名。"""
    return call("add_bone_constraint", armature=armature, bone=bone, type=type, settings=settings)


@mcp.tool()
def set_pose(armature: str, bones: dict, keyframe: bool = False, frame: int | None = None) -> dict:
    """设置姿态：bones={骨名: {location?, rotation_euler?|rotation_quaternion?, scale?}}；keyframe 时打关键帧。"""
    return call("set_pose", armature=armature, bones=bones, keyframe=keyframe, frame=frame)


@mcp.tool()
def reset_pose(armature: str, bones: list[str] | None = None) -> dict:
    """重置姿态到静止位。"""
    return call("reset_pose", armature=armature, bones=bones)


@mcp.tool()
def set_vertex_group_weights(object: str, group: str, weights: list[list[float]] | None = None, all: float | None = None,
                             mode: str = "REPLACE") -> dict:
    """设置顶点组权重：weights=[[vertex_index, weight], …] 或 all=统一值；mode: REPLACE/ADD/SUBTRACT。组不存在则创建。"""
    return call("set_vertex_group_weights", object=object, group=group, weights=weights, all=all, mode=mode)


@mcp.tool()
def add_rigify_metarig(type: str = "human", name: str | None = None) -> dict:
    """添加 Rigify 元骨架：human/basic_human/basic_quadruped/cat/wolf/horse/shark/bird。"""
    return call("add_rigify_metarig", type=type, name=name)


@mcp.tool()
def generate_rigify_rig(metarig: str) -> dict:
    """由元骨架生成 Rigify 控制骨架。"""
    return call("generate_rigify_rig", timeout=LONG, metarig=metarig)
