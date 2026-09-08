"""Rigging — armatures, bones, constraints, posing, weights and Rigify."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import LONG, call
from ._types import CREATE, DESTRUCTIVE, READ_ONLY, UPDATE, Objects


@mcp.tool(annotations=CREATE)
def create_armature(
    name: Annotated[str | None, Field(description="Name for the armature object. Defaults to 'Armature'.")] = None,
    location: Annotated[list[float] | None, Field(description="World position [x, y, z] of the armature object. Bone coordinates below are relative to this.")] = None,
    bones: Annotated[list[dict] | None, Field(description="Bones to create: [{'name': 'spine', 'head': [0,0,0], 'tail': [0,0,1]}, {'name': 'chest', 'head': [0,0,1], 'tail': [0,0,1.6], 'parent': 'spine', 'connect': true}, ...]. 'head' is the joint the bone rotates around and 'tail' its far end, both in armature-local meters. 'parent' must name an earlier bone in the list; 'connect' glues head to the parent's tail; 'roll' sets the twist in radians.")] = None,
) -> dict:
    """Create an armature and its whole bone chain in one call.

    A bone's HEAD is its pivot, so place heads at actual joints. Define bones parent-first
    in the list, since 'parent' can only refer to a bone already created. This only builds
    the skeleton — parent_to_armature is what makes a mesh follow it.
    """
    return call("create_armature", name=name, location=location, bones=bones)


@mcp.tool(annotations=READ_ONLY)
def list_bones(
    armature: Annotated[str, Field(description="Armature object to inspect.")],
    pose: Annotated[bool, Field(description="true also returns each bone's current pose transform (location, rotation, scale) rather than only its rest position.")] = False,
) -> list[dict]:
    """List an armature's bones with head, tail, parent and length.

    The reference for every other tool here, which addresses bones by name. Use
    check_bone_hierarchy for the tree structure and check_rig for problems.
    """
    return call("list_bones", armature=armature, pose=pose)


@mcp.tool(annotations=CREATE)
def add_bone(
    armature: Annotated[str, Field(description="Armature to add the bone to.")],
    name: Annotated[str, Field(description="Bone name. Use Blender's .L/.R suffix convention for symmetric limbs ('arm.L', 'arm.R') so mirroring and Rigify work.")],
    head: Annotated[list[float], Field(description="Joint position [x, y, z] in armature-local meters — the point the bone pivots around.")],
    tail: Annotated[list[float], Field(description="Far end of the bone [x, y, z]. Head and tail must differ or the bone is zero-length and Blender discards it.")],
    parent: Annotated[str | None, Field(description="Name of an existing bone to parent this one to.")] = None,
    roll: Annotated[float, Field(description="Twist around the bone's own axis in RADIANS, which sets the local axes used by constraints and IK.")] = 0.0,
    connect: Annotated[bool, Field(description="true snaps this bone's head to its parent's tail and keeps them joined, giving a continuous chain like a limb. false leaves a gap, right for a floating control bone.")] = False,
) -> dict:
    """Add one bone to an existing armature.

    Use create_armature to build a whole skeleton at once; this is for extending one.
    Zero-length bones are silently dropped by Blender, so make sure head != tail.
    """
    return call("add_bone", armature=armature, name=name, head=head, tail=tail, parent=parent, roll=roll,
                connect=connect)


@mcp.tool(annotations=UPDATE)
def set_bone(
    armature: Annotated[str, Field(description="Armature that owns the bone.")],
    bone: Annotated[str, Field(description="Bone to modify.")],
    head: Annotated[list[float] | None, Field(description="New joint position in armature-local meters.")] = None,
    tail: Annotated[list[float] | None, Field(description="New far end position.")] = None,
    roll: Annotated[float | None, Field(description="Twist around the bone axis in radians.")] = None,
    parent: Annotated[str | None, Field(description="New parent bone name.")] = None,
    connect: Annotated[bool | None, Field(description="Whether the head stays glued to the parent's tail.")] = None,
    deform: Annotated[bool | None, Field(description="false makes the bone NOT deform the mesh — the standard setting for control bones and IK targets, which should drive other bones without pulling geometry themselves.")] = None,
    inherit_scale: Annotated[str | None, Field(description="How the bone inherits parent scale: 'FULL', 'NONE', 'FIX_SHEAR', 'ALIGNED', 'AVERAGE'.")] = None,
) -> dict:
    """Change a bone's rest position, roll, parenting or deform behaviour.

    This edits the REST pose (the skeleton's base shape), not the current pose — use
    set_pose for posing. Moving bones after skinning shifts the mesh's bind, so do this
    before parent_to_armature where you can.
    """
    return call("set_bone", armature=armature, bone=bone, head=head, tail=tail, roll=roll, parent=parent,
                connect=connect, deform=deform, inherit_scale=inherit_scale)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_bone(
    armature: Annotated[str, Field(description="Armature that owns the bone.")],
    bone: Annotated[str, Field(description="Bone to delete. Its children are unparented rather than deleted.")],
) -> dict:
    """Delete a bone from an armature.

    Vertex groups on skinned meshes keep the bone's name and are simply no longer driven,
    so the geometry they held goes limp — check with check_rig afterwards.
    """
    return call("remove_bone", armature=armature, bone=bone)


@mcp.tool(annotations=UPDATE)
def parent_to_armature(
    objects: Objects,
    armature: Annotated[str, Field(description="Armature that will drive the meshes.")],
    method: Annotated[str, Field(description="'AUTOMATIC' (default) computes weights from bone proximity — good enough for most props and a decent start for characters; 'ENVELOPE' uses each bone's envelope radius; 'EMPTY_GROUPS' creates named vertex groups with no weights, for painting them yourself; 'DEFORM' parents without creating groups at all.")] = "AUTOMATIC",
) -> dict:
    """Skin meshes to an armature so they deform when it is posed.

    Adds an ARMATURE modifier and, for AUTOMATIC, the vertex groups that assign each
    vertex to bones. Apply object scale first (apply_transforms) — non-uniform scale makes
    automatic weights misbehave. Verify the result with check_rig and
    find_unweighted_vertices.
    """
    return call("parent_to_armature", objects=objects, armature=armature, method=method)


@mcp.tool(annotations=CREATE)
def add_bone_constraint(
    armature: Annotated[str, Field(description="Armature that owns the bone.")],
    bone: Annotated[str, Field(description="POSE bone to constrain.")],
    type: Annotated[str, Field(description="'IK' (inverse kinematics — the classic 'move the hand, the arm follows'), 'COPY_ROTATION', 'COPY_LOCATION', 'COPY_SCALE', 'TRACK_TO', 'DAMPED_TRACK', 'LIMIT_ROTATION', 'LIMIT_LOCATION', 'CHILD_OF', 'STRETCH_TO'.")],
    settings: Annotated[dict | None, Field(description="Constraint properties, e.g. {'target': 'Armature', 'subtarget': 'hand_ik', 'chain_count': 2} for IK, or {'target': 'Cube', 'influence': 0.5}. 'target' takes an OBJECT name and 'subtarget' a bone name within it. Look properties up with get_api_docs('bpy.types.KinematicConstraint').")] = None,
) -> dict:
    """Add a constraint to a pose bone, making it follow, copy or be limited by something else.

    Constraints are how rigs get their controls — an IK chain on the forearm with a
    control bone as subtarget turns a two-bone chain into a draggable hand. Constraints
    are evaluated live and not baked, so exporters need bake_animation first.
    list_constraint_issues catches targets that don't resolve.
    """
    return call("add_bone_constraint", armature=armature, bone=bone, type=type, settings=settings)


@mcp.tool(annotations=UPDATE)
def set_pose(
    armature: Annotated[str, Field(description="Armature to pose.")],
    bones: Annotated[dict, Field(description="Bone names mapped to their pose transforms: {'arm.L': {'rotation_euler': [0, 0, 0.5]}, 'head': {'location': [0, 0, 0.1], 'scale': [1, 1, 1]}}. Rotations are in RADIANS; use 'rotation_quaternion' with four components instead if you prefer quaternions (the bone's rotation mode is switched for you).")],
    keyframe: Annotated[bool, Field(description="true also inserts keyframes for the channels you set, turning the pose into animation.")] = False,
    frame: Annotated[int | None, Field(description="Frame to key at when keyframe=true. Defaults to the current frame.")] = None,
) -> dict:
    """Pose several bones at once, optionally keyframing the result.

    Pose transforms are relative to the rest pose, so all-zero rotation means 'as built'.
    This is the animation loop for characters: set_pose with keyframe=true at one frame,
    then a different pose at a later frame. reset_pose returns to rest.
    """
    return call("set_pose", armature=armature, bones=bones, keyframe=keyframe, frame=frame)


@mcp.tool(annotations=UPDATE)
def reset_pose(
    armature: Annotated[str, Field(description="Armature to reset.")],
    bones: Annotated[list[str] | None, Field(description="Specific bones to clear. Omit to reset every bone in the armature.")] = None,
) -> dict:
    """Return bones to their rest pose, clearing pose location, rotation and scale.

    Does not delete keyframes — on an animated rig the pose snaps back as soon as the
    frame changes. Use it to get a clean starting point before posing.
    """
    return call("reset_pose", armature=armature, bones=bones)


@mcp.tool(annotations=UPDATE)
def set_vertex_group_weights(
    object: Annotated[str, Field(description="Mesh object whose weights to edit.")],
    group: Annotated[str, Field(description="Vertex group name, which must match a bone name to drive deformation. Created if it does not exist.")],
    weights: Annotated[list[list[float]] | None, Field(description="Explicit per-vertex weights as [[vertex_index, weight], ...], weight 0-1. Get indices from find_unweighted_vertices or check_mesh.")] = None,
    all: Annotated[float | None, Field(description="Assign this weight to EVERY vertex of the mesh, ignoring `weights`. Handy for rigid props that should follow one bone completely (all=1.0).")] = None,
    mode: Annotated[str, Field(description="'REPLACE' (default) sets the weight outright, 'ADD' adds to the existing value, 'SUBTRACT' removes from it.")] = "REPLACE",
) -> dict:
    """Set vertex group weights, controlling how strongly each bone pulls each vertex.

    Weights across all groups should total 1.0 per vertex or the mesh deforms strangely —
    normalize_weights fixes that after manual edits. The group name must match the bone
    name exactly for the ARMATURE modifier to use it.
    """
    return call("set_vertex_group_weights", object=object, group=group, weights=weights, all=all, mode=mode)


@mcp.tool(annotations=CREATE)
def add_rigify_metarig(
    type: Annotated[str, Field(description="'human' (full biped with face and fingers), 'basic_human' (simplified biped), 'basic_quadruped', or another Rigify metarig type.")] = "human",
    name: Annotated[str | None, Field(description="Name for the metarig object.")] = None,
) -> dict:
    """Add a Rigify metarig — a pre-built template skeleton you position to match your character.

    Enables the Rigify add-on if needed. The metarig is NOT the final rig: move its bones
    to fit your mesh with set_bone, then call generate_rigify_rig to build the real,
    control-rich rig from it.
    """
    return call("add_rigify_metarig", type=type, name=name)


@mcp.tool(annotations=CREATE)
def generate_rigify_rig(
    metarig: Annotated[str, Field(description="The metarig object created by add_rigify_metarig and adjusted to fit your character.")],
) -> dict:
    """Generate a full production rig from a Rigify metarig, with IK/FK controls, custom shapes and switches.

    This is the payoff of the Rigify workflow: a complete animator-ready control rig
    without hand-building constraints. Fit the metarig to your mesh FIRST — regenerating
    after changes replaces the rig and loses work done on the old one. Takes a while on
    the full 'human' metarig; the call allows up to 10 minutes.
    """
    return call("generate_rigify_rig", timeout=LONG, metarig=metarig)
