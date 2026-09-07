"""Materials。"""
from __future__ import annotations

from ..server import mcp
from ._base import call


@mcp.tool()
def list_materials(used_only: bool = False) -> list[dict]:
    """列出材质及使用它的对象。"""
    return call("list_materials", used_only=used_only)


@mcp.tool()
def get_material_info(name: str) -> dict:
    """材质详情：Principled 主要输入值、贴图、渲染设置、使用者。"""
    return call("get_material_info", name=name)


@mcp.tool()
def create_material(name: str, base_color: list[float] | None = None, metallic: float | None = None, roughness: float | None = None,
                    emission_color: list[float] | None = None, emission_strength: float | None = None, alpha: float | None = None,
                    ior: float | None = None, assign_to: str | None = None) -> dict:
    """新建 Principled BSDF 材质；alpha<1 自动切 BLENDED；assign_to 直接赋给对象。"""
    return call("create_material", name=name, base_color=base_color, metallic=metallic, roughness=roughness,
                emission_color=emission_color, emission_strength=emission_strength, alpha=alpha, ior=ior, assign_to=assign_to)


@mcp.tool()
def assign_material(object: str, material: str, slot: int | None = None) -> dict:
    """把材质赋给对象的槽位（默认 0，不存在则新建）。"""
    return call("assign_material", object=object, material=material, slot=slot)


@mcp.tool()
def set_principled_inputs(material: str, inputs: dict) -> dict:
    """批量设置 Principled BSDF 输入。键用 5.2 插槽名：Base Color, Metallic, Roughness, IOR, Alpha, Emission Color,
    Emission Strength, Specular IOR Level, Subsurface Weight, Transmission Weight, Coat Weight, Sheen Weight…"""
    return call("set_principled_inputs", material=material, inputs=inputs)


@mcp.tool()
def set_material_settings(material: str, surface_render_method: str | None = None, backface_culling: bool | None = None,
                          displacement_method: str | None = None, pass_index: int | None = None) -> dict:
    """材质渲染设置。surface_render_method: DITHERED/BLENDED；displacement_method: BUMP/DISPLACEMENT/BOTH。"""
    return call("set_material_settings", material=material, surface_render_method=surface_render_method,
                backface_culling=backface_culling, displacement_method=displacement_method, pass_index=pass_index)


@mcp.tool()
def add_image_texture(material: str, image_path: str, target: str = "Base Color", colorspace: str | None = None,
                      projection: str | None = None) -> dict:
    """加载贴图接到 Principled。target: Base Color/Roughness/Metallic/Normal(自动加 Normal Map)/Alpha/Emission Color/Height/AO。"""
    return call("add_image_texture", material=material, image_path=image_path, target=target, colorspace=colorspace, projection=projection)


@mcp.tool()
def create_pbr_material(name: str, base_color: str | None = None, roughness: str | None = None, metallic: str | None = None,
                        normal: str | None = None, height: str | None = None, ao: str | None = None, assign_to: str | None = None) -> dict:
    """用一组贴图路径一次建好 PBR 材质。"""
    return call("create_pbr_material", name=name, base_color=base_color, roughness=roughness, metallic=metallic, normal=normal,
                height=height, ao=ao, assign_to=assign_to)


@mcp.tool()
def delete_material(name: str, unlink_only: bool = False) -> dict:
    """删除材质（或仅从对象上解除）。"""
    return call("delete_material", name=name, unlink_only=unlink_only)
