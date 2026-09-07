# blender_mcp — blender-mcp 本地自研版

让 Claude Code（或任何 MCP 客户端）通过自然语言驱动本机 **Blender 5.2 LTS**：
**17 个类目、159 个类型化工具**，覆盖建模、材质、节点、灯光、动画、相机、渲染、导入导出、UV/烘焙、批处理、资产、绑定与一键工作流。

- 平台：macOS / Windows / Linux（三端均已实测）
- Blender：5.2 LTS（不兼容 4.x）
- 依赖：Python 3.11+、[uv](https://docs.astral.sh/uv/)
- 许可：MIT

## 特性一览

- **159 个类型化工具**：每个工具都有明确的参数签名与说明，模型不需要猜 bpy API；`execute_code` 作为兜底可执行任意 Python。
- **纯本地、零联网插件**：Blender 插件只监听 `127.0.0.1:9877`，不访问网络；Poly Haven / Sketchfab 下载只在 MCP server 进程发生，落盘后再让插件按路径导入。
- **错误信息可读**：找不到对象 / 材质 / 节点 / 插槽时，错误会列出候选名并原样透传给模型，方便自纠。
- **可撤销**：所有写操作在 Blender 里 Ctrl+Z 可撤销，也提供 `undo` / `redo` 工具（GUI 下）。
- **一键工作流**：三点光、摄影棚、旋转展示动画、产品渲染、贴图文件夹建材质、表面散布、游戏资产导出。
- **本地 API 文档**：`get_api_docs("bpy.types.Object.location")` 不联网直接查 bpy 文档。
- **可视化反馈**：`render_image` / `viewport_screenshot` 可把图片直接回传给模型。

## 架构

```
Claude Code ──stdio──▶ MCP server（src/blender_mcp_pro，uv 管理的 Python 3.11+）
                            │  每个工具：类型化签名 → {tool, params} JSON 转发
                            ▼
                    127.0.0.1:9877（4 字节长度前缀 + JSON 帧，长连接）
                            │
                Blender 5.2 extension（addon/blender_mcp_pro，Blender 内置 Python 3.13）
                            │  守护线程收请求 → 主线程串行执行 bpy → 自动 undo_push
                            ▼
                    handlers/<类目>.py：真正的 bpy 代码
```

胖 addon + 薄 server：所有 bpy 逻辑都在插件侧，server 只做参数校验与转发，两边工具名一一对应并由对账测试锁住。

## 功能清单（17 类 159 个工具）

完整参数签名见 [docs/tools.md](docs/tools.md)（由 `dump-tools` 自动生成）。

| 类目 | 数量 | 工具 |
|---|---|---|
| **场景与物体** Scene | 16 | `get_scene_info` `list_objects` `get_object_info` `create_primitive` `delete_object` `duplicate_object` `set_transform` `rename_object` `set_parent` `set_visibility` `select_objects` `manage_collection` `join_objects` `apply_transforms` `set_origin` `set_custom_property` |
| **材质** Materials | 9 | `list_materials` `get_material_info` `create_material` `assign_material` `set_principled_inputs` `set_material_settings` `add_image_texture` `create_pbr_material` `delete_material` |
| **Shader 节点** | 10 | `list_shader_nodes` `add_shader_node` `remove_shader_node` `set_node_input` `set_node_property` `link_nodes` `unlink_nodes` `set_color_ramp` `build_node_tree` `get_node_types` |
| **灯光** Lights | 6 | `list_lights` `get_light_info` `create_light` `set_light` `point_light_at` `set_world_lighting` |
| **修改器** Modifiers | 8 | `list_modifier_types` `list_modifiers` `get_modifier_settings` `add_modifier` `set_modifier` `remove_modifier` `apply_modifier` `move_modifier` |
| **动画** Animation | 15 | `get_animation_info` `set_frame_range` `set_current_frame` `insert_keyframe` `insert_keyframes_batch` `delete_keyframe` `list_keyframes` `set_interpolation` `add_fcurve_modifier` `assign_action` `nla_push_down` `add_nla_strip` `bake_animation` `list_shape_keys` `set_shape_key` |
| **几何节点** Geometry Nodes | 11 | `list_node_groups` `create_geometry_nodes` `get_node_tree` `add_geometry_node` `remove_geometry_node` `link_geometry_nodes` `unlink_geometry_nodes` `set_geometry_node_input` `add_group_socket` `set_gn_modifier_input` `build_geometry_node_tree` |
| **相机** Camera | 7 | `list_cameras` `get_camera_info` `create_camera` `set_camera` `set_active_camera` `point_camera_at` `frame_objects` |
| **渲染** Render | 7 | `get_render_settings` `list_render_engines` `set_render_settings` `set_color_management` `render_image` `render_animation` `viewport_screenshot` |
| **导入导出** IO | 5 | `import_file` `export_file` `append_from_blend` `save_blend` `open_blend` |
| **UV 与贴图** UV & Texture | 10 | `list_uv_maps` `add_uv_map` `remove_uv_map` `unwrap_uv` `pack_uv_islands` `mark_seams` `create_image` `bake_texture` `save_image` `list_images` |
| **批处理** Batch | 8 | `batch_transform` `batch_rename` `batch_apply_material` `batch_add_modifier` `batch_set_property` `batch_delete` `distribute_objects` `randomize_transform` |
| **资产** Assets | 8 | `polyhaven_categories` `polyhaven_search` `polyhaven_download` `sketchfab_search` `sketchfab_download` `list_asset_libraries` `search_local_assets` `import_local_asset` |
| **绑定** Rigging | 12 | `create_armature` `list_bones` `add_bone` `set_bone` `remove_bone` `parent_to_armature` `add_bone_constraint` `set_pose` `reset_pose` `set_vertex_group_weights` `add_rigify_metarig` `generate_rigify_rig` |
| **绑定诊断** Rig Diagnostics | 7 | `check_rig` `check_bone_hierarchy` `check_bone_naming` `find_unweighted_vertices` `get_bone_influence` `list_constraint_issues` `normalize_weights` |
| **场景工具** Utilities | 13 | `execute_code` `get_blender_info` `get_api_docs` `undo` `redo` `purge_orphans` `set_units` `set_cursor` `measure_distance` `get_bounding_box` `ray_cast` `check_mesh` `mesh_cleanup` |
| **一键工作流** Workflows | 7 | `setup_three_point_lighting` `setup_studio_scene` `turntable_animation` `quick_product_render` `material_from_texture_folder` `scatter_objects` `export_for_game` |

几个值得单独说的能力：

- **节点树一次成型**：`build_node_tree` / `build_geometry_node_tree` 接收 `nodes=[{type,name,location,inputs,properties}]` 与 `links=[...]`，一次调用建整棵树，不用逐节点往返。
- **PBR 材质**：`create_pbr_material` 给一组贴图路径直接建好；`material_from_texture_folder` 扫描文件夹按文件名识别 basecolor / roughness / metallic / normal / height / ao。
- **导入导出格式**：obj / fbx / gltf / glb / usd / usda / usdc / stl / ply / abc / blend，按后缀识别，`options` 透传给 Blender 算子；`export_for_game` 复制→应用修改器→三角化→缩放→导出。
- **资产**：Poly Haven HDRI 下载后自动接到世界光，纹理自动建 PBR 材质，模型直接导入；Sketchfab 需 API token；本地资产库可按类型/关键字搜索并导入。
- **绑定**：从零建骨架、加约束、摆姿势、写顶点组权重；Rigify 元骨架（human / quadruped / cat / wolf / horse / shark / bird）与生成；`check_rig` 一次体检零长骨、多根、无权重顶点、未归一权重、未应用缩放、约束目标丢失、命名不对称。
- **烘焙**：`bake_texture` 用 Cycles 烘 DIFFUSE / NORMAL / AO / ROUGHNESS / EMIT / COMBINED 等到贴图，支持 selected-to-active。
- **相机取景**：`frame_objects` 沿相机当前朝向后退到恰好框住目标；`point_camera_at` / `point_light_at` 对准对象或坐标。
- **几何查询**：`ray_cast`、`measure_distance`、`get_bounding_box`、`check_mesh`（非流形、松散点、退化面等）。

## 安装

前提：已安装 Blender 5.2 LTS 与 [uv](https://docs.astral.sh/uv/)。

```bash
git clone <本仓库> blender_mcp && cd blender_mcp
uv sync
uv run blender-mcp-pro install-addon
```

`install-addon` 会把 `addon/blender_mcp_pro` 链接进 Blender 的用户扩展目录，然后用无头 Blender 启用扩展并保存偏好。

| 平台 | Blender 默认查找位置 | 扩展目录 | 链接方式 |
|---|---|---|---|
| macOS | `/Applications/Blender.app` | `~/Library/Application Support/Blender/5.2/extensions/user_default` | 软链 |
| Windows | `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` | `%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default` | 软链；无权限时自动改用目录 junction（不需要管理员） |
| Linux | `PATH` 里的 `blender`、`/usr/bin`、`/snap/bin` | `~/.config/blender/5.2/extensions/user_default` | 软链 |

- Blender 装在别处：先设 `BLENDER_MCP_BLENDER=<blender 可执行文件>`；扩展目录同理 `BLENDER_MCP_EXT_DIR`。
- 不想用链接：`install-addon --copy`（之后改插件源码要重跑安装）。
- **安装时如果有 GUI Blender 开着**，它退出时会用自己内存里的偏好覆盖。请在已打开的 Blender 里再确认一次：Edit ▸ Preferences ▸ Add-ons，搜 "MCP Pro"，勾上。
- 启用后默认自动起 server；3D 视口按 N，"MCP Pro" 面板可看状态、手动 Start / Stop、改端口。

### 接入 Claude Code

```bash
claude mcp add --scope user blender-pro -- uv --directory <仓库绝对路径> run blender-mcp-pro serve
claude mcp list        # 看到 blender-pro … Connected
```

Windows 示例：

```bash
claude mcp add --scope user blender-pro -- uv --directory C:\work\blender_mcp run blender-mcp-pro serve
```

其他 MCP 客户端（Cursor、Claude Desktop 等）用同样的 stdio 命令：`uv --directory <仓库> run blender-mcp-pro serve`。

可选环境变量：`BLENDER_MCP_HOST` / `BLENDER_MCP_PORT`（默认 `127.0.0.1` / `9877`）、`SKETCHFAB_API_TOKEN`。

### 卸载

```bash
uv run blender-mcp-pro uninstall-addon
claude mcp remove blender-pro -s user
```

## 使用示例

打开 GUI Blender 后，在 Claude Code 里直接说：

- "场景里有什么？" → `get_scene_info` / `list_objects`
- "建一个 2 米高的圆柱，用磨砂金属材质" → `create_primitive` + `create_material` + `set_principled_inputs`
- "给这个物体做三点光并渲染一张 1080p 产品图" → `quick_product_render` 或 `setup_three_point_lighting` + `frame_objects` + `render_image`
- "从 Poly Haven 拉一张 2k 的室内 HDRI 当环境光" → `polyhaven_search` + `polyhaven_download`
- "把 `textures/wood/` 里的贴图做成材质贴到桌子上" → `material_from_texture_folder`
- "给角色加 Rigify 人形骨架并体检" → `add_rigify_metarig` + `generate_rigify_rig` + `check_rig`
- "把选中的东西导出成游戏用的 GLB" → `export_for_game`
- "用 bmesh 拼一个积木风格的高达" → `execute_code`（任意 bpy 脚本），再 `frame_objects` + `render_image` 看效果

## 使用约定

- 位置 / 旋转 / 缩放都是 `[x, y, z]`，旋转是**弧度**欧拉角；颜色 `[r, g, b]` 或 `[r, g, b, a]`，取值 0–1。
- 凡接受 `objects` 的工具：名字列表，或 `{"pattern": "Cube*"}` / `{"collection": "Props"}` / `{"type": "MESH"}` / `{"selected": true}`。
- 找不到对象 / 材质 / 节点 / 插槽时，错误信息会列出候选名。
- 所有写操作在 Blender 里 Ctrl+Z 可撤销；只读工具不进 undo 栈。
- Principled BSDF 插槽用 5.2 的名字：`Base Color, Metallic, Roughness, IOR, Alpha, Emission Color, Emission Strength, Specular IOR Level, …`
- `execute_code` 预置 `bpy / bmesh / mathutils / Vector / math`，`return_var` 可取回变量。
- 渲染与下载缓存在 `~/.cache/blender-mcp-pro/`（`renders/` `hdris/` `textures/` `models/` `sketchfab/`），可随时清理。

## 开发与测试

```bash
uv run pytest -q                                   # 154 个用例；集成测试自动拉起无头 Blender
BLENDER_MCP_ONLINE_TESTS=1 uv run pytest tests/test_assets.py   # 顺带跑 Poly Haven 联网用例
uv run blender-mcp-pro dump-tools > docs/tools.md  # 重新生成工具清单
```

- 测试分三层：协议单测（假 Blender）、handler 集成测试（无头 Blender，`--factory-startup`）、MCP stdio 端到端（真实 MCP 客户端 → server → 无头 Blender）。
- 改了插件代码：Blender 里 F3 → "Reload Scripts"（软链 / junction 安装下源码即生效）。
- 改了 server 代码：Claude Code 里 `/mcp` 重启该 server。
- 新增工具：`addon/blender_mcp_pro/handlers/<类目>.py` 里 `@command("name")`，`src/blender_mcp_pro/tools/<类目>.py` 里 `@mcp.tool()`；`tests/test_parity.py` 会盯住两边名字一致。
- handler 模块**顶层不能调用 bpy**（对账测试用假 bpy 加载插件），只在函数体里用。
- 维护笔记与踩坑记录：[.claude/MAINTENANCE.md](.claude/MAINTENANCE.md)、[.claude/PITFALLS.md](.claude/PITFALLS.md)。

## 已知限制

- `viewport_screenshot`、`undo` / `redo` 需要 GUI Blender；无头模式明确报错。
- 无头模式下 EEVEE 能否渲染取决于 GPU 上下文；测试固定用 WORKBENCH。GUI 里 EEVEE / Cycles 都正常。
- Sketchfab 下载要 API token：Preferences ▸ Add-ons ▸ Blender MCP Pro 里填，或环境变量 `SKETCHFAB_API_TOKEN`。
- 只做 5.2 LTS，不兼容 4.x。
- 159 个工具的 schema 会占一部分上下文；若感觉慢，可考虑按类目裁剪（待办）。

## 文档

- 安装与开发细节：[docs/README.md](docs/README.md)
- 全部工具签名：[docs/tools.md](docs/tools.md)
- 设计与决策记录：[docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md](docs/superpowers/specs/2026-09-07-blender-mcp-pro-design.md)

## 许可

[MIT](LICENSE)
