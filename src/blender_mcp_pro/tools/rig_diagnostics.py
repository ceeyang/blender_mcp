"""Rig Diagnostics — find and fix the problems that make a rig deform badly."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..server import mcp
from ._base import call
from ._types import READ_ONLY, UPDATE


@mcp.tool(annotations=READ_ONLY)
def check_rig(
    armature: Annotated[str, Field(description="Armature to audit, together with the meshes skinned to it.")],
) -> dict:
    """Run a full health check on a rig and report every problem found, each with a severity, a code and a hint on how to fix it.

    Covers the usual causes of bad deformation: zero-length bones, deform bones with no
    matching vertex group, unweighted vertices, weights that don't sum to 1, unapplied
    object scale, constraints pointing at missing targets, and asymmetric .L/.R naming.
    Run it after parent_to_armature and before animating — most 'the mesh tears when I
    pose it' problems show up here. Read-only; normalize_weights and
    set_vertex_group_weights are what actually fix things.
    """
    return call("check_rig", armature=armature)


@mcp.tool(annotations=READ_ONLY)
def check_bone_hierarchy(
    armature: Annotated[str, Field(description="Armature to inspect.")],
) -> dict:
    """Report the bone parent tree, plus any orphan bones and multiple roots.

    A rig should normally have a single root; several roots usually means a limb was built
    detached and will not follow the body. Use it to understand an unfamiliar rig's
    structure before editing it.
    """
    return call("check_bone_hierarchy", armature=armature)


@mcp.tool(annotations=READ_ONLY)
def check_bone_naming(
    armature: Annotated[str, Field(description="Armature to check.")],
    convention: Annotated[str, Field(description="'BLENDER' checks the standard .L/.R suffix convention for symmetric bones.")] = "BLENDER",
) -> dict:
    """Check bone names against the left/right convention, flagging bones whose mirror counterpart is missing.

    Naming matters functionally, not cosmetically: Blender's symmetry tools, mirrored
    weight painting and Rigify all rely on the .L/.R suffix. A bone named 'arm_left'
    silently loses all of that.
    """
    return call("check_bone_naming", armature=armature, convention=convention)


@mcp.tool(annotations=READ_ONLY)
def find_unweighted_vertices(
    object: Annotated[str, Field(description="Skinned mesh object to scan.")],
    threshold: Annotated[float, Field(description="Total weight below which a vertex counts as unweighted. The default catches vertices with no meaningful influence at all.")] = 0.0001,
) -> dict:
    """Find vertices that no bone influences, returning their indices.

    These are the vertices that stay behind when the rig moves, producing stretched
    spikes. Feed the returned indices to set_vertex_group_weights to assign them to the
    right bone.
    """
    return call("find_unweighted_vertices", object=object, threshold=threshold)


@mcp.tool(annotations=READ_ONLY)
def get_bone_influence(
    object: Annotated[str, Field(description="Skinned mesh object.")],
    vertex_index: Annotated[int, Field(description="Index of the vertex to inspect, e.g. one reported by find_unweighted_vertices.")],
) -> list[dict]:
    """Show which bones influence one specific vertex, and by how much.

    The tool for diagnosing a single bad spot: when one area of the mesh deforms wrongly,
    this tells you whether it is weighted to the wrong bone or split between two.
    """
    return call("get_bone_influence", object=object, vertex_index=vertex_index)


@mcp.tool(annotations=READ_ONLY)
def list_constraint_issues(
    armature: Annotated[str, Field(description="Armature whose bone constraints to validate.")],
) -> list[dict]:
    """List bone constraints that are broken: empty targets, subtargets naming bones that don't exist, out-of-range IK chain lengths.

    Broken constraints fail silently in Blender — the control simply does nothing — so
    this is how you find out why a rig control stopped working.
    """
    return call("list_constraint_issues", armature=armature)


@mcp.tool(annotations=UPDATE)
def normalize_weights(
    object: Annotated[str, Field(description="Skinned mesh whose weights to normalise.")],
    lock_active: Annotated[bool, Field(description="true keeps the active vertex group's weights fixed and rescales only the others around them.")] = False,
    groups: Annotated[list[str] | None, Field(description="Restrict normalisation to these vertex groups. Omit to normalise across all of them.")] = None,
) -> dict:
    """Rescale each vertex's weights so they sum to 1.0 across all bones.

    Weights totalling more than 1 inflate the mesh when posed, less than 1 shrinks it —
    both look like the mesh is melting. Run this after manual set_vertex_group_weights
    edits, or when check_rig reports UNNORMALIZED_WEIGHTS.
    """
    return call("normalize_weights", object=object, lock_active=lock_active, groups=groups)
