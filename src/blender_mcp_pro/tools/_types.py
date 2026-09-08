"""Shared parameter annotations and ToolAnnotations presets.

Every tool declares annotations so an MCP client knows, without calling it, whether
the tool reads or writes, whether it destroys data, and whether it touches the network.
Parameter descriptions live here when the same argument appears across many tools, so
the wording (and the units) stay identical everywhere.
"""
from __future__ import annotations

from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

# --- ToolAnnotations presets -------------------------------------------------
# read_only: does not change the .blend at all.
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
# create: adds new datablocks; calling twice yields two of them, so not idempotent.
CREATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
# update: sets properties on existing data; same args twice leaves the same state.
UPDATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
# destructive: removes data or irreversibly bakes it down.
DESTRUCTIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False)
# writes a file on disk but does not alter the scene.
WRITES_FILE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
# network reads / writes (asset providers).
NET_READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
NET_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)

# --- Shared parameter annotations --------------------------------------------
OBJECTS_DOC = (
    'Objects to act on: either a list of exact names ["Cube", "Lamp"], or ONE filter dict — '
    '{"pattern": "Rock_*"} (glob on name), {"collection": "Props"}, '
    '{"type": "MESH"} (MESH/LIGHT/CAMERA/EMPTY/ARMATURE/CURVE/FONT), or {"selected": true}. '
    "Fails if a listed name does not exist or a filter matches nothing."
)
Objects = Annotated[list[str] | dict | str, Field(description=OBJECTS_DOC)]

Location = Annotated[
    list[float] | None,
    Field(description="World position [x, y, z] in meters (Blender is Z-up: +Z is up, -Y is toward the default front view)."),
]
Rotation = Annotated[
    list[float] | None,
    Field(description="Euler XYZ rotation in RADIANS, not degrees — 90 deg is 1.5708, a full turn is 6.2832."),
]
Scale = Annotated[list[float] | None, Field(description="Scale factors [x, y, z]; 1.0 means unchanged.")]
Color = Annotated[
    list[float] | None,
    Field(description="Linear RGB [r, g, b] or RGBA, each component 0.0-1.0 (not 0-255). Alpha defaults to 1."),
]
Timeout = 60.0
