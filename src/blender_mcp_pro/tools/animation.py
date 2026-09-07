"""Animation。"""
from __future__ import annotations

from ..server import mcp
from ._base import LONG, call


@mcp.tool()
def get_animation_info(object: str | None = None) -> dict:
    """场景帧范围/fps/动作列表；给 object 时附带其 action、fcurve 摘要、NLA 轨道、形态键。"""
    return call("get_animation_info", object=object)


@mcp.tool()
def set_frame_range(start: int, end: int, fps: int | None = None) -> dict:
    """设置帧范围与 fps。"""
    return call("set_frame_range", start=start, end=end, fps=fps)


@mcp.tool()
def set_current_frame(frame: int) -> dict:
    """跳到某帧。"""
    return call("set_current_frame", frame=frame)


@mcp.tool()
def insert_keyframe(object: str, data_path: str, frame: int | None = None, index: int | None = None,
                    value: float | int | bool | list | None = None) -> dict:
    """插关键帧。data_path 如 location / rotation_euler / scale / hide_render / ["prop"]；给 value 先赋值再打帧；index 指定分量。"""
    return call("insert_keyframe", object=object, data_path=data_path, frame=frame, index=index, value=value)


@mcp.tool()
def insert_keyframes_batch(object: str, keys: list[dict]) -> dict:
    """批量打帧：keys=[{frame, location?, rotation?, scale?, <其他 data_path>?}]。"""
    return call("insert_keyframes_batch", object=object, keys=keys)


@mcp.tool()
def delete_keyframe(object: str, data_path: str, frame: int, index: int | None = None) -> dict:
    """删除某帧的关键帧。"""
    return call("delete_keyframe", object=object, data_path=data_path, frame=frame, index=index)


@mcp.tool()
def list_keyframes(object: str, data_path: str | None = None) -> list[dict]:
    """列出 fcurve 与关键帧（帧、值、插值）。"""
    return call("list_keyframes", object=object, data_path=data_path)


@mcp.tool()
def set_interpolation(object: str, mode: str, easing: str | None = None, data_path: str | None = None,
                      frame_range: list[int] | None = None) -> dict:
    """设置关键帧插值：CONSTANT/LINEAR/BEZIER/SINE/QUAD/…；easing: AUTO/EASE_IN/EASE_OUT/EASE_IN_OUT。"""
    return call("set_interpolation", object=object, mode=mode, easing=easing, data_path=data_path, frame_range=frame_range)


@mcp.tool()
def add_fcurve_modifier(object: str, data_path: str, type: str, settings: dict | None = None) -> dict:
    """给 fcurve 加修改器：CYCLES（循环）/NOISE/LIMITS/STEPPED/GENERATOR…；settings 为其属性。"""
    return call("add_fcurve_modifier", object=object, data_path=data_path, type=type, settings=settings)


@mcp.tool()
def assign_action(object: str, action: str | None = None) -> dict:
    """给对象指定动作（省略则新建）。"""
    return call("assign_action", object=object, action=action)


@mcp.tool()
def nla_push_down(object: str) -> dict:
    """把当前动作推入 NLA 轨道。"""
    return call("nla_push_down", object=object)


@mcp.tool()
def add_nla_strip(object: str, action: str, frame_start: int, track: str | None = None, blend_type: str | None = None) -> dict:
    """在 NLA 轨道上添加动作片段。"""
    return call("add_nla_strip", object=object, action=action, frame_start=frame_start, track=track, blend_type=blend_type)


@mcp.tool()
def bake_animation(object: str, frame_start: int | None = None, frame_end: int | None = None, step: int = 1,
                   visual_keying: bool = True, clear_constraints: bool = False) -> dict:
    """把约束/父级/NLA 的运动烘焙成逐帧关键帧。"""
    return call("bake_animation", timeout=LONG, object=object, frame_start=frame_start, frame_end=frame_end, step=step,
                visual_keying=visual_keying, clear_constraints=clear_constraints)


@mcp.tool()
def list_shape_keys(object: str) -> list[dict]:
    """列出形态键。"""
    return call("list_shape_keys", object=object)


@mcp.tool()
def set_shape_key(object: str, name: str, value: float, frame: int | None = None) -> dict:
    """设置形态键值（不存在则创建，含 Basis）；给 frame 则同时打关键帧。"""
    return call("set_shape_key", object=object, name=name, value=value, frame=frame)
