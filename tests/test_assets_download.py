"""资产下载工具的调用链测试：不联网、不需要 Blender，但真的把函数体跑一遍。

这两个工具的联网用例默认 skip，函数体从来没被执行过——改描述时把
polyhaven.download_asset 误写成 polyhaven.download 就是这么溜过去的（两个函数都存在、
都是 4 个参数，静态检查绑得上）。这里把网络层和 Blender 连接都换成假的，
让调用链本身跑起来。
"""
from __future__ import annotations

import pytest

from blender_mcp_pro.assets import polyhaven, sketchfab
from blender_mcp_pro.tools import assets as A


@pytest.fixture
def calls(monkeypatch):
    """记录转发给 Blender 的调用，不真的连 socket。"""
    recorded = []

    def fake_call(tool, timeout=60.0, **params):
        recorded.append((tool, params))
        if tool == "get_secret":
            return "fake-token"
        return {"ok": tool}

    monkeypatch.setattr(A, "call", fake_call)
    return recorded


def test_polyhaven_hdri_goes_to_world_lighting(monkeypatch, calls):
    monkeypatch.setattr(polyhaven, "download_asset",
                        lambda *a, **k: {"type": "hdris", "files": {"hdri": "/tmp/sky.hdr"}})
    out = A.polyhaven_download("sky", "hdris", "1k")
    assert calls == [("set_world_lighting", {"hdri_path": "/tmp/sky.hdr"})]
    assert out["result"] == {"ok": "set_world_lighting"}


def test_polyhaven_texture_builds_pbr_material(monkeypatch, calls):
    monkeypatch.setattr(polyhaven, "download_asset", lambda *a, **k: {
        "type": "textures",
        "files": {"base_color": "/tmp/c.jpg", "roughness": "/tmp/r.jpg", "normal": "/tmp/n.jpg"},
    })
    A.polyhaven_download("wood_planks", "textures", "2k")
    tool, params = calls[0]
    assert tool == "create_pbr_material"
    assert params["name"] == "wood_planks" and params["base_color"] == "/tmp/c.jpg"
    assert params["metallic"] is None  # 缺的贴图传 None，不该报错


def test_polyhaven_model_is_imported(monkeypatch, calls):
    monkeypatch.setattr(polyhaven, "download_asset",
                        lambda *a, **k: {"type": "models", "files": {"model": "/tmp/m.gltf"}})
    A.polyhaven_download("chair", "models")
    assert calls == [("import_file", {"path": "/tmp/m.gltf"})]


def test_polyhaven_download_passes_arguments_through(monkeypatch, calls):
    """签名必须真的对得上——这正是那次改错溜过去的地方。"""
    seen = {}

    def spy(asset_id, asset_type, resolution="1k", file_format=None):
        seen.update(asset_id=asset_id, asset_type=asset_type, resolution=resolution, file_format=file_format)
        return {"type": "hdris", "files": {"hdri": "/tmp/x.hdr"}}

    monkeypatch.setattr(polyhaven, "download_asset", spy)
    A.polyhaven_download("sky", "hdris", "4k", "exr")
    assert seen == {"asset_id": "sky", "asset_type": "hdris", "resolution": "4k", "file_format": "exr"}


def test_sketchfab_glb_is_imported(monkeypatch, calls):
    monkeypatch.setattr(sketchfab, "download_model", lambda uid, token: {"path": "/tmp/m.glb", "format": "glb"})
    A.sketchfab_download("abc123")
    assert ("get_secret", {"key": "sketchfab_token"}) in calls
    assert ("import_file", {"path": "/tmp/m.glb"}) in calls


def test_sketchfab_zip_is_extracted(monkeypatch, tmp_path, calls):
    import zipfile
    archive = tmp_path / "m.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("scene.gltf", "{}")
    monkeypatch.setattr(sketchfab, "download_model", lambda uid, token: {"path": str(archive), "format": "zip"})
    monkeypatch.setattr(A, "cache_path", lambda *parts: tmp_path / "out")
    A.sketchfab_download("abc123")
    imported = [p["path"] for t, p in calls if t == "import_file"]
    assert imported and imported[0].endswith("scene.gltf")


def test_sketchfab_without_token_explains_where_to_set_it(monkeypatch):
    monkeypatch.setattr(A, "call", lambda tool, timeout=60.0, **p: None)
    monkeypatch.delenv("SKETCHFAB_API_TOKEN", raising=False)
    with pytest.raises(Exception) as ei:
        A.sketchfab_download("abc123")
    assert "SKETCHFAB_API_TOKEN" in str(ei.value) and "Preferences" in str(ei.value)
