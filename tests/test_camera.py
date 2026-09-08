from tests.conftest import call, run_py

IN_VIEW = """
from bpy_extras.object_utils import world_to_camera_view
sc = bpy.context.scene; cam = bpy.data.objects[%r]; o = bpy.data.objects['Cube']
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
uv = [world_to_camera_view(sc, cam, p) for p in pts]
result = all(0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0 for v in uv)
"""


def test_create_set_active(blender):
    r = call(blender, "create_camera", name="Cam2", location=[0, -10, 2], lens=85, clip_end=500)
    assert r["lens"] == 85 and r["is_active"] and r["clip_end"] == 500
    assert call(blender, "get_scene_info")["active_camera"] == "Cam2"
    r = call(blender, "set_camera", name="Cam2", type="ORTHO", ortho_scale=12, dof={"focus_object": "Cube", "fstop": 1.4})
    assert r["type"] == "CAMERA" and r["projection"] == "ORTHO" and r["ortho_scale"] == 12 and r["dof"] == {"enabled": True, "focus_object": "Cube", "focus_distance": 10, "fstop": 1.4}
    assert call(blender, "set_active_camera", name="Camera")["active_camera"] == "Camera"
    assert [c["name"] for c in call(blender, "list_cameras")] == ["Cam2", "Camera"] or len(call(blender, "list_cameras")) == 2


def test_point_and_frame(blender):
    call(blender, "create_camera", name="C", location=[8, 8, 8])
    call(blender, "point_camera_at", camera="C", target="Cube")
    assert run_py(blender, IN_VIEW % "C") is True
    call(blender, "set_transform", name="Cube", scale=[6, 6, 6])
    r = call(blender, "frame_objects", camera="C", objects=["Cube"])
    assert r["distance"] > 10 and run_py(blender, IN_VIEW % "C") is True
    call(blender, "set_camera", name="C", type="ORTHO")
    r = call(blender, "frame_objects", camera="C", objects=["Cube"], margin=1.2)
    assert r["ortho_scale"] > 12 and run_py(blender, IN_VIEW % "C") is True


def test_frame_keeps_side(blender):
    """相机放在 +X-Y 象限，取景后仍从该侧看，而不是被推成俯视。"""
    call(blender, "create_camera", name="C", location=[8, -8, 3])
    r = call(blender, "frame_objects", camera="C", objects=["Cube"])
    x, y, z = r["location"]
    assert x > 0 and y < 0 and 0 < z < abs(x) and run_py(blender, IN_VIEW % "C") is True
