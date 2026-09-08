"""Animation — keyframes, F-curves, actions, NLA, baking and shape keys."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import LONG, call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE

_DATA_PATH_DOC = (
    "Animated property path on the object: 'location', 'rotation_euler', 'scale', 'hide_render', "
    "'delta_location', or a nested path like \"modifiers[\\\"Bevel\\\"].width\" (use DOUBLE quotes inside brackets — "
    "single quotes are not accepted)."
)


@mcp.tool(annotations=READ_ONLY)
def get_animation_info(
    object: Annotated[str | None, Field(description="Object to report on. Omit for a scene-level summary (frame range, fps, current frame) without per-object detail.")] = None,
) -> dict:
    """Summarise animation state: scene frame range and fps, plus an object's action, F-curves and keyframe counts.

    The starting point for any animation work — it tells you whether an object is animated
    at all and which properties have curves, before you go inspecting keyframes.
    """
    return call("get_animation_info", object=object)


@mcp.tool(annotations=UPDATE)
def set_frame_range(
    start: Annotated[int, Field(description="First frame of the animation, usually 1.")],
    end: Annotated[int, Field(description="Last frame, inclusive. At 24 fps, a 3-second shot ends at frame 72.")],
    fps: Annotated[int | None, Field(description="Frames per second: 24 film, 25 PAL, 30 or 60 for games and web. Changing fps does NOT retime existing keyframes — they keep their frame numbers and the animation simply plays faster or slower.")] = None,
) -> dict:
    """Set the scene's playback and render frame range, and optionally its frame rate.

    This is what render_animation uses by default, so it defines how long the output is.
    Set it before creating keyframes so the timeline matches what you are building.
    """
    return call("set_frame_range", start=start, end=end, fps=fps)


@mcp.tool(annotations=UPDATE)
def set_current_frame(
    frame: Annotated[int, Field(description="Frame to jump to. May sit outside the scene's frame range.")],
) -> dict:
    """Move the playhead to a specific frame, evaluating the scene at that point in time.

    Everything animated updates to its value at that frame, so this is how you inspect a
    pose mid-animation, or how you position things before inserting a keyframe with
    insert_keyframe (which defaults to the current frame).
    """
    return call("set_current_frame", frame=frame)


@mcp.tool(annotations=CREATE)
def insert_keyframe(
    object: Annotated[str, Field(description="Object to key.")],
    data_path: Annotated[str, Field(description=_DATA_PATH_DOC)],
    frame: Annotated[int | None, Field(description="Frame to key at. Defaults to the scene's current frame. A key already on that frame is overwritten.")] = None,
    index: Annotated[int | None, Field(description="Which component of a vector property to key: 0=X, 1=Y, 2=Z. Omit to key all components at once, which is almost always what you want.")] = None,
    value: Annotated[float | int | bool | list | None, Field(description="Value to set BEFORE keying, so you can position and key in one call. Omit to key whatever the property currently holds.")] = None,
) -> dict:
    """Record one keyframe on one property, optionally setting the value first.

    The standard animation loop is: insert a key at the start frame, then another at the
    end frame with a different `value` — Blender interpolates between them. Use
    insert_keyframes_batch to lay down a whole sequence in a single call instead.
    """
    return call("insert_keyframe", object=object, data_path=data_path, frame=frame, index=index, value=value)


@mcp.tool(annotations=CREATE)
def insert_keyframes_batch(
    object: Annotated[str, Field(description="Object to animate.")],
    keys: Annotated[list[dict], Field(description="One dict per keyframe: [{'frame': 1, 'location': [0,0,0]}, {'frame': 48, 'location': [5,0,2], 'rotation': [0,0,3.14]}, ...]. Each accepts 'frame' plus any of 'location', 'rotation' (Euler XYZ in radians) and 'scale'. Only the channels present in a given entry are keyed on that frame.")],
) -> dict:
    """Lay down a whole sequence of transform keyframes in one call.

    Far better than repeated insert_keyframe calls for building a motion path — one round
    trip, and the timing is easy to read in the argument. For non-transform properties
    (modifier values, visibility) use insert_keyframe with a `data_path`.
    """
    return call("insert_keyframes_batch", object=object, keys=keys)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_keyframe(
    object: Annotated[str, Field(description="Object to modify.")],
    data_path: Annotated[str, Field(description=_DATA_PATH_DOC)],
    frame: Annotated[int, Field(description="Frame of the keyframe to remove. Must match exactly.")],
    index: Annotated[int | None, Field(description="Component to remove for vector properties (0=X, 1=Y, 2=Z). Omit to remove all components at that frame.")] = None,
) -> dict:
    """Remove one keyframe, letting the surrounding keys interpolate through the gap.

    Deleting the last key on a channel removes the F-curve entirely and the property goes
    back to being a static value.
    """
    return call("delete_keyframe", object=object, data_path=data_path, frame=frame, index=index)


@mcp.tool(annotations=READ_ONLY)
def list_keyframes(
    object: Annotated[str, Field(description="Animated object to inspect.")],
    data_path: Annotated[str | None, Field(description="Restrict to one property path. Omit to list every animated channel.")] = None,
) -> list[dict]:
    """List an object's F-curves and every keyframe on them, with frame numbers, values and interpolation.

    Use it to check what you built, find the exact frames to edit, or work out why motion
    looks wrong — uneven spacing and unexpected interpolation both show up here.
    """
    return call("list_keyframes", object=object, data_path=data_path)


@mcp.tool(annotations=UPDATE)
def set_interpolation(
    object: Annotated[str, Field(description="Animated object.")],
    mode: Annotated[str, Field(description="'BEZIER' (default, smooth ease in and out), 'LINEAR' (constant speed — right for turntables and mechanical motion), 'CONSTANT' (hold then jump, for stop-motion and visibility switches), or an easing curve like 'SINE', 'QUAD', 'CUBIC', 'BACK', 'BOUNCE', 'ELASTIC'.")],
    easing: Annotated[str | None, Field(description="Which side the easing applies to: 'EASE_IN', 'EASE_OUT', 'EASE_IN_OUT' or 'AUTO'. Only meaningful for the named easing curves, not BEZIER/LINEAR/CONSTANT.")] = None,
    data_path: Annotated[str | None, Field(description="Restrict to one property. Omit to apply to every F-curve on the object.")] = None,
    frame_range: Annotated[list[int] | None, Field(description="[start, end] to limit the change to keyframes in that span. Omit to apply to all of them.")] = None,
) -> dict:
    """Change how the animation interpolates between existing keyframes.

    This is the difference between motion that reads as mechanical and motion that reads
    as alive. Blender's default BEZIER eases in and out of every key, which is wrong for
    constant-speed motion — a turntable needs LINEAR or it visibly stutters at each
    rotation.
    """
    return call("set_interpolation", object=object, mode=mode, easing=easing, data_path=data_path,
                frame_range=frame_range)


@mcp.tool(annotations=CREATE)
def add_fcurve_modifier(
    object: Annotated[str, Field(description="Animated object.")],
    data_path: Annotated[str, Field(description=_DATA_PATH_DOC + " The property must already have keyframes.")],
    type: Annotated[str, Field(description="'CYCLES' repeats the keyed range forever, so two keys become an endless loop; 'NOISE' adds procedural jitter for handheld or organic motion; 'LIMITS' clamps the curve; 'GENERATOR' replaces it with a polynomial.")],
    settings: Annotated[dict | None, Field(description="Modifier properties, e.g. {'mode_before': 'REPEAT', 'mode_after': 'REPEAT'} for CYCLES, or {'strength': 0.3, 'scale': 20} for NOISE. Look names up with get_api_docs('bpy.types.FModifierNoise').")] = None,
) -> dict:
    """Attach a procedural modifier to an F-curve, changing it without adding keyframes.

    CYCLES is the big one: keyframe a single rotation, add CYCLES, and it loops forever
    with no extra keys — that is how you build an endless spin or a repeating bob.
    """
    return call("add_fcurve_modifier", object=object, data_path=data_path, type=type, settings=settings)


@mcp.tool(annotations=UPDATE)
def assign_action(
    object: Annotated[str, Field(description="Object to attach the action to.")],
    action: Annotated[str | None, Field(description="Name of an existing action to make active. Omit to create a fresh empty action, which is how you start a new animation while keeping the old one stored in the file.")] = None,
) -> dict:
    """Set which action (a named container of keyframes) is active on an object.

    Actions are how Blender stores separate animations — 'Walk', 'Idle', 'Jump' — on one
    object. Only the active action plays and receives new keyframes; the rest sit in the
    file until pushed into NLA strips.
    """
    return call("assign_action", object=object, action=action)


@mcp.tool(annotations=UPDATE)
def nla_push_down(
    object: Annotated[str, Field(description="Object whose active action to stash.")],
) -> dict:
    """Push the active action down into a new NLA strip, freeing the object for a new animation.

    After this the object has no active action, so the next keyframes you insert start a
    fresh one while the old animation is preserved as a strip and still plays. The standard
    way to build up multiple takes on one object.
    """
    return call("nla_push_down", object=object)


@mcp.tool(annotations=CREATE)
def add_nla_strip(
    object: Annotated[str, Field(description="Object to add the strip to.")],
    action: Annotated[str, Field(description="Name of an existing action to place in the strip.")],
    frame_start: Annotated[int, Field(description="Frame where the strip begins. This is how you retime an action — the same action can appear at several start frames.")],
    track: Annotated[str | None, Field(description="Name of the NLA track to place it on. Omit to create a new track; strips on higher tracks blend over lower ones.")] = None,
    blend_type: Annotated[str | None, Field(description="How it combines with lower tracks: 'REPLACE' (default), 'ADD', 'SUBTRACT' or 'MULTIPLY'.")] = None,
) -> dict:
    """Place an existing action on the NLA timeline as a strip at a given frame.

    Lets you reuse one action several times at different times, and layer animations
    (a walk on one track, a wave added on another) without duplicating keyframes.
    """
    return call("add_nla_strip", object=object, action=action, frame_start=frame_start, track=track,
                blend_type=blend_type)


@mcp.tool(annotations=CREATE)
def bake_animation(
    object: Annotated[str, Field(description="Object whose motion to bake.")],
    frame_start: Annotated[int | None, Field(description="First frame to bake. Defaults to the scene range start.")] = None,
    frame_end: Annotated[int | None, Field(description="Last frame to bake. Defaults to the scene range end.")] = None,
    step: Annotated[int, Field(description="Bake every Nth frame. 1 (default) keys every frame — exact but heavy; 2-4 gives smaller files at some loss of fidelity.")] = 1,
    visual_keying: Annotated[bool, Field(description="true (default) keys the FINAL visible transform including constraints and parenting, which is the whole point of baking. false keys only the raw local values and loses constraint results.")] = True,
    clear_constraints: Annotated[bool, Field(description="true removes the constraints afterwards, since the baked keys now reproduce their effect. Do this for export; keep them if you still want to tweak the setup.")] = False,
) -> dict:
    """Convert constraint- and parent-driven motion into explicit keyframes on every frame.

    Necessary before exporting to a game engine or another DCC, which cannot evaluate
    Blender's constraints — bake first or the animation arrives dead. It produces a lot of
    keyframes (one per frame per channel) and the original clean setup is hard to recover,
    so bake a copy or bake last.
    """
    return call("bake_animation", timeout=LONG, object=object, frame_start=frame_start, frame_end=frame_end, step=step,
                visual_keying=visual_keying, clear_constraints=clear_constraints)


@mcp.tool(annotations=READ_ONLY)
def list_shape_keys(
    object: Annotated[str, Field(description="Mesh object to inspect.")],
) -> list[dict]:
    """List a mesh's shape keys with their current values and ranges.

    Shape keys are stored deformations of the same mesh — facial expressions, blend
    shapes, morph targets. Returns empty for a mesh that has none.
    """
    return call("list_shape_keys", object=object)


@mcp.tool(annotations=UPDATE)
def set_shape_key(
    object: Annotated[str, Field(description="Mesh object.")],
    name: Annotated[str, Field(description="Shape key name. It is CREATED if it does not exist, capturing the mesh's current shape — so a typo silently makes a new key rather than failing.")],
    value: Annotated[float, Field(description="Blend amount, normally 0 (base shape) to 1 (full deformation). Values can be mixed across keys.")],
    frame: Annotated[int | None, Field(description="Also insert a keyframe on this value at this frame, so the shape animates. Omit to just set it.")] = None,
) -> dict:
    """Set a shape key's blend value, creating the key if needed, and optionally keyframe it.

    Keyframing the value is how blend-shape animation works — key it at 0 on one frame and
    1 on another to morph between shapes.
    """
    return call("set_shape_key", object=object, name=name, value=value, frame=frame)
