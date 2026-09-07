import os

import pytest

from blender_mcp_pro.errors import BlenderError
from tests.conftest import TMP, call


def test_settings_roundtrip(blender):
    r = call(blender, "set_render_settings", engine="CYCLES", resolution=[320, 180], percentage=50, samples=8, fps=30,
             file_format="JPEG", film_transparent=True, denoise=False, engine_settings={"device": "CPU"})
    assert r["engine"] == "CYCLES" and r["resolution"] == [320, 180] and r["samples"]["cycles"] == 8 and r["fps"] == 30
    assert r["file_format"] == "JPEG" and r["film_transparent"] is True and r["cycles_device"] == "CPU"
    r = call(blender, "set_render_settings", engine="BLENDER_EEVEE", samples=16)
    assert r["samples"]["eevee"] == 16
    with pytest.raises(BlenderError):
        call(blender, "set_render_settings", engine="BOGUS")
    assert "CYCLES" in call(blender, "list_render_engines")
    cm = call(blender, "set_color_management", exposure=0.5, gamma=1.1)
    assert cm["exposure"] == 0.5 and cm["gamma"] == 1.1


def test_render_image_workbench(blender):
    call(blender, "set_render_settings", engine="BLENDER_WORKBENCH", resolution=[64, 48], percentage=100)
    out = str(TMP / "render_test.png")
    r = call(blender, "render_image", output_path=out, timeout=300)
    assert os.path.exists(r["path"]) and r["resolution"] == [64, 48] and len(r["image_base64"]) > 100 and r["mime"] == "image/png"
    r = call(blender, "render_image", return_image=False, timeout=300)
    assert "image_base64" not in r and r["path"].endswith("render_0001.png")


def test_render_animation(blender):
    call(blender, "set_render_settings", engine="BLENDER_WORKBENCH", resolution=[32, 32])
    pattern = str(TMP / "anim" / "f_####.png")
    r = call(blender, "render_animation", output_path=pattern, frame_start=1, frame_end=2, timeout=300)
    assert r["count"] == 2 and len(r["files"]) == 2 and r["files"][0].endswith("f_0001.png")


def test_viewport_screenshot_headless(blender):
    with pytest.raises(BlenderError) as ei:
        call(blender, "viewport_screenshot")
    assert ei.value.type == "NoViewportError"
